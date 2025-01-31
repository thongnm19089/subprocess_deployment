# filepath: /home/thongnm/prj/subprocess/subprocess_admin/subprocess_app/views.py
from django.http import HttpResponse
import paramiko
from dotenv import load_dotenv
import os
import logging
from django.http import JsonResponse
from django.shortcuts import render, redirect
from .models import Deployment, Server
from django.contrib import messages
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
import subprocess

from django.core.cache import cache

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import hmac
import hashlib
from django.core.cache import cache
from datetime import datetime

def store_git_log(payload, deployment_status=None, deployment_message=None):
    """Lưu log vào cache"""
    logs = cache.get('git_logs', [])
    log_entry = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'repository': payload.get('repository'),
        'ref': payload.get('ref'),
        'commits': payload.get('commits', []),
        'pusher': payload.get('pusher'),
        'deployment_status': deployment_status,
        'deployment_message': deployment_message
    }
    logs.insert(0, log_entry)  # Thêm log mới nhất lên đầu
    cache.set('git_logs', logs[:100]) 
@csrf_exempt
@require_POST
def git_webhook(request):
    """
    Xử lý webhook từ Git khi có push event
    URL: /git-webhook/
    """
    try:
        # Đọc payload từ webhook
        payload = json.loads(request.body)
        
        # Kiểm tra xem event có phải là push vào master không
        if is_master_push(payload):
            # Lấy thông tin repository từ payload
            repo_name = get_repo_name(payload)
            # Tìm deployment tương ứng với repository
            try:
                deployment = Deployment.objects.get(project_name=repo_name)
                
                # Thực hiện deploy
                response = deploy(request, deployment.id)
                response_data = json.loads(response.content.decode())

                store_git_log(
                    payload,
                    deployment_status='success',
                    deployment_message=response_data.get('message')
                )
                return JsonResponse({
                    'status': 'success',
                    'message': f'Deployment triggered for {repo_name}'
                })
                
            except Deployment.DoesNotExist:
                store_git_log(
                    payload,
                    deployment_status='error',
                    deployment_message=f'No deployment configuration found for {repo_name}'
                )
                return JsonResponse({
                    'status': 'error',
                    'message': f'No deployment configuration found for {repo_name}'
                }, status=404)
        store_git_log(
            payload,
            deployment_status='ignored',
            deployment_message='Not a master branch push event'
        )
        return JsonResponse({
            'status': 'ignored',
            'message': 'Not a master branch push event'
        })
        
    except Exception as e:
        store_git_log(
            payload if 'payload' in locals() else {},
            deployment_status='error',
            deployment_message=str(e)
        )
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

def is_master_push(payload):
    """
    Kiểm tra xem webhook event có phải là push vào master không
    """
    try:
        # GitHub
        if 'ref' in payload:
            return payload['ref'] == 'refs/heads/main'
        
        # GitLab
        if 'ref' in payload and 'default_branch' in payload['project']:
            return payload['ref'] == f"refs/heads/{payload['project']['default_branch']}"
        
        return False
    except:
        return False

def get_repo_name(payload):
    """
    Lấy tên repository từ payload
    """
    try:
        # GitHub
        if 'repository' in payload and 'name' in payload['repository']:
            return payload['repository']['name']
        
        # GitLab
        if 'project' in payload and 'name' in payload['project']:
            return payload['project']['name']
        
        raise ValueError("Repository name not found in payload")
    except Exception as e:
        raise ValueError(f"Failed to extract repository name: {str(e)}")

def verify_github_signature(request):
    """
    Xác thực webhook signature từ GitHub
    """
    signature = request.headers.get('X-Hub-Signature-256')
    if not signature:
        return False

    secret = os.getenv('GITHUB_WEBHOOK_SECRET', '').encode()
    expected_signature = 'sha256=' + hmac.new(
        secret,
        request.body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)



def terminal_view(request):
    return render(request, 'terminal.html')

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
            # Stash local changes trước khi pull
            stash_output, stash_error = execute_ssh_command(
                ssh, 
                f'cd {deployment.project_path} && git stash'
            )
            messages.append("Local changes stashed")
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
        
def view_git_logs(request):
    """View để hiển thị logs"""
    git_logs = cache.get('git_logs', [])
    return render(request, 'git_logs.html', {'git_logs': git_logs})