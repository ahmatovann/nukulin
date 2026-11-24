"""Выдача доступа к курсу: оплата и код. Общая логика для сайта и Telegram-бота."""
from django.db import transaction
from django.db.models import F

from .models import AccessCode, Enrollment, Payment


class AccessError(Exception):
    """Доступ выдать нельзя. Текст ошибки показывается пользователю как есть."""


def enroll(user, course, source):
    """Создаёт запись на курс. Возвращает (запись, создана_ли_сейчас)."""
    return Enrollment.objects.get_or_create(user=user, course=course, defaults={'source': source})


def check_can_join(user, course):
    if course.status != 'published':
        raise AccessError('Этот курс сейчас недоступен.')
    if Enrollment.objects.filter(user=user, course=course).exists():
        raise AccessError(f'Вы уже записаны на курс «{course.title}».')
    if not course.lessons.exists():
        raise AccessError('В этом курсе пока нет уроков, получить доступ нельзя.')


def pay(user, course, card_number):
    """Учебная оплата: деньги не списываются, в журнал идут только последние 4 цифры карты."""
    check_can_join(user, course)
    with transaction.atomic():
        payment = Payment.objects.create(
            user=user, course=course, amount=course.price, card_last4=card_number[-4:],
        )
        enroll(user, course, 'payment')
    return payment


def redeem(user, code, course=None):
    """Применяет код доступа и возвращает курс.

    Если курс не указан, он определяется по коду (так открываются закрытые курсы).
    Блокировка строки не даёт двум людям занять последнее место одновременно.
    """
    code = (code or '').strip().upper()
    with transaction.atomic():
        query = AccessCode.objects.select_for_update().select_related('course').filter(code=code)
        if course is not None:
            query = query.filter(course=course)
        access = query.first()
        if access is None:
            raise AccessError('Такого кода нет. Проверьте, нет ли опечатки.')
        check_can_join(user, access.course)
        problem = access.problem()
        if problem:
            raise AccessError(problem)
        AccessCode.objects.filter(pk=access.pk).update(used_count=F('used_count') + 1)
        enroll(user, access.course, 'code')
    return access.course
