import os, json
from urllib.parse import quote as urlencode

import yt_dlp
import discord

TOKEN = os.getenv('DISCORD_TOKEN')
PUBLIC_ADDRESS = os.getenv('PUBLIC_ADDRESS')

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
	print(f'{client.user} is connected to the following guilds:')
	for guild in client.guilds:
		print(f'{guild.name} (id:{guild.id})')

@client.event
async def on_message(message):
	try:
		if message.author == client.user:
			return

		if '!yt' in message.content:
			videourl = message.content.split("!yt ")[1]

			prog_msg_str = f'Attempting to DL: <{videourl}>'
			prog_msg = await message.channel.send(prog_msg_str)

			class Logger(object):
				def __init__(self):
					self.output_msgs = []

				def push_to_output(self, msg):
					ignored_msgs = [
						": Downloading webpage",
						": Downloading android player API JSON",
						"/s ETA ",
						"Deleting original file"
					]
					append = True
					for line in ignored_msgs:
						if line in msg:
							append = False
					if append:
						self.output_msgs.append(msg)

				def debug(self, msg):
					self.push_to_output(msg)
				def warning(self, msg):
					self.push_to_output(msg)
				def error(self, msg):
					self.push_to_output(msg)

			logger = Logger()

			ydl_opts = {
				'quiet': True,
				'no_warnings': True,
				'restrict-filenames': True,
				'outtmpl': 'downloads/[%(uploader)s] %(title)s.%(ext)s',
				'logger': logger
			}

			with yt_dlp.YoutubeDL(ydl_opts) as ydl:
				info = ydl.extract_info(videourl, download=False)
				title = info["title"]
				msg_content = f"Attempting to DL: <{videourl}>\nTitle: {title}\nDownloading..."
				await prog_msg.edit(content=msg_content)

				info = ydl.extract_info(videourl, download=True)
				log = "\n".join(logger.output_msgs)
				filename = ydl.prepare_filename(info)
				if PUBLIC_ADDRESS and PUBLIC_ADDRESS != "YourPublicWebAddressHere":
					filename = f"http://{PUBLIC_ADDRESS}/{urlencode(filename.replace('downloads/', ''))}"
				msg_content += f"\n{log}\nOutput:\n{filename}"
				await prog_msg.edit(content=msg_content)

			with open('downloads/filelist.json', 'w') as f:
				json.dump({"files" : os.listdir('downloads')}, f)
	except Exception as e:
		print(e)
		pass

client.run(TOKEN)
