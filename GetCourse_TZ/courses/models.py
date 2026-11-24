from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


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
    price = models.DecimalField(
        'Цена, сом',
        max_digits=8,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(1)],
        help_text='Бесплатных курсов нет: получить доступ можно оплатой или по коду, который выдаёт администратор.',
    )
    is_private = models.BooleanField(
        'Закрытый курс',
        default=False,
        help_text='Закрытый курс не показывается в каталоге и ленте. Открыть его можно по ссылке или по коду доступа. '
                  'Оплата и коды работают так же, как у обычных курсов.',
    )
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    class Meta:
        verbose_name = 'Курс'
        verbose_name_plural = 'Курсы'
        ordering = ['title']

    def __str__(self):
        return self.title

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.price or self.price < 1:
            raise ValidationError({'price': 'Укажите цену курса больше нуля. Бесплатный доступ даётся только кодом от администратора.'})

    @property
    def lesson_count(self):
        return self.lessons.count()


    @property
    def rating_average(self):
        """Средняя оценка курса по отзывам (ФТ-31)."""
        values = [review.rating for review in self.reviews.all() if not review.is_hidden]
        return round(sum(values) / len(values), 1) if values else None

    @property
    def rating_count(self):
        return sum(1 for review in self.reviews.all() if not review.is_hidden)


class Lesson(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='lessons',
        verbose_name='Курс',
    )
    order = models.PositiveIntegerField('Номер урока', default=1)
    title = models.CharField('Название урока', max_length=200)
    content = models.TextField(
        'Текст урока',
        blank=True,
        help_text='Можно оставить пустым, если урок состоит только из видео или презентации.',
    )
    video_url = models.URLField(
        'Ссылка на видео',
        blank=True,
        help_text='Ссылка на YouTube. Видео встроится прямо в урок.',
    )
    audio_url = models.URLField(
        'Ссылка на аудио',
        blank=True,
        help_text='Ссылка на mp3-файл или на запись в YouTube — появится проигрыватель.',
    )
    presentation_url = models.URLField(
        'Ссылка на презентацию',
        blank=True,
        help_text='Google Презентации, Canva или другой сервис со ссылкой для встраивания.',
    )
    presentation_file = models.FileField(
        'Файл презентации',
        upload_to='lessons/presentations/',
        blank=True,
        null=True,
        help_text='PDF или PowerPoint. PDF откроется прямо на странице урока.',
    )

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

    @property
    def has_presentation(self):
        return bool(self.presentation_url or self.presentation_file)

    @property
    def presentation_is_pdf(self):
        return bool(self.presentation_file) and self.presentation_file.name.lower().endswith('.pdf')

    @property
    def material_kinds(self):
        """Какие материалы есть в уроке — показывается метками в начале страницы."""
        kinds = []
        if self.video_url:
            kinds.append('Видео')
        if self.audio_url:
            kinds.append('Аудио')
        if self.has_presentation:
            kinds.append('Презентация')
        if self.content.strip():
            kinds.append('Текст')
        if self.files.exists():
            kinds.append('Материалы для скачивания')
        return kinds


class Comment(models.Model):
    """Комментарий пользователя к уроку (ФТ-30)."""

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Урок',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Автор',
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='replies',
        verbose_name='Ответ на комментарий',
        blank=True,
        null=True,
    )
    text = models.TextField('Текст комментария', max_length=2000)
    created_at = models.DateTimeField('Дата', auto_now_add=True)
    is_hidden = models.BooleanField(
        'Скрыт',
        default=False,
        help_text='Скрытый комментарий виден только администратору.',
    )

    class Meta:
        verbose_name = 'Комментарий к уроку'
        verbose_name_plural = 'Комментарии к урокам'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.user} — {self.lesson.title}: {self.text[:40]}'


class Review(models.Model):
    """Отзыв об окончании курса с оценкой (ФТ-31)."""

    RATING_CHOICES = [(value, f'{value} из 5') for value in range(1, 6)]

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name='Курс',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name='Автор',
    )
    rating = models.PositiveSmallIntegerField(
        'Оценка',
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    text = models.TextField('Отзыв', max_length=2000, blank=True)
    created_at = models.DateTimeField('Дата', auto_now_add=True)
    is_hidden = models.BooleanField('Скрыт', default=False)

    class Meta:
        verbose_name = 'Отзыв о курсе'
        verbose_name_plural = 'Отзывы о курсах'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['course', 'user'],
                name='unique_review_per_user_course',
            )
        ]

    def __str__(self):
        return f'{self.user} — {self.course.title}: {self.rating} из 5'


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

class Test(models.Model):
    lesson = models.OneToOneField(
        Lesson,
        on_delete=models.CASCADE,
        related_name='test',
        verbose_name='Урок',
    )
    pass_score = models.PositiveSmallIntegerField(
        'Проходной балл, %',
        default=70,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text='От 1 до 100. По умолчанию 70%.',
    )

    class Meta:
        verbose_name = 'Тест'
        verbose_name_plural = 'Тесты'
        ordering = ['lesson__course', 'lesson__order']

    def __str__(self):
        return f'Тест к уроку «{self.lesson.title}» ({self.lesson.course.title})'


