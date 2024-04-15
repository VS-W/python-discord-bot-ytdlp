import asyncio, json, os, time
from base64 import urlsafe_b64encode
from hashlib import sha1
from socket import socket
from urllib.parse import quote
from re import sub

import aiosqlite
import discord
import emoji
import yt_dlp

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
	print(f'using options: {ydl_opts}')

if not os.path.isfile('downloads/filelist.json'):
	with open('downloads/filelist.json', 'w') as f:
		json.dump({"files": []}, f, indent=4)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

class Logger(object):
	def __init__(self, prog_msg, msg_content, async_loop):
		self.output_msgs = []
		self.valid_msgs = [msg_content]
		self.prog_msg = prog_msg
		self.async_loop = async_loop
		self.time_since_last_edit = time.time()

	def push_to_output(self, msg):
		print(msg)
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
		
def send_sse(message):
	client_socket = socket()
	client_socket.connect(('0.0.0.0', 6000))

	print(f'>>> Sending: {message}')
	client_socket.send(message.encode())

	client_socket.close()

async def setup_db():
	async with aiosqlite.connect("downloads.db") as db:
		await db.execute('''
			CREATE TABLE IF NOT EXISTS downloads (
				id integer primary key,
				folder TEXT unique,
				filename TEXT,
				title TEXT,
				video_id TEXT,
				thumbnail_ext TEXT
			)
		''')

async def insert_row(video_info_obj):
	async with aiosqlite.connect("downloads.db") as db:
		cursor = await db.execute(f'''
			INSERT OR IGNORE INTO downloads (
				folder,
				filename,
				title,
				video_id,
				thumbnail_ext
			)
			VALUES (?, ?, ?, ?, ?)
		''', [video_info_obj["folder"], video_info_obj["filename"], video_info_obj["title"], video_info_obj["video_id"], video_info_obj["thumbnail_ext"]])

		await db.commit()

		return {
			"data": video_info_obj,
			"id": cursor.lastrowid
		}

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

		if '!yt' == message.content[:3].lower():
			videourl = message.content[4:]

			msg_content = f'Attempting to DL: <{videourl}>'
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
				filename = await loop.run_in_executor(None, lambda: ydl.prepare_filename(info))
				opts['outtmpl']['default'] = path + sub(r'[^\w.-]', '_', filename)
				os.makedirs(path, exist_ok=True)

			with yt_dlp.YoutubeDL(opts) as ydl:
				info = await loop.run_in_executor(None, lambda: ydl.extract_info(videourl, download=True))
				filename = await loop.run_in_executor(None, lambda: ydl.prepare_filename(info))

				await logger.update_msg("Download completed.")

				if PUBLIC_ADDRESS and PUBLIC_ADDRESS != 'YourPublicWebAddressHere':
					target = filename.replace('downloads/', '', 1)
					ddl_target = filename.replace('downloads/', 'ddl/', 1)

					public_filename = f'http://{PUBLIC_ADDRESS}/{quote(target)}'
					ddl_filename = f'http://{PUBLIC_ADDRESS}/{quote(ddl_target)}'

					await message.channel.send(f'[{emoji.demojize(title, delimiters=("[", "]"))}]({public_filename}) ([download](<{ddl_filename}>))')
				else:
					public_filename = filename
					await message.channel.send(f'{public_filename}')

			output_info = {}
			output_info['folder'] = video_string_hash
			output_info['filename'] = filename.replace('downloads/', '', 1)
			output_info['title'] = info['title']
			output_info['video_id'] = info['id']
			output_info['thumbnail_ext'] = ''
			output_info['time'] = time.time()
			
			for line in logger.output_msgs:
				if 'Writing video thumbnail' in line:
					output_info['thumbnail_ext'] = line.split('.')[-1]
					break

			print(output_info)
			with open('downloads/' + video_string_hash + '/info.json', 'w') as f:
				json.dump(output_info, f, indent=4)
			
			inserted_row = await insert_row(output_info)
			send_sse(json.dumps(inserted_row))
	except Exception as e:
		print('Error attempting to download video:')
		print(e)
		try:
			await message.channel.send(e)
		except Exception as e:
			print('Error attempting to send exception as a message:')
			print(e)
			pass
		pass

async def main():
	await setup_db()

	loop = asyncio.get_event_loop()
	discordbot = loop.create_task(client.start(TOKEN))
	await asyncio.wait([discordbot])

asyncio.run(main())
