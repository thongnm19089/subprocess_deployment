# filepath: myapp/urls.py
from django.urls import path
from .views import git_pull , home ,manage

urlpatterns = [
    path('git-pull/', git_pull, name='git_pull'),
     path('deploy/<int:id>', home, name='home'),
     path('', manage, name='manage'),

]   