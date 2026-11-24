import nested_admin
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Count, F
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    generate_access_code,
    AccessCode,
    Payment,
    Comment,
    Review,
    Answer,
    Category,
    Course,
    Enrollment,
    Lesson,
    LessonFile,
    Question,
    Test,
    TestAttempt,
)

MAX_LESSONS = 50
MAX_QUESTIONS = 30
MIN_ANSWERS, MAX_ANSWERS = 2, 6
TEMP_OFFSET = 100000  # временный сдвиг номеров при перестановке уроков

admin.site.site_header = 'GetCourse — администрирование'
admin.site.site_title = 'GetCourse'
admin.site.index_title = 'Управление системой'


def _active_forms(formset):
    """Формы, которые останутся после сохранения (заполненные и не удалённые)."""
    result = []
    for form in formset.forms:
        data = getattr(form, 'cleaned_data', None)
        if not data or data.get('DELETE'):
            continue
        result.append(form)
    return result


# ---------------------------------------------------------------------------
# Уроки внутри курса (UC-15, UC-16)
# ---------------------------------------------------------------------------

class LessonInlineFormSet(nested_admin.formsets.NestedInlineFormSet):
    """Правила ТЗ: 1–50 уроков, курс без уроков не публикуется.
    Порядок меняется перетаскиванием и сохраняется как 1, 2, 3…"""

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        count = len(_active_forms(self))
        if count > MAX_LESSONS:
            raise ValidationError(f'В курсе может быть не больше {MAX_LESSONS} уроков.')
        if self.instance.status == 'published' and count == 0:
            raise ValidationError(
                'Нельзя опубликовать курс без уроков. '
                'Добавьте хотя бы один урок или оставьте статус «Черновик».'
            )

    def save(self, commit=True):
        course = self.instance
        # Временно сдвигаем номера, чтобы уроки могли поменяться местами
        # без конфликта «два урока с одним номером».
        if course.pk:
            Lesson.objects.filter(course=course).update(order=F('order') + TEMP_OFFSET)
        try:
            saved = super().save(commit)
        finally:
            if course.pk:
                self._renumber(course)
        return saved

    def _renumber(self, course):
        position = {}
        for form in self.forms:
            if form in self.deleted_forms or not form.instance.pk:
                continue
            position[form.instance.pk] = (form.instance.order, getattr(form, '_list_position', 0))
        lessons = list(Lesson.objects.filter(course=course))
        lessons.sort(key=lambda l: position.get(l.pk, (TEMP_OFFSET + l.order, 0)))
        Lesson.objects.filter(course=course).update(order=F('order') + TEMP_OFFSET * 2)
        for number, lesson in enumerate(lessons, start=1):
            Lesson.objects.filter(pk=lesson.pk).update(order=number)


class LessonInline(nested_admin.NestedTabularInline):
    model = Lesson
    formset = LessonInlineFormSet
    sortable_field_name = 'order'
    extra = 0
    max_num = MAX_LESSONS
    fields = ('order', 'title', 'content', 'test_status')
    readonly_fields = ('test_status',)
    show_change_link = True  # открыть урок: видео, файлы и тест

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'content':
            field.widget.attrs.update({'rows': 2, 'cols': 36})
        return field

    @admin.display(description='Тест')
    def test_status(self, obj):
        if not obj or not obj.pk:
            return '—'
        test = getattr(obj, 'test', None) if hasattr(obj, 'test') else None
        if test:
            return format_html('<span class="gc-pill gc-pill--ok">есть · {} вопр.</span>', test.questions.count())
        return format_html('<span class="gc-pill">нет</span>')


class LessonFileInline(admin.TabularInline):
    model = LessonFile
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'courses_total')
    search_fields = ('name',)

    @admin.display(description='Курсов')
    def courses_total(self, obj):
        return obj.courses.count()


