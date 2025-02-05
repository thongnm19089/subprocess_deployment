# filepath: myapp/urls.py
from django.urls import path
from .views import view_git_logs, terminal_view,  manage ,deploy ,get_deployment ,update_deployment ,delete_deployment ,git_webhook
from . import views

urlpatterns = [
    path('api/deployment/<int:id>/', get_deployment, name='get_deployment'),
    path('api/deployment/<int:id>/update/', update_deployment, name='update_deployment'),
    path('api/deployment/<int:id>/delete/', delete_deployment, name='delete_deployment'),
    # path('verify-deployment-password/<int:deployment_id>/', 
    #         verify_deployment_password, 
    #         name='verify-deployment-password'),
    path('deploy/<int:id>/', deploy, name='deploy'),
    path('', manage, name='management'),
    path('cmd/', terminal_view, name='terminal'),
    # path('git-webhook/', git_webhook, name='git-webhook'),

    path('git-logs/<int:deployment_id>/', view_git_logs, name='deployment-git-logs'),
    # Server Management URLs
    path('servers/', views.server_management, name='server_management'),
    path('api/server/add/', views.add_server, name='add_server'),
    path('api/server/<int:server_id>/', views.get_server, name='get_server'),
    path('api/server/<int:server_id>/update/', views.update_server, name='update_server'),
    path('api/server/<int:server_id>/delete/', views.delete_server, name='delete_server'),
    
      # Existing URLs...
    path('github/login/<int:deployment_id>/', views.github_login, name='github_login'),
    path('github/callback/', views.github_callback, name='github_callback'),
    path('github/select-repository/', views.select_repository, name='select_repository'),
    path('github/connect-repository/', views.connect_repository, name='connect_repository'),
    path('git-webhook/', views.git_webhook, name='git_webhook'),

]   
