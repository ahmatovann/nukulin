"""Расчёт статистики курса для администратора (UC-18, ФТ-22, ФТ-24).

Всё считается несколькими запросами к базе и затем в Python,
чтобы страница открывалась быстро и при 1000 пользователей.
"""
from collections import Counter, defaultdict
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from .models import AttemptAnswer, Enrollment, TestAttempt

INACTIVE_DAYS = 14          # ФТ-22: не заходили больше 14 дней
MIN_ATTEMPTS_FOR_HARD = 10  # UC-18, 4а: блок сложных вопросов — от 10 попыток
HARD_QUESTIONS = 5
WEEKS = 8


def _pct(part, whole):
    return round(part * 100 / whole) if whole else 0


def course_stats(course):
    now = timezone.now()
    lessons = list(course.lessons.order_by('order').select_related('test'))
    lesson_tests = [getattr(lesson, 'test', None) if hasattr(lesson, 'test') else None for lesson in lessons]
    test_ids = [t.pk for t in lesson_tests if t]

    enrollments = list(
        Enrollment.objects.filter(course=course).select_related('user').order_by('user__last_name', 'user__first_name')
    )
    if not enrollments:
        return {'has_data': False, 'lessons': lessons}

    user_ids = [e.user_id for e in enrollments]
    attempts = list(
        TestAttempt.objects.filter(test_id__in=test_ids, user_id__in=user_ids)
        .values('user_id', 'test_id', 'score', 'passed')
    )

    best = {}                     # (user, test) -> лучший балл
    passed = set()                # (user, test), сданные
    attempts_by_test = defaultdict(list)
    users_by_test = defaultdict(set)
    for a in attempts:
        key = (a['user_id'], a['test_id'])
        best[key] = max(best.get(key, 0), a['score'])
        if a['passed']:
            passed.add(key)
        attempts_by_test[a['test_id']].append(a['score'])
        users_by_test[a['test_id']].add(a['user_id'])

    # Прогресс каждого пользователя: сколько уроков подряд пройдено с начала курса.
    def lesson_done(user_id, test):
        return test is None or (user_id, test.pk) in passed

    n_lessons = len(lessons)
    rows = []
    streak_counter = Counter()
    for e in enrollments:
        streak = 0
        for test in lesson_tests:
            if lesson_done(e.user_id, test):
                streak += 1
            else:
                break
        streak_counter[streak] += 1
        scores = [best[(e.user_id, t.pk)] for t in lesson_tests if t and (e.user_id, t.pk) in best]
        last_login = e.user.last_login
        inactive = last_login is None or last_login < now - timedelta(days=INACTIVE_DAYS)
        rows.append({
            'user': e.user,
            'enrolled_at': e.enrolled_at,
            'progress': _pct(streak, n_lessons),
            'done': streak,
            'current': lessons[streak].title if streak < n_lessons else 'Курс завершён',
            'completed': n_lessons > 0 and streak == n_lessons,
            'avg_best': round(sum(scores) / len(scores)) if scores else None,
            'last_login': last_login,
            'inactive': inactive,
            'days_away': (now - last_login).days if last_login else None,
        })

    total = len(enrollments)
    completed = sum(1 for r in rows if r['completed'])
    in_progress = sum(1 for r in rows if not r['completed'] and r['done'] > 0)
    not_started = total - completed - in_progress

    # Воронка: сколько пользователей дошло до каждого урока
    # (до урока k доходит тот, кто сдал тесты всех предыдущих уроков).
    funnel = []
    for index, lesson in enumerate(lessons):
        reached = sum(count for streak, count in streak_counter.items() if streak >= index)
        funnel.append({
            'number': index + 1,
            'title': lesson.title,
            'reached': reached,
            'pct': _pct(reached, total),
        })
    for i, step in enumerate(funnel):
        prev = funnel[i - 1]['reached'] if i else total
        step['drop'] = prev - step['reached']
    max_drop = max((s['drop'] for s in funnel[1:]), default=0)
    for i, step in enumerate(funnel):
        step['is_max_drop'] = i > 0 and max_drop > 0 and step['drop'] == max_drop

    # Тесты: средний балл и среднее число попыток.
    tests = []
    for index, (lesson, test) in enumerate(zip(lessons, lesson_tests)):
        if not test:
            continue
        scores = attempts_by_test.get(test.pk, [])
        users = users_by_test.get(test.pk, set())
        tests.append({
            'number': index + 1,
            'title': lesson.title,
            'pass_score': test.pass_score,
            'avg_score': round(sum(scores) / len(scores)) if scores else None,
            'avg_attempts': round(len(scores) / len(users), 1) if users else None,
            'attempts': len(scores),
            'pass_rate': _pct(sum(1 for u in users if (u, test.pk) in passed), len(users)),
        })
    max_attempts = max((t['avg_attempts'] or 0 for t in tests), default=0)

    # Сложные вопросы: только если попыток не меньше 10.
    total_attempts = len(attempts)
    hard = []
    if total_attempts >= MIN_ATTEMPTS_FOR_HARD:
        qs = (
            AttemptAnswer.objects.filter(attempt__test_id__in=test_ids, attempt__user_id__in=user_ids)
            .values('question_id', 'question__text', 'question__test__lesson__order', 'is_correct')
            .annotate(n=Count('id'))
        )
        per_q = defaultdict(lambda: {'total': 0, 'wrong': 0, 'text': '', 'lesson': 0})
        for row in qs:
            q = per_q[row['question_id']]
            q['text'] = row['question__text']
            q['lesson'] = row['question__test__lesson__order']
            q['total'] += row['n']
            if not row['is_correct']:
                q['wrong'] += row['n']
        hard = sorted(
            ({'text': q['text'], 'lesson': q['lesson'], 'answers': q['total'], 'error_pct': _pct(q['wrong'], q['total'])}
             for q in per_q.values() if q['total']),
            key=lambda q: (-q['error_pct'], -q['answers']),
        )[:HARD_QUESTIONS]

    # Записи по неделям за последние 8 недель (динамика интереса к курсу).
    start = (now - timedelta(weeks=WEEKS - 1)).date()
    start = start - timedelta(days=start.weekday())
    weekly = Counter()
    for e in enrollments:
        d = timezone.localtime(e.enrolled_at).date()
        if d >= start:
            weekly[(d - start).days // 7] += 1
    weeks = []
    for i in range(WEEKS):
        week_start = start + timedelta(weeks=i)
        weeks.append({'label': week_start.strftime('%d.%m'), 'count': weekly.get(i, 0),
                      'range': f"{week_start:%d.%m}–{week_start + timedelta(days=6):%d.%m}"})
    max_week = max((w['count'] for w in weeks), default=0)
    for w in weeks:
        w['pct'] = _pct(w['count'], max_week) if max_week else 0

    inactive_rows = sorted((r for r in rows if r['inactive']), key=lambda r: -(r['days_away'] or 10_000))

    return {
        'has_data': True,
        'lessons': lessons,
        'total': total,
        'avg_progress': round(sum(r['progress'] for r in rows) / total),
        'completed': completed,
        'completed_pct': _pct(completed, total),
        'in_progress': in_progress,
        'in_progress_pct': _pct(in_progress, total),
        'not_started': not_started,
        'not_started_pct': _pct(not_started, total),
        'inactive_count': len(inactive_rows),
        'inactive': inactive_rows,
        'rows': rows,
        'funnel': funnel,
        'tests': tests,
        'max_attempts': max_attempts,
        'hard': hard,
        'hard_available': total_attempts >= MIN_ATTEMPTS_FOR_HARD,
        'total_attempts': total_attempts,
        'weeks': weeks,
        'week_total': sum(w['count'] for w in weeks),
    }
