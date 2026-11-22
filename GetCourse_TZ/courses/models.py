from django.db import models


class Category(models.Model):
    name = models.CharField('Название категории', max_length=100, unique=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']

    def __str__(self):
        return self.name


class Course(models.Model):
    DIFFICULTY_CHOICES = [
        ('beginner', 'Начальный'),
        ('intermediate', 'Средний'),
        ('advanced', 'Продвинутый'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('published', 'Опубликован'),
    ]

    title = models.CharField('Название курса', max_length=200)
    description = models.TextField('Описание')
    learning_outcomes = models.TextField(
        'Чему научится пользователь',
        blank=True,
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='courses',
        verbose_name='Категория',
    )
    difficulty = models.CharField(
        'Уровень сложности',
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default='beginner',
    )
    cover_image = models.ImageField(
        'Обложка',
        upload_to='course_covers/',
        blank=True,
        null=True,
    )
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
    )
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    class Meta:
        verbose_name = 'Курс'
        verbose_name_plural = 'Курсы'
        ordering = ['title']

    def __str__(self):
        return self.title

    @property
    def lesson_count(self):
        return self.lessons.count()


class Lesson(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='lessons',
        verbose_name='Курс',
    )
    order = models.PositiveIntegerField('Номер урока', default=1)
    title = models.CharField('Название урока', max_length=200)
    content = models.TextField('Содержание урока')
    video_url = models.URLField('Ссылка на видео', blank=True)

    class Meta:
        verbose_name = 'Урок'
        verbose_name_plural = 'Уроки'
        ordering = ['course', 'order']
        constraints = [
            models.UniqueConstraint(
                fields=['course', 'order'],
                name='unique_lesson_order_per_course',
            )
        ]

    def __str__(self):
        return f'{self.course.title}: {self.title}'


class LessonFile(models.Model):
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name='Урок',
    )
    name = models.CharField('Название файла', max_length=200)
    file = models.FileField('Файл', upload_to='lesson_files/')

    class Meta:
        verbose_name = 'Файл урока'
        verbose_name_plural = 'Файлы уроков'

    def __str__(self):
        return self.name