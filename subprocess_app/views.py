# filepath: /home/thongnm/prj/subprocess/subprocess_admin/subprocess_app/views.py
from django.http import HttpResponse
from django.shortcuts import render
import paramiko
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

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

        # Execute git pull command
        stdin, stdout, stderr = ssh.exec_command(f'cd {git_repo_path} && git pull')
        git_output = stdout.read().decode('utf-8')
        git_error = stderr.read().decode('utf-8')

        if git_error:
            ssh.close()
            return HttpResponse(f"Git pull failed:\n{git_error}", status=500)

        # Restart service
        stdin, stdout, stderr = ssh.exec_command(restart_command)
        restart_output = stdout.read().decode('utf-8')
        restart_error = stderr.read().decode('utf-8')

        ssh.close()

        if restart_error:
            return HttpResponse(f"Service restart failed:\n{restart_error}", status=500)
        return HttpResponse(f"Git pull successful:\n{git_output}\nService restart successful:\n{restart_output}")
    except Exception as e:
        return HttpResponse(f"SSH connection failed:\n{str(e)}", status=500)

def home(request):
    return render(request, 'home.html')