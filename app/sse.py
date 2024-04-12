import asyncio, json
import uvicorn
import aiosqlite
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 6000

updated = {'last_id': 0, 'data': None}

async def handle_client(reader, writer):
	try:
		request = (await reader.read(1024)).decode('utf8')
		request = json.loads(request)
		if request['id'] > 0:
			updated['last_id'] = request['id']
			updated['data'] = request['data']
	except Exception as e:
		print(f'Failed request:')
		print(e)

async def run_server():
	server = await asyncio.start_server(handle_client, SERVER_HOST, SERVER_PORT)
	async with server:
		await server.serve_forever()

async def fetch_rows(min_row=0, max_row=None, max_count=100):
	if max_count > 100:
		max_count = 100

	async with aiosqlite.connect("downloads.db") as db:
		if min_row == 0 and not max_row:
			output = await db.execute(f'''
				SELECT * FROM downloads
				ORDER BY rowid DESC
				LIMIT {max_count};
			''')
		else:
			if not max_row:
				max_row = await db.execute('''
					SELECT MAX(rowid) FROM downloads;
				''')
				max_row = await max_row.fetchone()
				max_row = max_row[0]
				if not max_row:
					max_row = 0

			output = await db.execute(f'''
				SELECT * FROM downloads
				WHERE rowid BETWEEN {min_row} AND {max_row}
				ORDER BY rowid DESC
				LIMIT {max_count};
			''')

		output = await output.fetchall()

	return output

async def sse(request):
	async def msg_socket():
		try:
			last_id = updated['last_id']
			while True:
				await asyncio.sleep(1)
				if last_id != updated['last_id']:
					last_id = updated['last_id']
					yield dict(data=json.dumps(updated))
		except asyncio.CancelledError:
			pass
	return EventSourceResponse(msg_socket(), send_timeout=180)

async def db(request):
	min_row = 0
	max_row = None
	max_count = 10
	res = []
		
	try:
		params = request.query_params.keys()
		if 'min_row' in params:
			min_row = int(request.query_params['min_row'])
		if 'max_row' in params:
			max_row = int(request.query_params['max_row'])
		if 'max_count' in params:
			max_count = int(request.query_params['max_count'])

		res = await fetch_rows(min_row=min_row, max_row=max_row, max_count=max_count)
	except Exception as e:
		print('Failed DB request:', e)

	return JSONResponse({
		"res": res
	})

async def main():
	loop = asyncio.get_event_loop()

	app = Starlette(debug=True, routes=[
		Route('/', endpoint=sse),
		Route('/db', endpoint=db)
	])
	config = uvicorn.Config(app=app, loop=loop, host='0.0.0.0', port=7000)
	server = uvicorn.Server(config)

	uvicorn_starlette = loop.create_task(server.serve())
	socketserver = loop.create_task(run_server())

	await asyncio.wait([socketserver, uvicorn_starlette])

asyncio.run(main())
