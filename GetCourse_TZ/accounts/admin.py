from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import User


class UserCreateForm(UserCreationForm):
    """Форма создания пользователя: вход по e-mail, без username."""

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name')


class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = '__all__'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserEditForm
    add_form = UserCreateForm

    list_display = ('email', 'first_name', 'last_name', 'role', 'blocked', 'created_at')
    list_filter = ('role', 'blocked', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    readonly_fields = ('last_login', 'date_joined', 'created_at')
    actions = ['block_users', 'unblock_users']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Личные данные', {'fields': ('first_name', 'last_name', 'avatar')}),
        ('Роль и доступ', {'fields': ('role', 'blocked', 'is_active', 'is_superuser')}),
        ('Даты', {'fields': ('created_at', 'last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'role', 'password1', 'password2'),
        }),
    )

    def save_model(self, request, obj, form, change):
        # Доступ в панель администратора есть только у роли «Администратор».
        obj.is_staff = obj.role == 'admin' or obj.is_superuser
        super().save_model(request, obj, form, change)

    @admin.action(description='Заблокировать выбранных пользователей')
    def block_users(self, request, queryset):
        queryset = queryset.exclude(pk=request.user.pk)
        updated = queryset.update(blocked=True)
        self.message_user(request, f'Заблокировано пользователей: {updated}', messages.SUCCESS)

    @admin.action(description='Разблокировать выбранных пользователей')
    def unblock_users(self, request, queryset):
        updated = queryset.update(blocked=False)
        self.message_user(request, f'Разблокировано пользователей: {updated}', messages.SUCCESS)
