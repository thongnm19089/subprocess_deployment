import json
import os
import subprocess
from channels.generic.websocket import AsyncWebsocketConsumer

class TerminalConsumer(AsyncWebsocketConsumer):
    current_directory = os.getcwd()

    async def connect(self):
        await self.accept()
        # Gửi thông tin thư mục hiện tại khi kết nối
        await self.send(text_data=json.dumps({
            'output': f'{self.current_directory}$ '
        }))

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        data = json.loads(text_data)
        command = data['command']

        if command.strip() == '':
            await self.send(text_data=json.dumps({
                'output': f'{self.current_directory}$ '
            }))
            return

        if command.startswith('cd '):
            try:
                new_dir = command[3:].strip()
                if new_dir.startswith('~'):
                    new_dir = os.path.expanduser(new_dir)
                os.chdir(os.path.join(self.current_directory, new_dir))
                self.current_directory = os.getcwd()
                output = f'{self.current_directory}$ '
            except FileNotFoundError:
                output = f"cd: {command[3:]}: No such file or directory\n{self.current_directory}$ "
        else:
            try:
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=self.current_directory
                )
                stdout, stderr = process.communicate()
                
                output = ''
                if stdout:
                    output += stdout.decode('utf-8')
                if stderr:
                    output += stderr.decode('utf-8')
                output += f'\n{self.current_directory}$ '
            except Exception as e:
                output = f"Error executing command: {str(e)}\n{self.current_directory}$ "

        await self.send(text_data=json.dumps({
            'output': output
        }))