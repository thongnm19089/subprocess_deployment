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
import requests
from django.urls import reverse

from django.core.cache import cache

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import hmac
import hashlib
from django.core.cache import cache
from datetime import datetime

def server_management(request):
    servers = Server.objects.all().order_by('-created_at')
    return render(request, 'server_management.html', {'servers': servers})

def add_server(request):
    if request.method == 'POST':
        try:
            server_name = request.POST.get('server_name')
            server_ip = request.POST.get('server_ip')
            user = request.POST.get('user')
            password = request.POST.get('password')

            # Kiểm tra xem server đã tồn tại chưa
            if Server.objects.filter(server_ip=server_ip).exists():
                return JsonResponse({
                    'status': 'error',
                    'message': 'Server with this IP already exists'
                })

            server = Server.objects.create(
                server_name=server_name,
                server_ip=server_ip,
                user=user,
                password=password
            )

            return JsonResponse({
                'status': 'success',
                'message': 'Server added successfully'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })

def get_server(request, server_id):
    try:
        server = Server.objects.get(id=server_id)
        return JsonResponse({
            'server_name': server.server_name,
            'server_ip': server.server_ip,
            'user': server.user,
        })
    except Server.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Server not found'
        })

def update_server(request, server_id):
    if request.method == 'POST':
        try:
            server = Server.objects.get(id=server_id)
            
            server.server_name = request.POST.get('server_name')
            server.server_ip = request.POST.get('server_ip')
            server.user = request.POST.get('user')
            
            # Chỉ cập nhật password nếu có nhập mới
            new_password = request.POST.get('password')
            if new_password:
                server.password = new_password

            # Kiểm tra xem IP mới có trùng với server khác không
            if Server.objects.exclude(id=server_id).filter(server_ip=server.server_ip).exists():
                return JsonResponse({
                    'status': 'error',
                    'message': 'Another server with this IP already exists'
                })

            server.save()
            return JsonResponse({
                'status': 'success',
                'message': 'Server updated successfully'
            })
        except Server.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Server not found'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })

@csrf_exempt
def delete_server(request, server_id):
    if request.method == 'POST':
        try:
            server = Server.objects.get(id=server_id)
            # Kiểm tra xem server có đang được sử dụng bởi deployment nào không
            if server.deployment_set.exists():
                return JsonResponse({
                    'status': 'error',
                    'message': 'Cannot delete server as it is being used by deployments'
                })
            
            server.delete()
            return JsonResponse({
                'status': 'success',
                'message': 'Server deleted successfully'
            })
        except Server.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Server not found'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
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
def git_webhook1(request):
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
        'server': deployment.server.id if deployment.server else None,
    })

def update_deployment(request, id):
    if request.method == 'POST':
        deployment = Deployment.objects.get(id=id)
        deployment.project_name = request.POST.get('project_name')
        deployment.project_path = request.POST.get('project_path')
        deployment.service_name = request.POST.get('service_name')
        
        # Xử lý password mới nếu được cung cấp
        new_password = request.POST.get('deploy_password')
        if new_password:  # Chỉ cập nhật password nếu có nhập mới
            deployment.pass_deploy = new_password
        
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
        server_id = request.POST.get('server')
        deploy_password = request.POST.get('deploy_password')  # Lấy password từ form

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
            server=server,
            pass_deploy=deploy_password  # Password sẽ tự động được mã hóa khi save

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

    # if deployment.pass_deploy:
    #     deploy_password = request.POST.get('deploy_password')
    #     if not deploy_password:
    #         return JsonResponse({
    #             'status': 'error',
    #             'message': 'Deploy password is required'
    #         }, status=403)
        
    #     if not deployment.check_deploy_password(deploy_password):
    #         return JsonResponse({
    #             'status': 'error',
    #             'message': 'Invalid deploy password'
    #         }, status=403)

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
                    warning_message = "Django check completed with warnings:\n" + test_error
                    messages.append(warning_message)
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



import requests  # Add this import
from django.urls import reverse  # Add this import

GITHUB_CLIENT_ID = 'Iv23lixmPB4dslLyaMht'
GITHUB_CLIENT_SECRET = '919c27e6627b606b6dc9683ada2f922ac67bbde1'
# Webhook secret phải là một chuỗi bí mật, không phải URL
GITHUB_WEBHOOK_SECRET = 'Vtca@1234'  
# URL callback nên là constant riêng
GITHUB_CALLBACK_URL = 'http://b0f6-123-24-142-95.ngrok-free.app/github/callback/'
def select_repository(request):
    token = request.session.get('github_token')
    deployment_id = request.session.get('deployment_id')

    if not token or not deployment_id:
        messages.error(request, 'Session expired. Please try again.')
        return redirect('management')

    try:
        deployment = Deployment.objects.get(id=deployment_id)
        
        headers = {
            'Authorization': f'token {token}',  # Sử dụng 'token' thay vì 'Bearer'
            'Accept': 'application/vnd.github.v3+json',
            'X-GitHub-Api-Version': '2022-11-28'
        }
        
        response = requests.get(
            'https://api.github.com/user/repos',
            headers=headers,
            params={'sort': 'updated', 'per_page': 100}
        )
        
        print(f"Repos fetch status: {response.status_code}")
        if response.status_code != 200:
            print(f"Repos fetch error: {response.text}")
            raise Exception(f'Failed to get repositories: {response.text}')

        repositories = response.json()
        
        return render(request, 'select_repository.html', {
            'deployment': deployment,
            'repositories': repositories
        })

    except Exception as e:
        messages.error(request, f'Error loading repositories: {str(e)}')
        return redirect('management')
