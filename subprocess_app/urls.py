# filepath: myapp/urls.py
from django.urls import path
from .views import view_git_logs, terminal_view,  manage ,deploy ,get_deployment ,update_deployment ,delete_deployment ,git_webhook

urlpatterns = [
    path('api/deployment/<int:id>/', get_deployment, name='get_deployment'),
    path('api/deployment/<int:id>/update/', update_deployment, name='update_deployment'),
    path('api/deployment/<int:id>/delete/', delete_deployment, name='delete_deployment'),
    # path('verify-deployment-password/<int:deployment_id>/', 
    #         verify_deployment_password, 
    #         name='verify-deployment-password'),
    path('deploy/<int:id>/', deploy, name='deploy'),
    path('', manage, name='manage'),
    path('cmd/', terminal_view, name='terminal'),
    path('git-webhook/', git_webhook, name='git-webhook'),

    path('git-logs/<int:deployment_id>/', view_git_logs, name='deployment-git-logs'),
]   
