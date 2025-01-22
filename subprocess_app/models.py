from django.db import models
from datetime import datetime

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