def connect_repository(request):
    if request.method != 'POST':
        return redirect('management')

    deployment_id = request.POST.get('deployment_id')
    repo_name = request.POST.get('repository')
    token = request.session.get('github_token')

    try:
        deployment = Deployment.objects.get(id=deployment_id)

        headers = {
            'Authorization': f'token {token}',  # Dùng 'token' không phải 'Bearer'
            'Accept': 'application/vnd.github.v3+json',
            'X-GitHub-Api-Version': '2022-11-28'
        }

        # Kiểm tra quyền truy cập repository
        user_response = requests.get('https://api.github.com/user', headers=headers)
        if user_response.status_code != 200:
            raise Exception('Invalid GitHub token')

        repo_response = requests.get(
            f'https://api.github.com/repos/{repo_name}',
            headers=headers
        )
        
        if repo_response.status_code != 200:
            error_message = repo_response.json().get('message', 'Cannot access repository')
            raise Exception(error_message)

        permissions = repo_response.json().get('permissions', {})
        if not permissions.get('admin', False):
            raise Exception('You need admin permissions for this repository')

        # Tạo webhook
        webhook_url = request.build_absolute_uri(reverse('git_webhook'))
        webhook_data = {
            'name': 'web',
            'active': True,
            'events': ['push'],
            'config': {
                'url': webhook_url,
                'content_type': 'json',
                'secret': GITHUB_WEBHOOK_SECRET,
                'insecure_ssl': '0'
            }
        }

        print(f"Creating webhook for {repo_name}")
        print(f"Token type: {type(token)}")
        print(f"Headers: {headers}")
        print(f"Webhook data: {webhook_data}")

        webhook_response = requests.post(
            f'https://api.github.com/repos/{repo_name}/hooks',
            json=webhook_data,
            headers=headers
        )
        
        print(f"Response status: {webhook_response.status_code}")
        print(f"Response headers: {webhook_response.headers}")
        print(f"Response body: {webhook_response.text}")

        if webhook_response.status_code == 201:
            webhook_data = webhook_response.json()
            deployment.project_name = repo_name
            deployment.webhook_id = webhook_data['id']
            deployment.github_token = token
            deployment.save()
            
            messages.success(request, f'Successfully connected to {repo_name}')
        else:
            error_message = webhook_response.json().get('message', 'Unknown error')
            messages.error(request, f'Failed to create webhook: {error_message}')
            print(f"Full webhook error response: {webhook_response.text}")

    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        print(f'Detailed error: {str(e)}')

    return redirect('management')

import secrets  # Thêm import này
from urllib.parse import urlencode  # Add this import
def github_login(request, deployment_id):
    request.session['deployment_id'] = deployment_id

    state = secrets.token_hex(16)
    request.session['github_oauth_state'] = state

    params = {
      'client_id': GITHUB_CLIENT_ID,
      'redirect_uri': GITHUB_CALLBACK_URL,
      'scope': 'repo admin:repo_hook read:org write:repo_hook user',
      'state': state,
      'allow_signup': 'false'
  }
    
    auth_url = f'https://github.com/login/oauth/authorize?{urlencode(params)}'
    return redirect(auth_url)

