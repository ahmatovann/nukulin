"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts.views import admin_login_redirect
from courses.admin_views import export_report, remind_inactive, statistics

urlpatterns = [
    path('admin/login/', admin_login_redirect),  # вход в админку — через общую страницу входа
    path('admin/statistics/', statistics, name='admin_statistics'),
    path('admin/statistics/<int:pk>/report.<str:fmt>', export_report, name='admin_statistics_export'),
    path('admin/statistics/<int:pk>/remind/', remind_inactive, name='admin_statistics_remind'),
    path('_nested_admin/', include('nested_admin.urls')),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', include('feed.urls')),
    path('', include('courses.urls')),
]

if settings.DEBUG:
    # В режиме разработки Django сам отдаёт загруженные файлы (обложки, материалы)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
