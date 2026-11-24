"""Автоматические тесты доступа к курсам и уведомлений в Telegram.

Запуск:  python manage.py test courses
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.management.commands.run_bot import Command as BotCommand

from . import access, notifications
from .models import AccessCode, Category, Comment, Course, Enrollment, Lesson, Payment, Test


def make_course(title='Курс', price=1000, private=False):
    course = Course.objects.create(
        title=title, description='Описание', category=Category.objects.get_or_create(name='Тема')[0],
        status='published', price=price, is_private=private,
    )
    lesson = Lesson.objects.create(course=course, order=1, title='Урок 1', content='Текст')
    Test.objects.create(lesson=lesson, pass_score=70)
    return course


class AccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='u@test.kg', password='Strong-pass-1', first_name='Аня', last_name='Тестова')
        self.course = make_course()

    def test_course_without_price_is_not_valid(self):
        from django.core.exceptions import ValidationError
        course = Course(title='Бесплатный', description='x', category=self.course.category, price=0)
        with self.assertRaises(ValidationError):
            course.full_clean()

    def test_payment_enrolls_and_logs_only_last4(self):
        access.pay(self.user, self.course, '4242424242424242')
        self.assertTrue(Enrollment.objects.filter(user=self.user, course=self.course, source='payment').exists())
        payment = Payment.objects.get()
        self.assertEqual(payment.card_last4, '4242')
        self.assertEqual(int(payment.amount), 1000)

    def test_cannot_pay_twice_for_same_course(self):
        access.pay(self.user, self.course, '4242424242424242')
        with self.assertRaises(access.AccessError):
            access.pay(self.user, self.course, '4242424242424242')
        self.assertEqual(Payment.objects.count(), 1)

    def test_course_without_lessons_cannot_be_joined(self):
        empty = Course.objects.create(
            title='Пустой', description='x', category=self.course.category, status='published', price=500)
        with self.assertRaises(access.AccessError):
            access.pay(self.user, empty, '4242424242424242')

    def test_code_is_case_insensitive_and_counts_uses(self):
        code = AccessCode.objects.create(course=self.course, max_uses=2)
        access.redeem(self.user, code.code.lower())
        code.refresh_from_db()
        self.assertEqual(code.used_count, 1)
        self.assertTrue(Enrollment.objects.filter(user=self.user, source='code').exists())

    def test_one_use_code_cannot_be_reused(self):
        code = AccessCode.objects.create(course=self.course, max_uses=1)
        other = get_user_model().objects.create_user(email='o@test.kg', password='Strong-pass-1')
        access.redeem(self.user, code.code)
        with self.assertRaisesMessage(access.AccessError, 'уже использован'):
            access.redeem(other, code.code)

    def test_expired_and_disabled_codes_are_rejected(self):
        expired = AccessCode.objects.create(course=self.course, expires_at=timezone.now() - timedelta(days=1))
        with self.assertRaisesMessage(access.AccessError, 'Срок'):
            access.redeem(self.user, expired.code)
        disabled = AccessCode.objects.create(course=self.course, is_active=False)
        with self.assertRaisesMessage(access.AccessError, 'отключён'):
            access.redeem(self.user, disabled.code)

    def test_code_for_another_course_does_not_work_here(self):
        other_course = make_course('Другой')
        code = AccessCode.objects.create(course=other_course)
        with self.assertRaises(access.AccessError):
            access.redeem(self.user, code.code, course=self.course)

    def test_private_course_hidden_from_catalog_but_open_by_link(self):
        private = make_course('Секретный', private=True)
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get('/catalog/'), 'Секретный')
        self.assertEqual(self.client.get(f'/course/{private.pk}/').status_code, 200)
        self.assertContains(self.client.get(f'/course/{private.pk}/access/'), 'Оплата курса')

    def test_enroll_endpoint_never_enrolls_for_free(self):
        self.client.force_login(self.user)
        self.client.post(f'/course/{self.course.pk}/enroll/')
        self.assertFalse(Enrollment.objects.exists())


class TelegramTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='t@test.kg', password='Strong-pass-1', first_name='Аня', last_name='Тестова')
        self.user.telegram_chat_id = 777
        self.user.save()
        self.course = make_course()

    def test_no_message_when_telegram_not_linked(self):
        stranger = get_user_model().objects.create_user(email='s@test.kg', password='Strong-pass-1')
        with mock.patch('accounts.telegram.send_message') as send:
            notifications.access_granted(stranger, self.course, 'payment')
        send.assert_not_called()

    def test_message_sent_after_access(self):
        with mock.patch('accounts.telegram.send_message', return_value=True) as send:
            notifications.access_granted(self.user, self.course, 'code', 'http://site/')
        self.assertEqual(send.call_args.args[0], 777)
        self.assertIn(self.course.title, send.call_args.args[1])

    def test_reply_notifies_author_of_comment_only(self):
        lesson = self.course.lessons.first()
        other = get_user_model().objects.create_user(
            email='r@test.kg', password='Strong-pass-1', first_name='Бек', last_name='Ответов')
        parent = Comment.objects.create(lesson=lesson, user=self.user, text='Вопрос по уроку')
        reply = Comment.objects.create(lesson=lesson, user=other, parent=parent, text='Вот ответ')
        with mock.patch('accounts.telegram.send_message', return_value=True) as send:
            notifications.comment_reply(reply, 'http://site/')
            own = Comment.objects.create(lesson=lesson, user=self.user, parent=parent, text='Сам себе')
            notifications.comment_reply(own, 'http://site/')
        self.assertEqual(send.call_count, 1)

    def bot_say(self, text, chat_id=777):
        sent = []
        bot = BotCommand()
        bot.reply = lambda chat, message: sent.append(message)
        bot.handle_message({'chat': {'id': chat_id}, 'text': text, 'from': {}})
        return sent[0]

    def test_bot_code_command_opens_course(self):
        code = AccessCode.objects.create(course=self.course)
        answer = self.bot_say(f'/code {code.code}')
        self.assertIn('открыт', answer)
        self.assertTrue(Enrollment.objects.filter(user=self.user, course=self.course).exists())

    def test_bot_code_command_wrong_code(self):
        self.assertIn('Такого кода нет', self.bot_say('/code NOPE-0000'))

    def test_bot_my_lists_courses(self):
        Enrollment.objects.create(user=self.user, course=self.course, source='admin')
        self.assertIn(self.course.title, self.bot_say('/my'))

    def test_bot_commands_need_linked_account(self):
        self.assertIn('подключите аккаунт', self.bot_say('/my', chat_id=999).lower())


class RatingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.anna = User.objects.create_user(email='a@test.kg', password='Strong-pass-1', first_name='Анна', last_name='Ким')
        self.bek = User.objects.create_user(email='b@test.kg', password='Strong-pass-1', first_name='Бек', last_name='Осмонов')
        self.course = make_course()
        self.test = self.course.lessons.first().test

    def attempt(self, user, score, passed=True):
        from .models import TestAttempt
        return TestAttempt.objects.create(user=user, test=self.test, score=score, passed=passed)

    def test_points_use_only_best_passed_attempt(self):
        from . import rating
        self.attempt(self.anna, 70)
        self.attempt(self.anna, 90)
        self.attempt(self.anna, 100, passed=False)  # несданная попытка баллов не даёт
        entry = rating.points_table()[self.anna.pk]
        self.assertEqual(entry['points'], 9)
        self.assertEqual(entry['tests'], 1)

    def test_completed_course_gives_bonus(self):
        from . import rating
        self.attempt(self.anna, 80)
        Enrollment.objects.create(user=self.anna, course=self.course, source='payment', completed_at=timezone.now())
        self.assertEqual(rating.points_table()[self.anna.pk]['points'], 8 + rating.POINTS_PER_COURSE)

    def test_levels(self):
        from . import rating
        self.assertEqual(rating.level_for(0)['name'], 'Новичок')
        self.assertEqual(rating.level_for(30)['name'], 'Ученик')
        self.assertEqual(rating.level_for(499)['name'], 'Знаток')
        top = rating.level_for(999)
        self.assertEqual(top['name'], 'Мастер')
        self.assertIsNone(top['next_name'])

    def test_leaderboard_order_and_privacy(self):
        from . import rating
        self.attempt(self.anna, 100)
        self.attempt(self.bek, 80)
        rows, own, total = rating.leaderboard(self.bek)
        self.assertEqual([r['name'] for r in rows], ['Анна К.', 'Бек О.'])
        self.assertEqual(total, 2)
        self.anna.hide_from_rating = True
        self.anna.save()
        rows, _, total = rating.leaderboard(self.bek)
        self.assertEqual([r['name'] for r in rows], ['Бек О.'])
        self.assertEqual(total, 1)

    def test_blocked_and_zero_point_users_not_ranked(self):
        from . import rating
        self.attempt(self.anna, 90)
        self.anna.blocked = True
        self.anna.save()
        _, _, total = rating.leaderboard(self.bek)
        self.assertEqual(total, 0)

    def test_pages_open(self):
        self.client.force_login(self.anna)
        self.assertContains(self.client.get('/stats/'), 'Моя статистика')
        self.client.logout()
        self.assertContains(self.client.get('/help/'), 'Как пользоваться GetCourse')
        self.assertEqual(self.client.get('/stats/').status_code, 302)


class SessionTests(TestCase):
    def test_session_ends_after_two_hours_of_inactivity(self):
        """НФТ-13: сеанс живёт 2 часа и продлевается при каждом действии."""
        from django.conf import settings
        self.assertEqual(settings.SESSION_COOKIE_AGE, 2 * 60 * 60)
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)