def github_callback(request):
    code = request.GET.get('code')
    state = request.GET.get('state')
    
    stored_state = request.session.get('github_oauth_state')
    if not stored_state or state != stored_state:
        messages.error(request, 'Invalid state parameter')
        return redirect('management')

    try:
        deployment_id = request.session.get('deployment_id')
        if not deployment_id:
            messages.error(request, 'No deployment ID found in session')
            return redirect('management')

        deployment = Deployment.objects.get(id=deployment_id)
        
        token_response = requests.post(
            'https://github.com/login/oauth/access_token',
            data={
                'client_id': GITHUB_CLIENT_ID,
                'client_secret': GITHUB_CLIENT_SECRET,
                'code': code,
                'state': state
            },
            headers={'Accept': 'application/json'}
        )
        
        if token_response.status_code != 200:
            raise Exception(f'Failed to get access token: {token_response.text}')
            
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        if not access_token:
            raise Exception('No access token in response')

        # Log các scope nhận được
        scopes = token_data.get('scope', '')
        print(f"Received scopes: {scopes}")  # Debug log

        if not scopes or scopes.strip() == '':
            raise Exception('Token did not receive required scopes. Please revoke the current OAuth access in GitHub and try again.')

        headers = {
            'Authorization': f'token {access_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        user_response = requests.get('https://api.github.com/user', headers=headers)
        if user_response.status_code != 200:
            raise Exception('Invalid token or insufficient permissions')

        request.session['github_token'] = access_token
        return redirect('select_repository')

    except Deployment.DoesNotExist:
        messages.error(request, f'Deployment {deployment_id} not found')
    except Exception as e:
        messages.error(request, f'GitHub connection error: {str(e)}')
        print(f'Detailed error: {str(e)}')
    
    return redirect('management')
def github_install_webhook(request, deployment_id):
    """
    Cài đặt webhook cho repository được chọn
    """
    try:
        deployment = Deployment.objects.get(id=deployment_id)
        token = request.session.get('github_token')
        
        if not token:
            return redirect('github_login')

        # Lấy thông tin repository
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Kiểm tra quyền truy cập repository
        repo_url = f'https://api.github.com/repos/{deployment.project_name}'
        repo_response = requests.get(repo_url, headers=headers)
        
        if repo_response.status_code != 200:
            messages.error(request, f'Repository not found or no access: {deployment.project_name}')
            return redirect('management')

        # Tạo webhook
        webhook_url = request.build_absolute_uri(reverse('git_webhook'))
        webhook_data = {
            'name': 'web',
            'active': True,
            'events': ['push'],
            'config': {
                'url': webhook_url,
                'content_type': 'json',
                'secret': GITHUB_WEBHOOK_SECRET,
                'insecure_ssl': '0'
            }
        }

        # Kiểm tra webhook hiện có
        hooks_response = requests.get(f'{repo_url}/hooks', headers=headers)
        existing_hooks = hooks_response.json()
        
        for hook in existing_hooks:
            if hook['config'].get('url') == webhook_url:
                messages.warning(request, 'Webhook already exists')
                return redirect('management')

        # Tạo webhook mới
        response = requests.post(
            f'{repo_url}/hooks',
            json=webhook_data,
            headers=headers
        )

        if response.status_code == 201:
            webhook_data = response.json()
            deployment.webhook_id = webhook_data['id']
            deployment.webhook_url = webhook_url
            deployment.github_token = token  # Lưu token để sau này sử dụng
            deployment.save()
            
            messages.success(request, f'Successfully connected to repository: {deployment.project_name}')
        else:
            messages.error(request, f'Failed to install webhook: {response.json().get("message")}')

        return redirect('management')

    except Deployment.DoesNotExist:
        messages.error(request, 'Deployment not found')
    except Exception as e:
        messages.error(request, f'Error installing webhook: {str(e)}')
    return redirect('management')

@csrf_exempt  # GitHub không thể gửi CSRF token
@require_POST  # Chỉ chấp nhận POST requests
def git_webhook(request):
    """
    Xử lý webhook từ GitHub khi có push event
    """
    try:
        # Verify GitHub signature
        signature = request.headers.get('X-Hub-Signature-256')
        if not signature:
            return HttpResponse('No signature', status=400)

        # Verify webhook secret
        expected_signature = 'sha256=' + hmac.new(
            GITHUB_WEBHOOK_SECRET.encode(),
            request.body,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            return HttpResponse('Invalid signature', status=403)

        # Parse payload
        event = request.headers.get('X-GitHub-Event')
        if event != 'push':
            return JsonResponse({'status': 'ignored', 'message': f'Event {event} ignored'})

        payload = json.loads(request.body)
        
        # Lấy thông tin repository và branch
        repo_name = payload['repository']['full_name']
        branch = payload['ref'].split('/')[-1]  # Lấy tên branch từ refs/heads/main

        # Tìm deployment tương ứng
        try:
            deployment = Deployment.objects.get(
                project_name=repo_name,
                is_active=True
            )

            # Chỉ deploy khi push vào branch chính (main hoặc master)
            if branch in ['main', 'master']:
                # Thực hiện git pull
                result = subprocess.run(
                    ['git', 'pull', 'origin', branch],
                    cwd=deployment.project_path,
                    capture_output=True,
                    text=True
                )

                if result.returncode != 0:
                    raise Exception(f'Git pull failed: {result.stderr}')

                # Thực hiện các bước deploy bổ sung (nếu cần)
                # Ví dụ: restart services, collect static, migrate database
                deploy_steps = [
                    # Collect static files
                    ['python', 'manage.py', 'collectstatic', '--noinput'],
                    # Migrate database
                    ['python', 'manage.py', 'migrate'],
                    # Restart service (tùy vào setup của bạn)
                    # ['sudo', 'systemctl', 'restart', 'your-service'],
                ]

                for step in deploy_steps:
                    result = subprocess.run(
                        step,
                        cwd=deployment.project_path,
                        capture_output=True,
                        text=True
                    )
                    if result.returncode != 0:
                        raise Exception(f'Deploy step failed: {result.stderr}')

                return JsonResponse({
                    'status': 'success',
                    'message': f'Deployed {repo_name} successfully'
                })
            else:
                return JsonResponse({
                    'status': 'ignored',
                    'message': f'Branch {branch} ignored'
                })

        except Deployment.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'No deployment found for {repo_name}'
            }, status=404)

    except Exception as e:
        # Log error (nên dùng logging thay vì print)
        print(f'Webhook error: {str(e)}')
        return JsonResponse({
            'status': 'error',
            'message': str(e)
            }, status=500)