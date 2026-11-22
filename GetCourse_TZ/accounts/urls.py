from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('telegram/connect/', views.telegram_connect, name='telegram_connect'),
    path('telegram/disconnect/', views.telegram_disconnect, name='telegram_disconnect'),

    path('password-reset/', views.password_reset, name='password_reset'),
    path('password-reset/code/', views.password_reset_code, name='password_reset_code'),
    path('password-reset/new/', views.password_reset_new, name='password_reset_new'),
    path('password-reset/done/', views.password_reset_complete, name='password_reset_complete'),
]
