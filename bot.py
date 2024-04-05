import os, json, asyncio, time
from base64 import urlsafe_b64encode
from hashlib import sha1
from urllib.parse import quote as urlencode

import yt_dlp
import discord

TOKEN = os.getenv('DISCORD_TOKEN')
PUBLIC_ADDRESS = os.getenv('PUBLIC_ADDRESS')
QUIET = os.getenv('QUIET')

if QUIET and QUIET.lower() == "true":
	QUIET = True
else:
	QUIET = False

IGNORED_MSGS = [
	": Downloading webpage",
	": Downloading android player API JSON",
	"Deleting original file",
	"(frag",
	"[youtube]",
	"[info] Downloading video thumbnail",
	"[info] Video Thumbnail"
]

if QUIET:
	IGNORED_MSGS = IGNORED_MSGS + [
		"[info] ",
		"[Merger] "
	]

with open('options.json') as options_file:
	ydl_opts = json.load(options_file)
	print(f'using options: {ydl_opts}', flush=True)

if not os.path.isfile('downloads/filelist.json'):
	with open('downloads/filelist.json', 'w') as f:
		json.dump({"files": []}, f, indent=4)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
	print(f'{client.user} is connected to the following guilds:', flush=True)
	for guild in client.guilds:
		print(f'{guild.name} (id:{guild.id})', flush=True)

class Logger(object):
	def __init__(self, prog_msg, msg_content, async_loop):
		self.output_msgs = []
		self.valid_msgs = [msg_content]
		self.prog_msg = prog_msg
		self.async_loop = async_loop
		self.time_since_last_edit = time.time()

	def push_to_output(self, msg):
		print(msg, flush=True)
		self.output_msgs.append(msg)

		append = True
		for line in IGNORED_MSGS:
			if line in msg:
				append = False
		if append:
			msg = msg.replace('_', '\\_')

			if "[download] " in msg:
				if "[download] " in self.valid_msgs[-1]:
					self.valid_msgs[-1] = msg
				else:
					self.valid_msgs.append(msg)
			else:
				self.valid_msgs.append(msg)

			if time.time() - self.time_since_last_edit > 2:
				self.time_since_last_edit = time.time()
				asyncio.run_coroutine_threadsafe(self.update_msg(), self.async_loop)

	async def update_msg(self, new_msg=False):
		if new_msg:
			self.valid_msgs.append(new_msg)
		await self.prog_msg.edit(content="\n".join(self.valid_msgs))

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

		if '!yt' == message.content[:3].lower():
			videourl = message.content[4:]

			msg_content = f'Attempting to DL: <{videourl}>'
			print(msg_content, flush=True)
			prog_msg = await message.channel.send(msg_content)

			loop = asyncio.get_running_loop()

			logger = Logger(prog_msg, msg_content, loop)
			opts = ydl_opts.copy()
			opts['logger'] = logger
			ydl_opts_str = str(ydl_opts)

			with yt_dlp.YoutubeDL(opts) as ydl:
				info = await loop.run_in_executor(None, lambda: ydl.extract_info(videourl, download=False))
				title = info['title']
				video_id = info['id']
				if QUIET:
					msg_content = f'Title: {title}\nDownloading...'.replace('_', '\\_')
				else:
					msg_content = f'Title: {title}\nOptions: {ydl_opts_str}\nDownloading...'.replace('_', '\\_')

				await logger.update_msg(msg_content)

				path = title + video_id
				video_string_hash = urlsafe_b64encode(sha1(path.encode('utf-8')).digest()).decode('utf-8')[:-1]
				path = 'downloads/' + video_string_hash + '/'
				opts['outtmpl']['default'] = opts['outtmpl']['default'].replace('downloads/', path, 1)
				os.makedirs(path, exist_ok=True)

			with yt_dlp.YoutubeDL(opts) as ydl:
				info = await loop.run_in_executor(None, lambda: ydl.extract_info(videourl, download=True))
				filename = await loop.run_in_executor(None, lambda: ydl.prepare_filename(info))

				await logger.update_msg("Download completed.")

				if PUBLIC_ADDRESS and PUBLIC_ADDRESS != 'YourPublicWebAddressHere':
					target = filename.replace('downloads/', '', 1)
					ddl_target = filename.replace('downloads/', 'ddl/', 1)
					
					public_filename = f"http://{PUBLIC_ADDRESS}/{urlencode(target)}"
					ddl_filename = f"http://{PUBLIC_ADDRESS}/{urlencode(ddl_target)}"
					
					await message.channel.send(f'[{title}]({public_filename}) ([download](<{ddl_filename}>))')
				else:
					public_filename = filename
					await message.channel.send(f'{public_filename}')

			output_info = {}
			output_info['folder'] = video_string_hash
			output_info['filename'] = filename.replace('downloads/', '')
			output_info['title'] = info['title']
			output_info['video_id'] = info['id']
			
			for line in logger.output_msgs:
				if 'Writing video thumbnail' in line:
					output_info['thumbnail_ext'] = line.split('.')[-1]
					break

			print(output_info, flush=True)
			with open('downloads/filelist.json', 'r+') as f:
				files_arr = json.load(f)
				files_arr["files"].append(output_info)
				f.seek(0)
				json.dump(files_arr, f, indent=4)
				f.truncate()
	except Exception as e:
		print('Error attempting to download video:', flush=True)
		print(e, flush=True)
		try:
			await message.channel.send(e)
		except Exception as e:
			print('Error attempting to send exception as a message:', flush=True)
			print(e, flush=True)
			pass
		pass

client.run(TOKEN)
