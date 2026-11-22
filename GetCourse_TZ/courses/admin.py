from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from .models import Category, Course, Lesson, LessonFile

MAX_LESSONS = 50

admin.site.site_header = 'GetCourse — администрирование'
admin.site.site_title = 'GetCourse'
admin.site.index_title = 'Управление системой'


class LessonInlineFormSet(BaseInlineFormSet):
    """Правила ТЗ: в курсе от 1 до 50 уроков, курс без уроков нельзя опубликовать."""

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        count = 0
        for form in self.forms:
            data = getattr(form, 'cleaned_data', None)
            if not data or data.get('DELETE'):
                continue
            count += 1

        if count > MAX_LESSONS:
            raise ValidationError(f'В курсе может быть не больше {MAX_LESSONS} уроков.')

        if self.instance.status == 'published' and count == 0:
            raise ValidationError(
                'Нельзя опубликовать курс без уроков. '
                'Добавьте хотя бы один урок или оставьте статус «Черновик».'
            )


class LessonInline(admin.StackedInline):
    model = Lesson
    formset = LessonInlineFormSet
    extra = 1
    max_num = MAX_LESSONS
    ordering = ('order',)
    fields = ('order', 'title', 'content', 'video_url')
    show_change_link = True  # ссылка на страницу урока, где прикрепляются файлы


class LessonFileInline(admin.TabularInline):
    model = LessonFile
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'difficulty', 'status', 'lessons_total', 'created_at')
    list_filter = ('status', 'difficulty', 'category')
    search_fields = ('title', 'description')
    fieldsets = (
        (None, {'fields': ('title', 'category', 'difficulty', 'status')}),
        ('Описание', {'fields': ('description', 'learning_outcomes', 'cover_image')}),
    )
    inlines = [LessonInline]
    actions = ['publish_courses', 'make_draft']

    @admin.display(description='Уроков')
    def lessons_total(self, obj):
        return obj.lessons.count()

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
    list_display = ('title', 'course', 'order')
    list_filter = ('course',)
    search_fields = ('title', 'course__title')
    ordering = ('course', 'order')
    inlines = [LessonFileInline]

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
        # Опубликованный курс без уроков возвращается в черновики.
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
