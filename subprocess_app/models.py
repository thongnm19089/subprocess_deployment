from django.db import models
from datetime import datetime
from django.utils import timezone

class GitLog(models.Model):
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('error', 'Error'),
        ('ignored', 'Ignored')
    ]

    deployment = models.ForeignKey('Deployment', on_delete=models.CASCADE, related_name='git_logs')
    timestamp = models.DateTimeField(default=timezone.now)
    commit_id = models.CharField(max_length=40, blank=True, null=True)
    commit_message = models.TextField(blank=True, null=True)
    author_name = models.CharField(max_length=100, blank=True, null=True)
    author_email = models.EmailField(blank=True, null=True)
    branch = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    deployment_message = models.TextField(blank=True, null=True)
    files_changed = models.JSONField(default=dict, blank=True)  # Lưu thông tin files thay đổi

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.deployment.project_name} - {self.commit_id[:7]} - {self.status}"
class Server(models.Model):
    server_name = models.CharField(max_length=100)
    server_ip = models.CharField(max_length=100) 
    user = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.server_name

class Deployment(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    
    project_name = models.CharField(max_length=100)
    project_path = models.CharField(max_length=200)
    service_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    server = models.ForeignKey(Server, on_delete=models.CASCADE , null=True , blank=True)

    def __str__(self):
        return f"{self.project_name} ({self.service_name})"

    class Meta:
        ordering = ['-created_at']