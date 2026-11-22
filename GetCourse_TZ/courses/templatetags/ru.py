"""Склонение слов после числа по-русски.

Встроенный фильтр Django pluralize рассчитан на английский язык и понимает
только две формы, поэтому для русского нужен свой фильтр.

Пример:  {{ n }} {{ n|plural:"урок,урока,уроков" }}  →  1 урок, 3 урока, 5 уроков
"""
from django import template

register = template.Library()


@register.filter
def plural(value, forms):
    """Выбирает форму слова по числу: один, два-четыре, пять и больше."""
    try:
        number = abs(int(value))
    except (TypeError, ValueError):
        return ''

    parts = [part.strip() for part in forms.split(',')]
    if len(parts) != 3:
        return parts[-1] if parts else ''
    one, few, many = parts

    if number % 100 in (11, 12, 13, 14):
        return many
    last = number % 10
    if last == 1:
        return one
    if last in (2, 3, 4):
        return few
    return many