@admin.register(Course)
class CourseAdmin(nested_admin.NestedModelAdmin):
    list_display = ('title', 'category', 'difficulty', 'price', 'is_private', 'status', 'lessons_total', 'created_at')
    list_filter = ('status', 'is_private', 'difficulty', 'category')
    search_fields = ('title', 'description')
    fieldsets = (
        (None, {'fields': ('title', 'category', 'difficulty', 'status')}),
        ('Доступ', {'fields': ('price', 'is_private')}),
        ('Описание', {'fields': ('description', 'learning_outcomes', 'cover_image')}),
    )
    inlines = [LessonInline]
    actions = ['publish_courses', 'make_draft', 'make_codes']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_lessons=Count('lessons'))

    @admin.display(description='Уроков', ordering='_lessons')
    def lessons_total(self, obj):
        return obj._lessons

    def change_view(self, request, object_id, form_url='', extra_context=None):
        # Карточка курса сверху страницы: главные цифры по курсу.
        from .stats import course_stats
        course = self.get_object(request, object_id)
        card = None
        if course is not None:
            s = course_stats(course)
            card = {
                'lessons': course.lessons.count(),
                'tests': Test.objects.filter(lesson__course=course).count(),
                'enrolled': s.get('total', 0),
                'completed_pct': s.get('completed_pct', 0),
                'avg_progress': s.get('avg_progress', 0),
            }
        extra_context = {**(extra_context or {}), 'course_card': card}
        return super().change_view(request, object_id, form_url, extra_context)

    def delete_view(self, request, object_id, extra_context=None):
        # ФТ-21: предупреждаем, если на курс уже записаны пользователи.
        if request.method == 'GET':
            course = self.get_object(request, object_id)
            if course is not None:
                count = course.enrollments.count()
                if count:
                    self.message_user(
                        request,
                        f'Внимание: на курс «{course.title}» записано пользователей: {count}. '
                        'После удаления их прогресс и результаты тестов будут потеряны.',
                        messages.WARNING,
                    )
        return super().delete_view(request, object_id, extra_context)

    @admin.action(description='Выпустить 10 кодов доступа для выбранных курсов')
    def make_codes(self, request, queryset):
        total = 0
        for course in queryset:
            AccessCode.objects.bulk_create([AccessCode(course=course, code=generate_access_code()) for _ in range(10)])
            total += 10
        if total:
            self.message_user(
                request,
                f'Выпущено кодов: {total}. Каждый рассчитан на одного человека. Посмотреть их можно в разделе «Коды доступа».',
                messages.SUCCESS,
            )

    @admin.action(description='Опубликовать выбранные курсы')
    def publish_courses(self, request, queryset):
        empty = [c.title for c in queryset if not c.lessons.exists()]
        ready = queryset.filter(lessons__isnull=False).distinct()
        published = Course.objects.filter(pk__in=ready).update(status='published')
        if published:
            self.message_user(request, f'Опубликовано курсов: {published}', messages.SUCCESS)
        if empty:
            self.message_user(
                request,
                'Не опубликованы, потому что в них нет уроков: ' + ', '.join(empty),
                messages.ERROR,
            )

    @admin.action(description='Вернуть в черновики')
    def make_draft(self, request, queryset):
        updated = queryset.update(status='draft')
        self.message_user(request, f'Переведено в черновики: {updated}', messages.SUCCESS)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order', 'has_test')
    list_filter = ('course',)
    search_fields = ('title', 'course__title')
    ordering = ('course', 'order')
    fields = ('course', 'order', 'title', 'content', 'video_url', 'test_button')
    readonly_fields = ('test_button',)
    inlines = [LessonFileInline]

    @admin.display(description='Тест', boolean=True)
    def has_test(self, obj):
        return hasattr(obj, 'test')

    @admin.display(description='Тест урока')
    def test_button(self, obj):
        # UC-17: «Администратор открывает урок и нажимает „Тест“».
        if not obj or not obj.pk:
            return 'Сохраните урок, затем создайте к нему тест.'
        if hasattr(obj, 'test'):
            url = reverse('admin:courses_test_change', args=[obj.test.pk])
            return format_html(
                '<a class="button gc-test-btn" href="{}">Открыть тест</a> '
                '<span class="gc-pill gc-pill--ok">вопросов: {}, проходной балл {}%</span>',
                url, obj.test.questions.count(), obj.test.pass_score,
            )
        url = reverse('admin:courses_test_add') + f'?lesson={obj.pk}'
        return format_html('<a class="button gc-test-btn" href="{}">Создать тест</a>', url)

    def delete_model(self, request, obj):
        course = obj.course
        super().delete_model(request, obj)
        self._draft_if_empty(request, course)

    def delete_queryset(self, request, queryset):
        courses = {lesson.course for lesson in queryset}
        super().delete_queryset(request, queryset)
        for course in courses:
            self._draft_if_empty(request, course)

    def _draft_if_empty(self, request, course):
        if course.status == 'published' and not course.lessons.exists():
            course.status = 'draft'
            course.save(update_fields=['status'])
            self.message_user(
                request,
                f'Курс «{course.title}» остался без уроков и переведён в черновики.',
                messages.WARNING,
            )


