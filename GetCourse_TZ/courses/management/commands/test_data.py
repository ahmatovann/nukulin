"""Небольшой набор записей для ручной проверки сайта по чек-листу.

Запуск:   python manage.py test_data
Удалить:  python manage.py test_data --clear

Создаёт двух тестовых студентов, их оплаты и записи, комментарии с ответом, отзывы
и набор кодов доступа на все случаи (рабочий, использованный, просроченный, отключённый).
Курсы и ваши настоящие пользователи не меняются. Сначала должны быть курсы (demo_data).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from courses import access
from courses.models import AccessCode, Comment, Course, Enrollment, Payment, Review

PASSWORD = 'Test2026!'
NOTE = 'тестовые данные для проверки'
STUDENTS = [
    ('student1@getcourse.local', 'Айжан', 'Тестова'),
    ('student2@getcourse.local', 'Бакыт', 'Проверов'),
]
CARD = '4242424242424242'


class Command(BaseCommand):
    help = 'Создаёт (или удаляет с --clear) тестовых студентов, оплаты, отзывы и коды доступа.'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Удалить тестовые данные')

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        emails = [email for email, _, _ in STUDENTS]

        if options['clear']:
            users = User.objects.filter(email__in=emails)
            Payment.objects.filter(user__in=users).delete()
            Comment.objects.filter(user__in=users).delete()
            Review.objects.filter(user__in=users).delete()
            n_users = users.delete()[0]
            n_codes = AccessCode.objects.filter(note=NOTE).delete()[0]
            self.stdout.write(f'Удалено записей: {n_users + n_codes}')
            return

        open_courses = [
            c for c in Course.objects.filter(status='published', is_private=False).order_by('title')
            if c.lessons.exists()
        ]
        private = [
            c for c in Course.objects.filter(status='published', is_private=True).order_by('title')
            if c.lessons.exists()
        ]
        if len(open_courses) < 3:
            raise CommandError('Нет курсов с уроками. Сначала выполните: python manage.py demo_data')
        a, b, c = open_courses[:3]

        users = []
        for email, first, last in STUDENTS:
            user, created = User.objects.get_or_create(
                email=email, defaults={'first_name': first, 'last_name': last})
            if created:
                user.set_password(PASSWORD)
                user.save()
            users.append(user)
        s1, s2 = users

        # Коды на все случаи проверки (раздел 10 чек-листа)
        def make_code(code, course, **fields):
            obj, _ = AccessCode.objects.get_or_create(
                code=code, defaults={'course': course, 'note': NOTE, **fields})
            return obj

        make_code('CODE-0001', b, max_uses=1)
        make_code('CODE-GROUP', c, max_uses=3)
        make_code('CODE-USED', c, max_uses=1)
        make_code('CODE-OLD', b, max_uses=5, expires_at=timezone.now() - timedelta(days=1))
        make_code('CODE-OFF', b, max_uses=5, is_active=False)
        if private:
            make_code('CODE-CLOSED', private[0], max_uses=2)

        # Оплаты и записи первого студента, запись по коду у второго (источник «код»)
        for user in users:
            if not Enrollment.objects.filter(user=user, course=a).exists():
                access.pay(user, a, CARD)
        if not Enrollment.objects.filter(user=s1, course=c).exists():
            access.redeem(s1, 'CODE-USED')

        # Комментарий с ответом и отзывы
        lesson = a.lessons.order_by('order').first()
        if not Comment.objects.filter(user=s1, lesson=lesson).exists():
            first = Comment.objects.create(
                user=s1, lesson=lesson, text='Не совсем понял последний пример, объясните, пожалуйста.')
            Comment.objects.create(
                user=s2, lesson=lesson, parent=first, text='Посмотри ещё раз начало урока, там это разбирается.')
        Review.objects.update_or_create(
            user=s1, course=a, defaults={'rating': 5, 'text': 'Всё понятно, уроки идут по порядку.'})
        Review.objects.update_or_create(
            user=s2, course=a, defaults={'rating': 4, 'text': 'Хороший курс, хотелось бы больше практики.'})

        self.stdout.write(self.style.SUCCESS('Готово.'))
        self.stdout.write(f'Студенты (пароль {PASSWORD}): ' + ', '.join(emails))
        self.stdout.write(f'Оплачен курс: «{a.title}» (оба студента)')
        self.stdout.write('Коды: CODE-0001 (на «%s»), CODE-GROUP (на «%s», 3 раза), CODE-USED (уже использован), '
                          'CODE-OLD (просрочен), CODE-OFF (отключён)%s' % (
                              b.title, c.title, ', CODE-CLOSED (закрытый курс)' if private else ''))
