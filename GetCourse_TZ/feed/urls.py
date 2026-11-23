from django.urls import path

from . import views

app_name = 'feed'

urlpatterns = [
    path('news/<int:pk>/', views.post_detail, name='post_detail'),
]
