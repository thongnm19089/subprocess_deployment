from django.contrib import admin
from .models import Server, Deployment

class ServerAdmin(admin.ModelAdmin):
    list_display = ('server_name', 'server_ip', 'user', 'created_at', 'updated_at')
    search_fields = ('server_name', 'server_ip', 'user')

class DeploymentAdmin(admin.ModelAdmin):
    list_display = ('project_name', 'project_path', 'service_name', 'status', 'server', 'created_at', 'updated_at')
    list_filter = ('status', 'server')
    search_fields = ('project_name', 'service_name', 'project_path')

admin.site.register(Server, ServerAdmin)
admin.site.register(Deployment, DeploymentAdmin)