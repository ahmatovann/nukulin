from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('Необходимо указать e-mail')

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('У суперпользователя is_staff должен быть True')

        if extra_fields.get('is_superuser') is not True:
            raise ValueError('У суперпользователя is_superuser должен быть True')

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField('Электронная почта', unique=True)

    ROLE_CHOICES = [
        ('user', 'Пользователь'),
        ('admin', 'Администратор'),
    ]

    role = models.CharField(
        'Роль',
        max_length=20,
        choices=ROLE_CHOICES,
        default='user',
    )
    avatar = models.ImageField(
        'Фото профиля',
        upload_to='avatars/',
        blank=True,
        null=True,
    )
    blocked = models.BooleanField(
        'Учётная запись заблокирована',
        default=False,
    )
    created_at = models.DateTimeField(
        'Дата регистрации',
        auto_now_add=True,
    )
    # Telegram: привязывается самим пользователем через бота (кнопка в профиле).
    telegram_chat_id = models.BigIntegerField('Telegram: чат', null=True, blank=True, unique=True)
    telegram_username = models.CharField('Telegram: имя', max_length=64, blank=True)
    hide_from_rating = models.BooleanField(
        'Скрыть меня из рейтинга',
        default=False,
        help_text='Баллы и уровень вы по-прежнему видите, но другие пользователи вас в рейтинге не увидят.',
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.email