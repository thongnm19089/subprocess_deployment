# filepath: /home/thongnm/prj/subprocess/subprocess_admin/subprocess_app/views.py
from django.http import HttpResponse
from django.shortcuts import render
import paramiko
from dotenv import load_dotenv
import os
import logging
from django.http import JsonResponse
from django.shortcuts import render, redirect
from .models import Deployment, Server
from django.contrib import messages# Load environment variables from .env file
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
import subprocess
def git_pull(request):
    ssh_host = os.getenv('SSH_HOST')
    ssh_port = int(os.getenv('SSH_PORT'))
    ssh_user = os.getenv('SSH_USER')
    ssh_password = os.getenv('SSH_PASSWORD')
    git_repo_path = os.getenv('GIT_REPO_PATH')
    restart_command = os.getenv('RESTART_COMMAND')

    try:
        # Create SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ssh_host, port=ssh_port, username=ssh_user, password=ssh_password)
        logger.info("Connected to server successfully.")
        connect_message = "Connected to server successfully."

        # Execute git pull command
        logger.info("Running git pull...")
        stdin, stdout, stderr = ssh.exec_command(f'cd {git_repo_path} && git status')
        git_output = stdout.read().decode('utf-8')
        git_error = stderr.read().decode('utf-8')

        if git_error:
            ssh.close()
            logger.error(f"Git pull failed: {git_error}")
            return JsonResponse({'status': 'error', 'message': f"{connect_message}\nGit pull failed:\n{git_error}"})

        # Log success of git pull
        logger.info("Git pull successful.")
        git_message = f"Git pull successful:\n{git_output}"

        # Restart service
        # logger.info("Restarting service...")
        stdin, stdout, stderr = ssh.exec_command(restart_command)
        restart_output = stdout.read().decode('utf-8')
        restart_error = stderr.read().decode('utf-8')

        ssh.close()

        if restart_error:
            logger.error(f"Service restart failed: {restart_error}")
            return JsonResponse({'status': 'error', 'message': f"{connect_message}\n{git_message}\nService restart failed:\n{restart_error}"})

        # Log success of service restart
        # logger.info("Service restart successful.")
        restart_message = f"Service restart successful:\n{restart_output}"

        return JsonResponse({'status': 'success', 'message': f"{connect_message}\n{git_message}\n{restart_message}"})
    except Exception as e:
        logger.error(f"SSH connection failed: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f"SSH connection failed:\n{str(e)}"})

def home(request):
    return render(request, 'home.html')
def get_deployment(request, id):
    deployment = Deployment.objects.get(id=id)
    return JsonResponse({
        'id': deployment.id,
        'project_name': deployment.project_name,
        'project_path': deployment.project_path,
        'service_name': deployment.service_name,
        'status': deployment.status,
        'server': deployment.server.id if deployment.server else None,
    })

def update_deployment(request, id):
    if request.method == 'POST':
        deployment = Deployment.objects.get(id=id)
        deployment.project_name = request.POST.get('project_name')
        deployment.project_path = request.POST.get('project_path')
        deployment.service_name = request.POST.get('service_name')
        deployment.status = request.POST.get('status')
        server_id = request.POST.get('server')
        if server_id and server_id != 'none':
            try:
                server = Server.objects.get(id=server_id)
                deployment.server = server
            except Server.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Server not found'
                })
        else:
            deployment.server = None

        deployment.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'})
def manage(request):
    if request.method == 'POST':
        project_name = request.POST.get('project_name')
        project_path = request.POST.get('project_path')
        service_name = request.POST.get('service_name')
        status = request.POST.get('status')
        server_id = request.POST.get('server')

        if server_id:
            try:
                server = Server.objects.get(id=server_id)
            except Server.DoesNotExist:
                server = None
        else:
            server = None


        deployment = Deployment(
            project_name=project_name,
            project_path=project_path,
            service_name=service_name,
            status=status,
            server=server,
        )
        deployment.save()
        messages.success(request, 'Deployment added successfully!')
        return redirect('manage')
    
    servers = Server.objects.all()
    deployments = Deployment.objects.all()
    return render(request, 'management.html', {'servers': servers, 'deployments': deployments})

