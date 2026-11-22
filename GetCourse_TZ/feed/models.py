"""Лента анонсов и новостей онлайн-школы (ФТ-26, ФТ-28)."""
from django.core.exceptions import ValidationError
from django.db import models

MAX_PINNED = 3


class Post(models.Model):
    """Публикация ленты. Видна всем, в том числе гостям без входа в систему."""

    title = models.CharField('Заголовок', max_length=200)
    text = models.TextField('Текст публикации')
    image = models.ImageField('Картинка', upload_to='feed/', blank=True, null=True)
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.SET_NULL,
        related_name='posts',
        verbose_name='Ссылка на курс',
        blank=True,
        null=True,
        help_text='Необязательно. Если выбрать курс, в публикации появится кнопка перехода.',
    )
    pinned = models.BooleanField(
        'Закрепить вверху',
        default=False,
        help_text=f'Закрепить можно не больше {MAX_PINNED} публикаций.',
    )
    created_at = models.DateTimeField('Дата публикации', auto_now_add=True)

    class Meta:
        verbose_name = 'Публикация ленты'
        verbose_name_plural = 'Лента: публикации'
        # Сначала закреплённые, затем остальные по дате, новые сверху (ФТ-26)
        ordering = ['-pinned', '-created_at']

    def __str__(self):
        return self.title

    def clean(self):
        # ФТ-28: закреплённых публикаций не больше трёх
        if self.pinned:
            others = Post.objects.filter(pinned=True).exclude(pk=self.pk).count()
            if others >= MAX_PINNED:
                raise ValidationError({
                    'pinned': f'Закрепить можно не больше {MAX_PINNED} публикаций. '
                              f'Сначала открепите одну из закреплённых.',
                })
