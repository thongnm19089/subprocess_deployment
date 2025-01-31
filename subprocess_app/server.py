import asyncio
import websockets
import os
import json

current_directory = os.getcwd()

async def terminal_handler(websocket, path):
    global current_directory
    while True:
        message = await websocket.recv()
        data = json.loads(message)
        command = data['command']

        if command.startswith('cd '):
            try:
                os.chdir(command[3:])
                current_directory = os.getcwd()
                output = f"Changed directory to {current_directory}"
            except FileNotFoundError:
                output = "Directory not found"
        else:
            process = os.popen(command)
            output = process.read()
            process.close()

        await websocket.send(json.dumps({'output': output}))

start_server = websockets.serve(terminal_handler, "localhost", 8001)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever() 