@admin.register(LessonFile)
class LessonFileAdmin(admin.ModelAdmin):
    list_display = ('name', 'lesson')
    search_fields = ('name', 'lesson__title', 'lesson__course__title')


# ---------------------------------------------------------------------------
# Тесты (UC-17): вопросы и варианты ответов на одной странице
# ---------------------------------------------------------------------------

class AnswerInlineFormSet(nested_admin.formsets.NestedInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        forms = _active_forms(self)
        correct = sum(1 for f in forms if f.cleaned_data.get('is_correct'))
        if len(forms) < MIN_ANSWERS:
            raise ValidationError(f'У вопроса должно быть не меньше {MIN_ANSWERS} вариантов ответа.')
        if len(forms) > MAX_ANSWERS:
            raise ValidationError(f'У вопроса может быть не больше {MAX_ANSWERS} вариантов ответа.')
        if correct == 0:
            raise ValidationError('Отметьте хотя бы один правильный ответ.')
        if getattr(self.instance, 'qtype', 'single') == 'single' and correct > 1:
            raise ValidationError(
                'У вопроса с одним правильным ответом отмечено несколько правильных. '
                'Оставьте один или выберите тип «Несколько правильных ответов».'
            )


class QuestionInlineFormSet(nested_admin.formsets.NestedInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        count = len(_active_forms(self))
        if count < 1:
            raise ValidationError('Добавьте в тест хотя бы один вопрос.')
        if count > MAX_QUESTIONS:
            raise ValidationError(f'В тесте может быть не больше {MAX_QUESTIONS} вопросов.')


class AnswerInline(nested_admin.NestedTabularInline):
    model = Answer
    formset = AnswerInlineFormSet
    sortable_field_name = 'order'
    fields = ('order', 'text', 'is_correct')
    extra = 0
    max_num = MAX_ANSWERS


class QuestionInline(nested_admin.NestedStackedInline):
    model = Question
    formset = QuestionInlineFormSet
    sortable_field_name = 'order'
    fields = ('order', 'text', 'qtype')
    extra = 0
    max_num = MAX_QUESTIONS
    inlines = [AnswerInline]

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'text':
            field.widget.attrs.update({'rows': 2})
        return field


@admin.register(Test)
class TestAdmin(nested_admin.NestedModelAdmin):
    list_display = ('lesson', 'course_title', 'pass_score', 'questions_total')
    list_filter = ('lesson__course',)
    search_fields = ('lesson__title', 'lesson__course__title')
    autocomplete_fields = ('lesson',)
    fields = ('lesson', 'pass_score')
    inlines = [QuestionInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('lesson__course').annotate(_q=Count('questions'))

    @admin.display(description='Курс', ordering='lesson__course__title')
    def course_title(self, obj):
        return obj.lesson.course.title

    @admin.display(description='Вопросов', ordering='_q')
    def questions_total(self, obj):
        return obj._q


# ---------------------------------------------------------------------------
# Записи на курсы и попытки тестов (данные для статистики)
# ---------------------------------------------------------------------------

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'source', 'enrolled_at', 'completed_at')
    list_filter = ('source', 'course')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'course__title')
    autocomplete_fields = ('user', 'course')
    date_hierarchy = 'enrolled_at'

    def save_model(self, request, obj, form, change):
        # Запись, созданную вручную в админке, помечаем как «выдал администратор».
        if not change:
            obj.source = 'admin'
        super().save_model(request, obj, form, change)
        if not change:
            from . import notifications
            notifications.access_granted(obj.user, obj.course, 'admin', request.build_absolute_uri('/'))


@admin.register(TestAttempt)
class TestAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'test', 'score', 'passed', 'created_at')
    list_filter = ('passed', 'test__lesson__course')
    search_fields = ('user__email', 'user__last_name', 'test__lesson__title')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False  # попытки создаются только при прохождении теста

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """Модерация комментариев к урокам (ФТ-30)."""

    list_display = ('short_text', 'user', 'lesson', 'course_title', 'created_at', 'is_hidden')
    list_filter = ('is_hidden', 'created_at', 'lesson__course')
    search_fields = ('text', 'user__email', 'user__first_name', 'user__last_name', 'lesson__title')
    list_editable = ('is_hidden',)
    readonly_fields = ('created_at',)
    actions = ['hide_comments', 'show_comments']

    @admin.display(description='Комментарий')
    def short_text(self, obj):
        return obj.text[:70]

    @admin.display(description='Курс')
    def course_title(self, obj):
        return obj.lesson.course.title

    @admin.action(description='Скрыть выбранные комментарии')
    def hide_comments(self, request, queryset):
        count = queryset.update(is_hidden=True)
        self.message_user(request, f'Скрыто комментариев: {count}.')

    @admin.action(description='Показать выбранные комментарии')
    def show_comments(self, request, queryset):
        count = queryset.update(is_hidden=False)
        self.message_user(request, f'Показано комментариев: {count}.')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Отзывы о курсах (ФТ-31)."""

    list_display = ('course', 'user', 'rating', 'short_text', 'created_at', 'is_hidden')
    list_filter = ('rating', 'is_hidden', 'course')
    search_fields = ('text', 'user__email', 'course__title')
    list_editable = ('is_hidden',)
    readonly_fields = ('created_at',)

    @admin.display(description='Отзыв')
    def short_text(self, obj):
        return obj.text[:70] if obj.text else '—'


@admin.register(AccessCode)
class AccessCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'course', 'note', 'usage', 'expires_at', 'is_active', 'created_at')
    list_filter = ('is_active', 'course')
    search_fields = ('code', 'note', 'course__title')
    autocomplete_fields = ('course',)
    readonly_fields = ('used_count', 'created_at')
    actions = ['disable_codes', 'enable_codes']

    @admin.display(description='Использован')
    def usage(self, obj):
        return f'{obj.used_count} из {obj.max_uses}'

    @admin.action(description='Отключить выбранные коды')
    def disable_codes(self, request, queryset):
        self.message_user(request, f'Отключено кодов: {queryset.update(is_active=False)}', messages.SUCCESS)

    @admin.action(description='Включить выбранные коды')
    def enable_codes(self, request, queryset):
        self.message_user(request, f'Включено кодов: {queryset.update(is_active=True)}', messages.SUCCESS)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Журнал оплат только для чтения: платёж нельзя подправить задним числом."""

    list_display = ('created_at', 'user', 'course', 'amount', 'card_last4')
    list_filter = ('course',)
    search_fields = ('user__email', 'course__title')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
