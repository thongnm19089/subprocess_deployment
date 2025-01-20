# filepath: myapp/urls.py
from django.urls import path
from .views import git_pull , home

urlpatterns = [
    path('git-pull/', git_pull, name='git_pull'),
     path('', home, name='home'),

]