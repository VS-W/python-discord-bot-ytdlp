import os, json, asyncio
from base64 import urlsafe_b64encode
from hashlib import sha256
from urllib.parse import quote as urlencode

import yt_dlp
import discord

TOKEN = os.getenv('DISCORD_TOKEN')
PUBLIC_ADDRESS = os.getenv('PUBLIC_ADDRESS')

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
    def __init__(self):
        self.output_msgs = []

    def push_to_output(self, msg):
        print(msg, flush=True)
        ignored_msgs = [
            ": Downloading webpage",
            ": Downloading android player API JSON",
            "/s ETA ",
            "Deleting original file",
            "(frag",
            "[youtube]"
        ]
        append = True
        for line in ignored_msgs:
            if line in msg:
                append = False
        if append:
            msg = msg.replace('_', '\_')
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
            videourl = message.content.split('!yt ')[1]

            prog_msg_str = f'Attempting to DL: <{videourl}>'
            print(prog_msg_str, flush=True)
            prog_msg = await message.channel.send(prog_msg_str)

            logger = Logger()

            opts = ydl_opts.copy()
            opts['logger'] = logger
            ydl_opts_str = str(ydl_opts).replace('_', '\_')

            loop = asyncio.get_running_loop()
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(videourl, download=False))
                title = info['title']
                video_id = info['id']
                msg_content = f"Attempting to DL: <{videourl}>\nTitle: {title}\nOptions: {ydl_opts_str}\nDownloading..."
                await prog_msg.edit(content=msg_content)
                path = title + video_id
                video_string_hash = urlsafe_b64encode(sha256(path.encode('utf-8')).digest()).decode('utf-8')
                path = 'downloads/' + video_string_hash + '/'
                opts['outtmpl']['default'] = opts['outtmpl']['default'].replace('downloads/', path, 1)
                os.makedirs(path, exist_ok=True)

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(videourl, download=True))
                log = '\n'.join(logger.output_msgs)
                filename = await loop.run_in_executor(None, lambda: ydl.prepare_filename(info))
                msg_content += f'\n{log}\nOutput:\n{filename}'
                await prog_msg.edit(content=msg_content, suppress=True)
                if PUBLIC_ADDRESS and PUBLIC_ADDRESS != 'YourPublicWebAddressHere':
                    target = filename.replace('downloads/', '', 1)
                    ddl_target = filename.replace('downloads/', 'ddl/', 1)
                    
                    public_filename = f"http://{PUBLIC_ADDRESS}/{urlencode(target)}"
                    ddl_filename = f"http://{PUBLIC_ADDRESS}/{urlencode(ddl_target)}"
                    
                    res_msg = await message.channel.send(f'[{title}]({public_filename}) ([download](<{ddl_filename}>))')
                else:
                    public_filename = filename
                    res_msg = await message.channel.send(f'{public_filename}')

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
        print(e, flush=True)
        pass

client.run(TOKEN)
