import os, json, asyncio
from urllib.parse import quote as urlencode

import yt_dlp
import discord

TOKEN = os.getenv('DISCORD_TOKEN')
PUBLIC_ADDRESS = os.getenv('PUBLIC_ADDRESS')

with open("options.json") as options_file:
	ydl_opts = json.load(options_file)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
	print(f'{client.user} is connected to the following guilds:')
	for guild in client.guilds:
		print(f'{guild.name} (id:{guild.id})')

class Logger(object):
	def __init__(self):
		self.output_msgs = []

	def push_to_output(self, msg):
		ignored_msgs = [
			": Downloading webpage",
			": Downloading android player API JSON",
			"/s ETA ",
			"Deleting original file",
			"(frag"
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

@client.event
async def on_message(message):
	try:
		if message.author == client.user:
			return

		if '!yt' in message.content:
			videourl = message.content.split("!yt ")[1]

			prog_msg_str = f'Attempting to DL: <{videourl}>'
			prog_msg = await message.channel.send(prog_msg_str)

			logger = Logger()

			opts = ydl_opts.copy()
			opts['logger'] = logger

			loop = asyncio.get_running_loop()
			with yt_dlp.YoutubeDL(opts) as ydl:
				info = await loop.run_in_executor(None, lambda: ydl.extract_info(videourl, download=False))
				title = info["title"]
				msg_content = f"Attempting to DL: <{videourl}>\nTitle: {title}\nDownloading..."
				await prog_msg.edit(content=msg_content)

				info = await loop.run_in_executor(None, lambda: ydl.extract_info(videourl, download=True))
				log = "\n".join(logger.output_msgs)
				filename = await loop.run_in_executor(None, lambda: ydl.prepare_filename(info))
				if PUBLIC_ADDRESS and PUBLIC_ADDRESS != "YourPublicWebAddressHere":
					filename = f"http://{PUBLIC_ADDRESS}/{urlencode(filename.replace('downloads/', ''))}"
				msg_content += f"\n{log}\nOutput:\n{filename}"
				await prog_msg.edit(content=msg_content)
				res_msg = await message.channel.send(filename)

			with open('downloads/filelist.json', 'w') as f:
				json.dump({"files" : os.listdir('downloads')}, f)
	except Exception as e:
		print(e)
		pass

client.run(TOKEN)
