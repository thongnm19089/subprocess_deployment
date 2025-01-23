# filepath: myapp/urls.py
from django.urls import path
from .views import git_pull , home ,manage ,deploy ,get_deployment ,update_deployment ,delete_deployment

urlpatterns = [
    path('git-pull/', git_pull, name='git_pull'),
     path('deploy/<int:id>', deploy, name='deploy'),
    path('api/deployment/<int:id>/', get_deployment, name='get_deployment'),
    path('api/deployment/<int:id>/update/', update_deployment, name='update_deployment'),
    path('api/deployment/<int:id>/delete/', delete_deployment, name='delete_deployment'),

    path('', manage, name='manage'),

]   