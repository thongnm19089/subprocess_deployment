import json
import os
import subprocess
from channels.generic.websocket import AsyncWebsocketConsumer
import paramiko  # Thêm thư viện paramiko để hỗ trợ SSH
import io   
import asyncio
from .models import Deployment

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

from channels.db import database_sync_to_async
import logging

logger = logging.getLogger(__name__)
class TerminalConsumerID(AsyncWebsocketConsumer):
    async def handle_shell_command(self, command):
        try:
            # Nếu đang sử dụng SSH
            if hasattr(self, 'shell'):
                self.shell.send(command + '\n')
                await asyncio.sleep(0.5)
                output = ''
                while self.shell.recv_ready():
                    output += self.shell.recv(1024).decode('utf-8', errors='replace')
                return output

            # Nếu sử dụng local terminal
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.current_directory,
                env={"TERM": "xterm-256color"}  # Thêm biến môi trường TERM
            )
            
            stdout, stderr = process.communicate(timeout=30)
            
            output = ''
            if stdout:
                # Xử lý đặc biệt cho output có chứa escape sequences
                output += stdout.decode('utf-8', errors='replace')
            if stderr:
                output += stderr.decode('utf-8', errors='replace')
            
            # Loại bỏ các ký tự điều khiển ANSI không cần thiết
            output = self.clean_ansi_escape_sequences(output)
            
            if output:
                output = output.rstrip('\n') + '\n'
            output += f'{self.current_directory}$ '
            return output
                
        except subprocess.TimeoutExpired:
            process.kill()
            return f"Command timed out after 30 seconds\n{self.current_directory}$ "
        except Exception as e:
            logger.error(f"Shell command error: {str(e)}")
            return f"Error executing command: {str(e)}\n{self.current_directory}$ "

    def clean_ansi_escape_sequences(self, text):
        """
        Loại bỏ các escape sequences không cần thiết nhưng giữ lại màu sắc cơ bản
        """
        import re
        # Giữ lại các escape sequences cho màu sắc cơ bản
        # Loại bỏ các escape sequences phức tạp khác
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    @database_sync_to_async
    def get_deployment(self):
        """
        Lấy deployment từ database một cách bất đồng bộ
        """
        try:
            deployment = Deployment.objects.select_related('server').get(id=self.deployment_id)
            return deployment
        except Deployment.DoesNotExist:
            return None
    async def connect(self):
        try:
            self.deployment_id = int(self.scope['url_route']['kwargs']['deployment_id'])
            
            # Lấy deployment từ database
            self.deployment = await self.get_deployment()
            if not self.deployment:
                await self.accept()
                await self.send(text_data=json.dumps({
                    'output': f'Error: Deployment ID {self.deployment_id} not found\n$ '
                }))
                return

            self.current_directory = self.deployment.project_path
            
            # Kiểm tra xem deployment có server không
            if self.deployment.server:
                # Khởi tạo SSH client
                self.ssh = paramiko.SSHClient()
                self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                try:
                    self.ssh.connect(
                        self.deployment.server.server_ip,
                        username=self.deployment.server.user,
                        password=self.deployment.server.password
                    )
                    # Tạo SSH shell
                    self.shell = self.ssh.invoke_shell()
                    # Đổi thư mục sang project path
                    self.shell.send(f'cd {self.current_directory}\n')
                    # Đợi output
                    await asyncio.sleep(1)
                    output = self.shell.recv(1024).decode()
                    
                    await self.accept()
                    await self.send(text_data=json.dumps({
                        'output': f'Connected to {self.deployment.server.server_name} via SSH\n{output}'
                    }))
                    return
                except Exception as e:
                    logger.error(f"SSH connection error: {str(e)}")
                    await self.accept()
                    await self.send(text_data=json.dumps({
                        'output': f'SSH connection failed: {str(e)}\n$ '
                    }))
                    return
            
            # Nếu không có server hoặc server là None, sử dụng local terminal
            if not os.path.exists(self.current_directory):
                await self.accept()
                await self.send(text_data=json.dumps({
                    'output': f'Error: Directory not found: {self.current_directory}\n$ '
                }))
                return
            
            os.chdir(self.current_directory)
            await self.accept()
            await self.send(text_data=json.dumps({
                'output': f'Connected to local terminal...\nConnected to {self.deployment.project_name}\n{self.current_directory}$ '
            }))
            
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            await self.accept()
            await self.send(text_data=json.dumps({
                'output': f'Error: {str(e)}\n$ '
            }))

    async def disconnect(self, close_code):
        # Đóng kết nối SSH nếu có
        if hasattr(self, 'ssh'):
            self.ssh.close()
        logger.info(f"Disconnected from deployment: {self.deployment_id if hasattr(self, 'deployment_id') else 'unknown'}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            command = data.get('command', '').strip()

            if not command:
                await self.send(text_data=json.dumps({
                    'output': f'{self.current_directory}$ '
                }))
                return

            # Nếu đang sử dụng SSH
            if hasattr(self, 'shell'):
                # Gửi lệnh qua SSH
                self.shell.send(command + '\n')
                # Đợi output
                await asyncio.sleep(0.5)
                output = ''
                while self.shell.recv_ready():
                    output += self.shell.recv(1024).decode()
                await self.send(text_data=json.dumps({
                    'output': output
                }))
                return

            # Nếu sử dụng local terminal
            if command.startswith('cd '):
                output = await self.handle_cd_command(command)
            else:
                output = await self.handle_shell_command(command)

            await self.send(text_data=json.dumps({
                'output': output
            }))
            
        except Exception as e:
            logger.error(f"Error processing command: {str(e)}")
            await self.send(text_data=json.dumps({
                'output': f"Error: {str(e)}\n{self.current_directory}$ "
            }))