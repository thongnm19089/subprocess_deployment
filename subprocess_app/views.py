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