class Question(models.Model):
    TYPE_CHOICES = [
        ('single', 'Один правильный ответ'),
        ('multiple', 'Несколько правильных ответов'),
    ]

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name='Тест',
    )
    order = models.PositiveIntegerField('Порядок', default=0)
    text = models.TextField('Текст вопроса')
    qtype = models.CharField(
        'Тип ответа',
        max_length=10,
        choices=TYPE_CHOICES,
        default='single',
    )

    class Meta:
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'
        ordering = ['order', 'id']

    def __str__(self):
        return self.text[:80]


class Answer(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Вопрос',
    )
    order = models.PositiveIntegerField('Порядок', default=0)
    text = models.CharField('Вариант ответа', max_length=300)
    is_correct = models.BooleanField('Правильный', default=False)

    class Meta:
        verbose_name = 'Вариант ответа'
        verbose_name_plural = 'Варианты ответов'
        ordering = ['order', 'id']

    def __str__(self):
        return self.text



class Enrollment(models.Model):
    """Запись пользователя на курс (UC-8). Повторная запись запрещена."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name='Пользователь',
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name='Курс',
    )
    SOURCE_CHOICES = [
        ('payment', 'Оплата'),
        ('code', 'Код доступа'),
        ('admin', 'Выдал администратор'),
    ]

    enrolled_at = models.DateTimeField('Дата записи', default=timezone.now)
    completed_at = models.DateTimeField('Курс завершён', null=True, blank=True)
    source = models.CharField('Как получен доступ', max_length=10, choices=SOURCE_CHOICES, default='admin')

    class Meta:
        verbose_name = 'Запись на курс'
        verbose_name_plural = 'Записи на курсы'
        ordering = ['-enrolled_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'course'], name='unique_enrollment'),
        ]

    def __str__(self):
        return f'{self.user} → {self.course}'


class TestAttempt(models.Model):
    """Попытка сдачи теста (UC-11, UC-12). Засчитывается лучший результат."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='test_attempts',
        verbose_name='Пользователь',
    )
    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='attempts',
        verbose_name='Тест',
    )
    score = models.PositiveSmallIntegerField(
        'Результат, %',
        validators=[MaxValueValidator(100)],
    )
    passed = models.BooleanField('Сдан', default=False)
    created_at = models.DateTimeField('Дата попытки', default=timezone.now)

    class Meta:
        verbose_name = 'Попытка теста'
        verbose_name_plural = 'Попытки тестов'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} — {self.test.lesson.title}: {self.score}%'


class AttemptAnswer(models.Model):
    """Ответ пользователя на один вопрос в попытке — нужен для «сложных вопросов»."""

    attempt = models.ForeignKey(
        TestAttempt,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Попытка',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='attempt_answers',
        verbose_name='Вопрос',
    )
    selected = models.ManyToManyField(Answer, blank=True, verbose_name='Выбранные ответы')
    is_correct = models.BooleanField('Ответ верный', default=False)

    class Meta:
        verbose_name = 'Ответ в попытке'
        verbose_name_plural = 'Ответы в попытках'


def generate_access_code():
    """Короткий код без похожих символов (0/O, 1/I), чтобы его удобно было диктовать."""
    import secrets
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    raw = ''.join(secrets.choice(alphabet) for _ in range(8))
    return f'{raw[:4]}-{raw[4:]}'


class AccessCode(models.Model):
    """Код доступа к закрытому курсу. Его выдаёт администратор."""

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='access_codes',
        verbose_name='Курс',
    )
    code = models.CharField('Код', max_length=20, unique=True, blank=True, default=generate_access_code)
    note = models.CharField(
        'Кому выдан',
        max_length=120,
        blank=True,
        help_text='Для себя: например, «группа ПИ-2-24» или «Иван Петров».',
    )
    max_uses = models.PositiveIntegerField(
        'Сколько раз можно использовать',
        default=1,
        validators=[MinValueValidator(1)],
        help_text='1 — код для одного человека, больше — для группы.',
    )
    used_count = models.PositiveIntegerField('Уже использован', default=0, editable=False)
    expires_at = models.DateTimeField('Действует до', null=True, blank=True, help_text='Пусто — без срока.')
    is_active = models.BooleanField('Действует', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Код доступа'
        verbose_name_plural = 'Коды доступа'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.code} → {self.course}'

    def save(self, *args, **kwargs):
        self.code = (self.code or generate_access_code()).strip().upper()
        super().save(*args, **kwargs)

    @property
    def uses_left(self):
        return max(self.max_uses - self.used_count, 0)

    def problem(self):
        """Почему код нельзя применить. None — код рабочий."""
        if not self.is_active:
            return 'Этот код отключён администратором.'
        if self.expires_at and self.expires_at < timezone.now():
            return 'Срок действия кода закончился.'
        if self.used_count >= self.max_uses:
            return 'Этот код уже использован — попросите у администратора новый.'
        return None


class Payment(models.Model):
    """Журнал оплат. Оплата учебная: деньги не списываются, номер карты не хранится."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Пользователь',
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name='Курс',
    )
    amount = models.DecimalField('Сумма, сом', max_digits=8, decimal_places=0)
    card_last4 = models.CharField('Последние цифры карты', max_length=4, blank=True)
    created_at = models.DateTimeField('Дата оплаты', default=timezone.now)

    class Meta:
        verbose_name = 'Платёж'
        verbose_name_plural = 'Платежи'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} — {self.course}: {self.amount} сом'

    @property
    def receipt_number(self):
        """Номер чека берётся из номера записи в журнале, отдельное поле не нужно."""
        return f'{self.pk:06d}'
