"""Баллы, уровни и рейтинг пользователей. Всё считается из настоящих результатов тестов.

Правила (они же написаны на странице «Моя статистика»):
  * за каждый сданный тест — лучший результат, делённый на 10 (100% = 10 баллов, 80% = 8);
  * за каждый завершённый курс — ещё 50 баллов.
"""
from collections import defaultdict
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Max
from django.utils import timezone

from .models import Enrollment, TestAttempt

POINTS_PER_COURSE = 50
LEADERBOARD_SIZE = 10
LEVELS = [
    (0, 'Новичок'),
    (30, 'Ученик'),
    (100, 'Практик'),
    (250, 'Знаток'),
    (500, 'Мастер'),
]
MONTHS = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']


def level_for(points):
    """Уровень по числу баллов и сколько осталось до следующего."""
    index = max(i for i, (floor, _) in enumerate(LEVELS) if points >= floor)
    floor, name = LEVELS[index]
    result = {'number': index + 1, 'total': len(LEVELS), 'name': name, 'floor': floor}
    if index + 1 < len(LEVELS):
        next_floor, next_name = LEVELS[index + 1]
        span = next_floor - floor
        result.update(
            next_name=next_name, next_floor=next_floor, left=next_floor - points,
            percent=min(100, int((points - floor) * 100 / span)),
        )
    else:
        result.update(next_name=None, next_floor=None, left=0, percent=100)
    return result


def points_table():
    """Словарь {id пользователя: {'points', 'tests', 'courses'}} по всем, кто учится."""
    table = defaultdict(lambda: {'points': 0, 'tests': 0, 'courses': 0})

    best_scores = (
        TestAttempt.objects
        .filter(passed=True, user__is_staff=False)
        .values('user_id', 'test_id')
        .annotate(best=Max('score'))
    )
    for row in best_scores:
        entry = table[row['user_id']]
        entry['points'] += row['best'] // 10
        entry['tests'] += 1

    finished = (
        Enrollment.objects
        .filter(completed_at__isnull=False, user__is_staff=False)
        .values_list('user_id', flat=True)
    )
    for user_id in finished:
        entry = table[user_id]
        entry['points'] += POINTS_PER_COURSE
        entry['courses'] += 1
    return table


def _visible_ranking(table):
    """Список (id, данные) в порядке рейтинга: без скрытых и заблокированных, без нулевых баллов."""
    User = get_user_model()
    hidden = set(User.objects.filter(hide_from_rating=True).values_list('pk', flat=True))
    blocked = set(User.objects.filter(blocked=True).values_list('pk', flat=True))
    rows = [
        (uid, data) for uid, data in table.items()
        if data['points'] > 0 and uid not in hidden and uid not in blocked
    ]
    rows.sort(key=lambda item: (-item[1]['points'], -item[1]['tests'], item[0]))
    return rows


def leaderboard(current_user=None, limit=LEADERBOARD_SIZE):
    """Лучшие пользователи. Если текущий пользователь не вошёл в топ, его строка добавляется отдельно."""
    ranking = _visible_ranking(points_table())
    User = get_user_model()
    wanted = [uid for uid, _ in ranking[:limit]]
    own_position = None
    if current_user is not None:
        for position, (uid, _) in enumerate(ranking, start=1):
            if uid == current_user.pk:
                own_position = position
                if uid not in wanted:
                    wanted.append(uid)
                break
    users = User.objects.in_bulk(wanted)

    def row(position, uid, data):
        user = users[uid]
        return {
            'rank': position,
            'name': f'{user.first_name} {user.last_name[:1]}.'.strip(),
            'points': data['points'],
            'tests': data['tests'],
            'courses': data['courses'],
            'level': level_for(data['points'])['name'],
            'is_me': current_user is not None and uid == current_user.pk,
            'user': user,
        }

    rows = [row(i, uid, data) for i, (uid, data) in enumerate(ranking[:limit], start=1)]
    extra = None
    if own_position and own_position > limit:
        uid, data = ranking[own_position - 1]
        extra = row(own_position, uid, data)
    return rows, extra, len(ranking)


def weekly_activity(user, weeks=8):
    """Сколько тестов сдано по неделям — для столбиков на странице статистики."""
    today = timezone.localdate()
    monday = today - timedelta(days=today.weekday())
    starts = [monday - timedelta(weeks=n) for n in range(weeks - 1, -1, -1)]
    counts = {start: 0 for start in starts}
    since = timezone.make_aware(timezone.datetime.combine(starts[0], timezone.datetime.min.time()))
    for moment in TestAttempt.objects.filter(user=user, passed=True, created_at__gte=since).values_list('created_at', flat=True):
        day = timezone.localtime(moment).date()
        week = day - timedelta(days=day.weekday())
        if week in counts:
            counts[week] += 1
    peak = max(counts.values()) or 1
    return [
        {
            'label': f'{start.day} {MONTHS[start.month - 1]}',
            'count': counts[start],
            'height': round(counts[start] * 100 / peak) if counts[start] else 0,
        }
        for start in starts
    ]


def user_summary(user):
    """Всё для страницы «Моя статистика»."""
    table = points_table()
    mine = table.get(user.pk, {'points': 0, 'tests': 0, 'courses': 0})

    attempts = TestAttempt.objects.filter(user=user)
    best_by_test = attempts.values('test_id').annotate(best=Max('score'))
    scores = [row['best'] for row in best_by_test]
    ranking = _visible_ranking(table)
    place = next((i for i, (uid, _) in enumerate(ranking, start=1) if uid == user.pk), None)

    return {
        'points': mine['points'],
        'tests_passed': mine['tests'],
        'courses_done': mine['courses'],
        'attempts': attempts.count(),
        'average': round(sum(scores) / len(scores)) if scores else None,
        'level': level_for(mine['points']),
        'place': place,
        'participants': len(ranking),
        'hidden': user.hide_from_rating,
        'weeks': weekly_activity(user),
    }
