# filepath: /home/thongnm/prj/subprocess/subprocess_admin/subprocess_app/views.py
from django.http import HttpResponse
import paramiko
from dotenv import load_dotenv
import os
import logging
from django.http import JsonResponse
from django.shortcuts import render, redirect ,get_object_or_404
from .models import Deployment, Server ,GitLog
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

def store_git_log(deployment, payload, deployment_status=None, deployment_message=None):
    """Lưu log vào database"""
    try:
        # Lấy thông tin commit cuối cùng
        latest_commit = payload.get('commits', [{}])[-1] if payload.get('commits') else {}
        
        # Chuẩn bị thông tin files thay đổi
        files_changed = {
            'added': latest_commit.get('added', []),
            'modified': latest_commit.get('modified', []),
            'removed': latest_commit.get('removed', [])
        }

        # Tạo git log mới
        git_log = GitLog.objects.create(
            deployment=deployment,
            commit_id=latest_commit.get('id'),
            commit_message=latest_commit.get('message'),
            author_name=latest_commit.get('author', {}).get('name'),
            author_email=latest_commit.get('author', {}).get('email'),
            branch=payload.get('ref'),
            status=deployment_status,
            deployment_message=deployment_message,
            files_changed=files_changed
        )
        return git_log
    except Exception as e:
        logger.error(f"Failed to store git log: {str(e)}")
        return None
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
                    deployment=deployment,
                    payload=payload,
                    deployment_status='success',
                    deployment_message=response_data.get('message')
                )
                return JsonResponse({
                    'status': 'success',
                    'message': f'Deployment triggered for {repo_name}'
                })
                
            except Deployment.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': f'No deployment configuration found for {repo_name}'
                }, status=404)
        
       
        return JsonResponse({
            'status': 'ignored',
            'message': 'Not a master branch push event'
        })
        
    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}")
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
    """
    Thực thi lệnh SSH và trả về output
    """
    try:
        if need_sudo:
            if not password:
                raise ValueError("Password is required for sudo command.")
            command = f"sudo -S {command}"

        # Thực thi lệnh
        stdin, stdout, stderr = ssh.exec_command(command)
        
        # Gửi password nếu cần sudo
        if need_sudo and password:
            stdin.write(password + '\n')
            stdin.flush()

        # Đọc output và error
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')

        # Lấy exit status
        exit_status = stdout.channel.recv_exit_status()

        # Log để debug
        logger.info(f"Command: {command}")
        logger.info(f"Exit status: {exit_status}")
        logger.info(f"Output: {output}")
        logger.info(f"Error: {error}")

        # Với git pull, stderr có thể chứa thông tin về pull progress
        # nên chỉ raise exception nếu exit status không phải 0
        if exit_status != 0:
            raise Exception(f"Command failed with status {exit_status}: {error}")

        return output, error

    except Exception as e:
        logger.error(f"SSH command execution failed: {str(e)}")
        raise


def deploy(request, id):
    deployment = Deployment.objects.get(id=id)
    server = deployment.server
    messages = []
    venv_path = os.path.join(deployment.project_path, 'venv')  # đường dẫn đến virtual environment

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

            # Git Pull với full command
            git_command = f'''
                cd {deployment.project_path} && \
                git fetch origin && \
                git reset --hard origin/main
            '''
            
            git_output, git_error = execute_ssh_command(ssh, git_command)
            messages.append(f"Git pull successful:\n{git_output}")


            # Install requirements trong virtual environment
            pip_command = f'''
                source {venv_path}/bin/activate && \
                cd {deployment.project_path} && \
                pip install -r requirements.txt
            '''
            pip_output, pip_error = execute_ssh_command(ssh, pip_command)
            if 'Successfully installed' in pip_output or 'Requirement already satisfied' in pip_output:
                messages.append("Requirements installed successfully")
            else:
                raise Exception(f"Failed to install requirements: {pip_error}")

            # Chạy migrations
            migrate_command = f'''
                source {venv_path}/bin/activate && \
                cd {deployment.project_path} && \
                python manage.py migrate
            '''
            migrate_output, migrate_error = execute_ssh_command(ssh, migrate_command)
            if 'error' in migrate_error.lower():
                raise Exception(f"Migration failed: {migrate_error}")
            messages.append("Database migrations completed successfully")

            # Test runserver
            test_command = f'''
                source {venv_path}/bin/activate && \
                cd {deployment.project_path} && \
                python manage.py check --deploy
            '''
            test_output, test_error = execute_ssh_command(ssh, test_command)

            # Kiểm tra kết quả check --deploy
            if test_error:
                # Kiểm tra xem có phải chỉ là warnings không
                if "System check identified some issues:" in test_error and "ERROR:" not in test_error:
                    # Chỉ có warnings, vẫn cho phép tiếp tục
                    messages.append("Django check completed with warnings")
                    logger.warning(f"Django check warnings: {test_error}")
                else:
                    # Có lỗi nghiêm trọng, dừng deployment
                    logger.error(f"Django check failed with errors: {test_error}")
                    raise Exception(f"Django check failed with errors. Deployment aborted.")
            else:
                messages.append("Django check passed successfully")


            # Service Restart
            service_output, service_error = execute_ssh_command(
                ssh, 
                f'systemctl restart {deployment.service_name}',
                need_sudo=True,
                password=server.password
            )
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
        
def view_git_logs(request, deployment_id=None):
    """View để hiển thị logs"""
    deployment = get_object_or_404(Deployment, id=deployment_id)
    git_logs = GitLog.objects.filter(deployment=deployment)
    template_name = 'git_logs.html'
   
    
    response = render(request, template_name, {
        'git_logs': git_logs,
        'deployment': deployment if deployment_id else None
    })
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response