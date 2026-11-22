"""Прохождение курса: какие уроки открыты, сколько пройдено (ФТ-10, ФТ-15, ФТ-16).

Правило из ТЗ: первый урок открыт сразу после записи, каждый следующий
открывается только после сдачи теста предыдущего. Урок без теста отдельного
подтверждения не требует и считается пройденным.

По этому же правилу считает статистика администратора (courses/stats.py),
поэтому прогресс на странице пользователя и цифры в отчёте совпадают.
"""
from .models import TestAttempt

# Состояния урока
DONE = 'done'        # урок пройден
CURRENT = 'current'  # доступен сейчас
LOCKED = 'locked'    # закрыт, нужно сдать тест предыдущего урока


def passed_test_ids(user, course):
    """Тесты курса, которые пользователь уже сдал."""
    if not user.is_authenticated:
        return set()
    return set(
        TestAttempt.objects
        .filter(user=user, passed=True, test__lesson__course=course)
        .values_list('test_id', flat=True)
    )


def build_track(user, course, lessons=None):
    """Список уроков курса с состоянием каждого.

    Возвращает список словарей: lesson, test, state, is_open, number.
    """
    if lessons is None:
        lessons = list(course.lessons.order_by('order').select_related('test'))

    passed = passed_test_ids(user, course)

    track = []
    previous_done = True
    for number, lesson in enumerate(lessons, start=1):
        test = getattr(lesson, 'test', None)
        done = test is None or test.pk in passed

        if done:
            state = DONE
        elif previous_done:
            state = CURRENT
        else:
            state = LOCKED

        track.append({
            'number': number,
            'lesson': lesson,
            'test': test,
            'state': state,
            'is_open': state in (DONE, CURRENT),
            'is_done': done,
            'is_locked': state == LOCKED,
        })
        previous_done = done

    return track


def track_summary(track):
    """Сколько уроков пройдено подряд с начала курса и сколько это в процентах."""
    total = len(track)
    done = 0
    for item in track:
        if item['is_done']:
            done += 1
        else:
            break

    return {
        'total': total,
        'done': done,
        'percent': round(done * 100 / total) if total else 0,
        'completed': total > 0 and done == total,
        'next_item': next((item for item in track if item['state'] == CURRENT), None),
    }


def course_progress(user, course):
    """Краткий прогресс пользователя по курсу — для списка «Мои курсы»."""
    return track_summary(build_track(user, course))


def lesson_state(user, lesson):
    """Состояние одного урока и его место в курсе."""
    track = build_track(user, lesson.course)
    for index, item in enumerate(track):
        if item['lesson'].pk == lesson.pk:
            return {
                'track': track,
                'item': item,
                'index': index,
                'previous': track[index - 1]['lesson'] if index > 0 else None,
                'next_item': track[index + 1] if index + 1 < len(track) else None,
                'summary': track_summary(track),
            }
    return None
