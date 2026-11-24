from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.core.cache import cache
from django.core.exceptions import ValidationError

from .middleware import BLOCKED_MESSAGE
from .models import User

MAX_LOGIN_ATTEMPTS = 5      # ТЗ: после 5 неверных попыток подряд…
LOCKOUT_SECONDS = 10 * 60   # …вход блокируется на 10 минут


def _lock_key(email):
    return f'login-fails:{email}'


def clear_login_failures(email):
    cache.delete(_lock_key(email.lower()))


class StyledFormMixin:
    """Добавляет полям класс gc-input, чтобы они выглядели по стилю сайта."""

    def _style_fields(self):
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (css + ' gc-input').strip()


class RegisterForm(StyledFormMixin, UserCreationForm):
    first_name = forms.CharField(label='Имя', max_length=150)
    last_name = forms.CharField(label='Фамилия', max_length=150)
    email = forms.EmailField(
        label='Электронная почта',
        error_messages={'invalid': 'Введите правильный e-mail, например name@mail.ru.'},
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].label = 'Пароль'
        self.fields['password2'].label = 'Повторите пароль'
        self.fields['password1'].help_text = 'Не меньше 8 символов.'
        self.fields['email'].widget.attrs.update({'autocomplete': 'email'})
        self._style_fields()

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Пользователь с таким e-mail уже существует.')
        return email


class LoginForm(StyledFormMixin, AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'Неверный e-mail или пароль.',
        'inactive': 'Учётная запись отключена.',
        'blocked': BLOCKED_MESSAGE,
        'locked': 'Слишком много неудачных попыток. Вход заблокирован на 10 минут.',
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields['username'].label = 'Электронная почта'
        self.fields['username'].widget.attrs.update({'autocomplete': 'email', 'inputmode': 'email'})
        self.fields['password'].label = 'Пароль'
        self._style_fields()

    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()

    def clean(self):
        email = self.cleaned_data.get('username') or ''
        key = _lock_key(email)

        if email and cache.get(key, 0) >= MAX_LOGIN_ATTEMPTS:
            raise ValidationError(self.error_messages['locked'], code='locked')

        try:
            return super().clean()
        except ValidationError as error:
            if email and getattr(error, 'code', None) == 'invalid_login':
                fails = cache.get(key, 0) + 1
                cache.set(key, fails, LOCKOUT_SECONDS)
                if fails >= MAX_LOGIN_ATTEMPTS:
                    raise ValidationError(self.error_messages['locked'], code='locked')
            raise

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.blocked:
            raise ValidationError(self.error_messages['blocked'], code='blocked')


# ---------------------------------------------------------------------------
# UC-14: профиль (пользователь и администратор)
# ---------------------------------------------------------------------------

MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2 МБ
AVATAR_FORMATS = {'JPEG', 'PNG'}
AVATAR_ERROR = 'Фото должно быть в формате JPG или PNG и не больше 2 МБ.'


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'avatar', 'hide_from_rating')
        labels = {'first_name': 'Имя', 'last_name': 'Фамилия', 'avatar': 'Фото профиля',
                  'hide_from_rating': 'Скрыть меня из рейтинга'}
        widgets = {'avatar': forms.FileInput(attrs={'accept': 'image/jpeg,image/png'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self._style_fields()
        self.fields['avatar'].widget.attrs['class'] = 'gc-file'

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar and avatar != self.instance.avatar:
            if avatar.size > MAX_AVATAR_BYTES:
                raise ValidationError(AVATAR_ERROR)
            image = getattr(avatar, 'image', None)
            fmt = getattr(image, 'format', None)
            if fmt not in AVATAR_FORMATS:
                raise ValidationError(AVATAR_ERROR)
        return avatar


class ChangePasswordForm(StyledFormMixin, PasswordChangeForm):
    error_messages = {
        **PasswordChangeForm.error_messages,
        'password_incorrect': 'Текущий пароль указан неверно.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'Текущий пароль'
        self.fields['new_password1'].label = 'Новый пароль'
        self.fields['new_password2'].label = 'Повторите новый пароль'
        self.fields['new_password1'].help_text = 'Не меньше 8 символов.'
        self.fields['old_password'].widget.attrs.pop('autofocus', None)
        self._style_fields()


# ---------------------------------------------------------------------------
# UC-6, альтернативный сценарий 1а: «Забыли пароль?»
# ---------------------------------------------------------------------------

class ResetRequestForm(StyledFormMixin, PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].label = 'Электронная почта'
        self._style_fields()


class ResetSetPasswordForm(StyledFormMixin, SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'Новый пароль'
        self.fields['new_password2'].label = 'Повторите новый пароль'
        self.fields['new_password1'].help_text = 'Не меньше 8 символов.'
        self._style_fields()
