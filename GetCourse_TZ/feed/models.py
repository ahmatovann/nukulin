"""Лента анонсов и новостей онлайн-школы (ФТ-26, ФТ-28)."""
from django.core.exceptions import ValidationError
from django.db import models

MAX_PINNED = 3


class Post(models.Model):
    """Публикация ленты. Видна всем, в том числе гостям без входа в систему."""

    COVER = 'cover'
    CONTAIN = 'contain'

    ANNOUNCEMENT = 'announcement'
    NEWS = 'news'
    TIP = 'tip'
    EVENT = 'event'
    KIND_CHOICES = [
        (ANNOUNCEMENT, 'Анонс'),
        (NEWS, 'Новость'),
        (TIP, 'Совет'),
        (EVENT, 'Событие'),
    ]

    title = models.CharField('Заголовок', max_length=200)
    kind = models.CharField(
        'Тип публикации',
        max_length=20,
        choices=KIND_CHOICES,
        default=NEWS,
        help_text='Показывается цветной меткой в начале публикации.',
    )
    summary = models.CharField(
        'Короткое описание',
        max_length=300,
        blank=True,
        help_text='Одно предложение под заголовком. Если не заполнить, '
                  'возьмётся начало текста публикации.',
    )
    text = models.TextField('Текст публикации')
    image = models.ImageField(
        'Фотография',
        upload_to='feed/',
        blank=True,
        null=True,
        help_text='Лучше всего подходит широкая картинка, например 1200 на 675 точек. '
                  'Без неё публикация тоже выглядит аккуратно.',
    )
    image_fit = models.CharField(
        'Как показывать картинку',
        max_length=10,
        choices=[
            (COVER, 'Заполнить рамку — подходит для обычных фотографий'),
            (CONTAIN, 'Вписать целиком — для коллажей и картинок без фона'),
        ],
        default=COVER,
    )
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

    @property
    def short_text(self):
        """Одно предложение для карточки: своё описание или начало текста."""
        if self.summary:
            return self.summary
        first = self.text.strip().split('\n')[0]
        return first if len(first) <= 200 else first[:197].rstrip() + '…'

    @property
    def initial(self):
        """Первая буква заголовка — для заглушки, когда фотографии нет."""
        return self.title[:1].upper()

    def clean(self):
        # ФТ-28: закреплённых публикаций не больше трёх
        if self.pinned:
            others = Post.objects.filter(pinned=True).exclude(pk=self.pk).count()
            if others >= MAX_PINNED:
                raise ValidationError({
                    'pinned': f'Закрепить можно не больше {MAX_PINNED} публикаций. '
                              f'Сначала открепите одну из закреплённых.',
                })
