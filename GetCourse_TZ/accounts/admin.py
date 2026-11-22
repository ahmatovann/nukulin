from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.template.response import TemplateResponse

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

    list_display = ('email', 'first_name', 'last_name', 'role', 'blocked', 'has_telegram', 'last_login', 'created_at')
    list_filter = ('role', 'blocked', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    readonly_fields = ('last_login', 'date_joined', 'created_at', 'telegram_username')
    actions = ['block_users', 'unblock_users']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Личные данные', {'fields': ('first_name', 'last_name', 'avatar')}),
        ('Роль и доступ', {'fields': ('role', 'blocked', 'is_active', 'is_superuser')}),
        ('Даты', {'fields': ('created_at', 'last_login', 'date_joined')}),
        ('Telegram', {'fields': ('telegram_username',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'role', 'password1', 'password2'),
        }),
    )

    @admin.display(description='Telegram', boolean=True)
    def has_telegram(self, obj):
        return bool(obj.telegram_chat_id)

    def save_model(self, request, obj, form, change):
        # Доступ в панель администратора есть только у роли «Администратор».
        obj.is_staff = obj.role == 'admin' or obj.is_superuser
        # UC-20, 3а: нельзя заблокировать самого себя.
        if obj.pk == request.user.pk and obj.blocked:
            obj.blocked = False
            self.message_user(request, 'Нельзя заблокировать собственную учётную запись.', messages.ERROR)
        super().save_model(request, obj, form, change)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        # Карточка пользователя сверху страницы: насколько заполнен профиль.
        from .views import profile_completeness
        obj = self.get_object(request, object_id)
        extra_context = {**(extra_context or {}), 'completeness': profile_completeness(obj) if obj else 0}
        return super().change_view(request, object_id, form_url, extra_context)

    # UC-20, шаги 3–5: «Заблокировать» / «Разблокировать» → подтверждение → смена статуса.
    def _confirm_status(self, request, queryset, block):
        if block and queryset.filter(pk=request.user.pk).exists():
            self.message_user(request, 'Нельзя заблокировать собственную учётную запись.', messages.ERROR)
            queryset = queryset.exclude(pk=request.user.pk)
            if not queryset.exists():
                return None

        if request.POST.get('post') == 'yes':
            updated = queryset.update(blocked=block)
            text = 'Заблокировано' if block else 'Разблокировано'
            self.message_user(request, f'{text} пользователей: {updated}', messages.SUCCESS)
            return None

        context = {
            **self.admin_site.each_context(request),
            'title': 'Заблокировать пользователей?' if block else 'Разблокировать пользователей?',
            'users': queryset,
            'block': block,
            'action': 'block_users' if block else 'unblock_users',
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
            'opts': self.model._meta,
        }
        return TemplateResponse(request, 'admin/accounts/user/status_confirmation.html', context)

    @admin.action(description='Заблокировать выбранных пользователей')
    def block_users(self, request, queryset):
        return self._confirm_status(request, queryset, block=True)

    @admin.action(description='Разблокировать выбранных пользователей')
    def unblock_users(self, request, queryset):
        return self._confirm_status(request, queryset, block=False)