def delete_deployment(request, id):
    if request.method == 'POST':
        try:
            deployment = Deployment.objects.get(id=id)
            deployment.delete()
            return JsonResponse({'status': 'success'})
        except Deployment.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Deployment not found'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

def execute_ssh_command(ssh, command, need_sudo=False, password=None):
    if need_sudo:
        if not password:
            raise ValueError("Password is required for sudo command.")
        command = f"sudo -S {command}"

    # Thực thi lệnh qua SSH
    stdin, stdout, stderr = ssh.exec_command(command)

    # Gửi mật khẩu nếu cần sudo
    if need_sudo and password:
        stdin.write(password + '\n')
        stdin.flush()

    # Đọc đầu ra từ stdout và stderr
    output = ""
    error = ""

    # Kiểm tra luồng dữ liệu để đảm bảo xử lý đúng thời điểm
    while not stdout.channel.exit_status_ready():
        if stdout.channel.recv_ready():
            output += stdout.read(1024).decode('utf-8')
        if stderr.channel.recv_stderr_ready():
            error += stderr.read(1024).decode('utf-8')

        # Phát hiện yêu cầu mật khẩu từ sudo và gửi lại
        if "[sudo]" in error and "password" in error:
            stdin.write(password + '\n')
            stdin.flush()
            error = ""  # Xóa thông báo cũ sau khi gửi mật khẩu

    # Đọc toàn bộ phần còn lại
    output += stdout.read().decode('utf-8')
    error += stderr.read().decode('utf-8')

    # Trả về đầu ra và lỗi
    return output, error


def deploy(request, id):
    deployment = Deployment.objects.get(id=id)
    server = deployment.server
    messages = []

    if server:
        try:
            # SSH Connection
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                server.server_ip, 
                port=22, 
                username=server.user, 
                password=server.password
            )
            logger.info("Connected to server successfully")
            messages.append("Connected to server successfully")

            # Git Pull
            git_output, git_error = execute_ssh_command(
                ssh, 
                f'cd {deployment.project_path} && git pull'
            )
            if git_error:
                raise Exception(f"Git pull failed: {git_error}")
            messages.append(f"Git pull successful:\n{git_output}")

            # Service Restart
            service_output, service_error = execute_ssh_command(
                ssh, 
                f'systemctl restart {deployment.service_name}',
                need_sudo=True,
                password=server.password
            )
            if service_error:
                raise Exception(f"Service restart failed: {service_error}")
            messages.append(f"Service restart initiated")

            # Check Service Status
            status_output, status_error = execute_ssh_command(
                ssh, 
                f'systemctl status {deployment.service_name}',
                need_sudo=True,
                password=server.password
            )
            if 'active (running)' not in status_output:
                raise Exception("Service not running properly after restart")
            messages.append(f"Service {deployment.service_name} running successfully")

        except Exception as e:
            logger.error(f"Deployment failed: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f"{messages}\nError: {str(e)}"
            })
        finally:
            if 'ssh' in locals():
                ssh.close()

        return JsonResponse({
            'status': 'success',
            'message': '\n'.join(messages)
        })
    else:
        # Local deployment
        try:
            subprocess.run(['git', 'pull'], cwd=deployment.project_path, check=True)
            messages.append("Local git pull successful")
            
            subprocess.run(['systemctl', 'restart', deployment.service_name], check=True)
            messages.append(f"Local service {deployment.service_name} restarted")
            
            return JsonResponse({
                'status': 'success',
                'message': '\n'.join(messages)
            })
        except subprocess.CalledProcessError as e:
            return JsonResponse({
                'status': 'error',
                'message': f"Local deployment failed: {str(e)}"
            })