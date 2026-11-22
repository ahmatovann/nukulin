"""Расчёт популярных курсов недели (ФТ-27)."""
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

POPULAR_COUNT = 5
POPULAR_DAYS = 7


def popular_courses_of_week():
    """Пять курсов с наибольшим числом записей за последние 7 дней.

    Если за неделю записей не было, возвращаются пять последних добавленных курсов.
    У каждого курса появляется поле week_enrollments — сколько человек записалось.
    """
    from courses.models import Course

    since = timezone.now() - timedelta(days=POPULAR_DAYS)
    published = Course.objects.filter(status='published')

    popular = list(
        published
        .annotate(
            week_enrollments=Count(
                'enrollments',
                filter=Q(enrollments__enrolled_at__gte=since),
                distinct=True,
            )
        )
        .filter(week_enrollments__gt=0)
        .order_by('-week_enrollments', '-created_at')[:POPULAR_COUNT]
    )
    if popular:
        return popular

    # Записей за неделю не было — показываем последние добавленные курсы
    fallback = list(published.order_by('-created_at')[:POPULAR_COUNT])
    for course in fallback:
        course.week_enrollments = 0
    return fallback
