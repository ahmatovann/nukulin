from django.urls import path

from . import views

app_name = 'courses'

urlpatterns = [
    path('', views.home, name='home'),

    # Каталог и курсы (UC-2 — UC-4, UC-8)
    path('catalog/', views.catalog, name='catalog'),
    path('course/<int:pk>/', views.course_detail, name='course_detail'),
    path('course/<int:pk>/enroll/', views.enroll, name='enroll'),
    path('course/<int:pk>/access/', views.course_access, name='course_access'),
    path('code/', views.redeem_code_page, name='redeem_code'),
    path('course/<int:pk>/progress/', views.course_progress_page, name='course_progress'),

    # Обучение (UC-9 — UC-13)
    path('my/', views.my_courses, name='my_courses'),
    path('lesson/<int:pk>/', views.lesson_detail, name='lesson_detail'),
    path('stats/', views.my_stats, name='my_stats'),
    path('help/', views.help_page, name='help'),
    path('test/<int:pk>/', views.test_take, name='test_take'),
    path('test/result/<int:pk>/', views.test_result, name='test_result'),
]
