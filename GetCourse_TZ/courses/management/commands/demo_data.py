"""Демо-данные для показа статистики на защите.

Запуск:   python manage.py demo_data
Удалить:  python manage.py demo_data --clear

Создаёт 3 демонстрационных курса с уроками и тестами, 45 демо-пользователей
(e-mail вида demo01@demo.getcourse.kg, пароль Demo2026!), их записи на курсы
и попытки тестов. Ваши собственные курсы и пользователи не изменяются.
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from courses.models import (
    Answer, AttemptAnswer, Category, Course, Enrollment, Lesson, Question, Test, TestAttempt,
)

from ._demo_content import LESSONS

DEMO_DOMAIN = 'demo.getcourse.kg'
DEMO_MARK = 'Демонстрационный курс.'
PASSWORD = 'Demo2026!'

FIRST = ['Айгерим', 'Нурлан', 'Алина', 'Бекзат', 'Мээрим', 'Тимур', 'Асель', 'Эрлан', 'Дарья', 'Азамат',
         'Жибек', 'Руслан', 'Камила', 'Данияр', 'Элина', 'Артём', 'Айжан', 'Максат', 'Сезим', 'Илья',
         'Нурай', 'Канат', 'Адилет', 'Зарина', 'Ислам']
LAST = ['Абдыкадырова', 'Токтогулов', 'Иванова', 'Садыков', 'Осмонова', 'Ким', 'Бакирова', 'Жумабеков',
        'Петрова', 'Сыдыков', 'Мамытова', 'Асанов', 'Орозова', 'Исаев', 'Кадырова', 'Смирнов', 'Темирова',
        'Алиев', 'Шаршеева', 'Ли']

COURSES = [
    ('Программирование', 'Python с нуля', 'beginner', [
        'Введение в Python', 'Переменные и типы', 'Условия if / else', 'Циклы for и while', 'Функции', 'Списки и словари']),
    ('Базы данных', 'SQL для начинающих', 'beginner', [
        'Что такое база данных', 'SELECT и WHERE', 'Сортировка и группировка', 'JOIN — соединение таблиц', 'Изменение данных']),
    ('Веб-разработка', 'HTML и CSS', 'intermediate', [
        'Структура HTML-страницы', 'Текст, ссылки, картинки', 'Основы CSS', 'Flexbox', 'Адаптивная вёрстка']),
]


POSTS = [
    ('Набор на курс «Python с нуля» открыт',
     'Новая группа начинается в понедельник. Заниматься можно в своём темпе: уроки '
     'открываются по очереди, после каждого — короткий тест.\n'
     'Записаться можно прямо сейчас, место закрепляется автоматически.',
     True, 'Python с нуля'),
    ('Как устроено обучение в школе',
     'Каждый курс разбит на уроки. Следующий урок открывается только после того, как сдан '
     'тест предыдущего — так материал не перескакивается и лучше запоминается.\n'
     'Количество попыток не ограничено, засчитывается лучший результат.',
     True, None),
    ('Добавили курс по базам данных',
     'Разбираем таблицы, запросы SELECT, сортировку, группировку и объединение таблиц '
     'через JOIN. Курс пригодится после основ программирования.',
     False, 'SQL для начинающих'),
    ('Три совета, как не бросить курс на середине',
     'Первое: занимайтесь понемногу, но регулярно. Второе: не пропускайте тесты — они '
     'показывают, что материал действительно понят. Третье: возвращайтесь к прошлым '
     'урокам, если что-то забылось.',
     False, None),
    ('Занятия с телефона',
     'Сайт работает на экранах от 360 пикселей: уроки, тесты и прогресс доступны с '
     'телефона так же, как с компьютера.',
     False, None),
]


class Command(BaseCommand):
    help = 'Создаёт (или удаляет с --clear) демо-данные для страницы статистики.'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Удалить демо-данные')

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        if options['clear']:
            from feed.models import Post

            n_posts = Post.objects.filter(title__in=[p[0] for p in POSTS]).delete()[0]
            n_users = User.objects.filter(email__endswith='@' + DEMO_DOMAIN).delete()[0]
            n_courses = Course.objects.filter(description__startswith=DEMO_MARK).delete()[0]
            self.stdout.write(self.style.SUCCESS(
                f'Удалено демо-записей: {n_users + n_courses + n_posts}'
            ))
            return

        rnd = random.Random(2026)
        now = timezone.now()

        courses = []
        for cat_name, title, level, lesson_titles in COURSES:
            if Course.objects.filter(title=title).exists():
                self.stdout.write(f'Курс «{title}» уже есть — пропускаю.')
                continue
            category, _ = Category.objects.get_or_create(name=cat_name)
            course = Course.objects.create(
                title=title, category=category, difficulty=level, status='published',
                description=f'{DEMO_MARK} Курс «{title}»: уроки идут по порядку, после каждого — '
                            f'короткий тест. Следующий урок открывается, когда предыдущий тест сдан.',
                learning_outcomes='\n'.join(lesson_titles[:4]),
                created_at=now - timedelta(weeks=9),
            )
            hard_lesson = rnd.randint(2, len(lesson_titles) - 2)
            for order, lesson_title in enumerate(lesson_titles, start=1):
                material = LESSONS.get(lesson_title, {})
                lesson = Lesson.objects.create(
                    course=course, order=order, title=lesson_title,
                    content=material.get('text', f'Материал урока «{lesson_title}».'),
                )
                test = Test.objects.create(lesson=lesson, pass_score=70)

                questions = material.get('questions')
                if not questions:
                    # Если готовых вопросов для урока нет, создаём заготовки
                    questions = [
                        (f'Вопрос {qn} по теме «{lesson_title}»',
                         'multiple' if qn == 4 else 'single',
                         [(f'Вариант {an}', (an <= 2) if qn == 4 else an == 1)
                          for an in range(1, 5 if qn == 4 else 4)])
                        for qn in range(1, 5)
                    ]

                for qn, (text, qtype, options) in enumerate(questions, start=1):
                    question = Question.objects.create(
                        test=test, order=qn, qtype=qtype, text=text,
                    )
                    for an, (answer_text, is_correct) in enumerate(options, start=1):
                        Answer.objects.create(question=question, order=an,
                                              text=answer_text, is_correct=is_correct)
            courses.append((course, hard_lesson))

        n_posts = self.make_posts()

        if not courses:
            self.stdout.write(f'Новых демо-курсов нет — данные уже созданы. '
                              f'Публикаций в ленте добавлено: {n_posts}.')
            return

        users = []
        for i in range(1, 46):
            email = f'demo{i:02d}@{DEMO_DOMAIN}'
            user, created = User.objects.get_or_create(
                email=email,
                defaults={'first_name': rnd.choice(FIRST), 'last_name': rnd.choice(LAST)},
            )
            if created:
                user.set_password(PASSWORD)
                user.created_at = now - timedelta(days=rnd.randint(10, 70))
                roll = rnd.random()
                user.last_login = (None if roll < 0.06 else
                                   now - timedelta(days=rnd.randint(15, 45)) if roll < 0.3 else
                                   now - timedelta(hours=rnd.randint(1, 13 * 24)))
                user.save()
            users.append(user)

        n_attempts = 0
        for course, hard_lesson in courses:
            lessons = list(course.lessons.order_by('order'))
            questions = {l.pk: list(Question.objects.filter(test__lesson=l).prefetch_related('answers')) for l in lessons}
            errs = {}
            for l in lessons:
                for q in questions[l.pk]:
                    errs[q.pk] = 0.1 + rnd.random() * 0.25 + (0.3 if l.order == hard_lesson and q.order in (2, 4) else 0)
            for user in rnd.sample(users, k=rnd.randint(26, 38)):
                # Интерес к курсу растёт: больше записей в последние недели.
                days_ago = int(56 * (1 - rnd.random() ** 0.7))
                enrolled = now - timedelta(days=days_ago, hours=rnd.randint(0, 23))
                enrollment = Enrollment.objects.create(user=user, course=course, enrolled_at=enrolled)
                moment = enrolled
                stay = rnd.uniform(0.75, 0.97)
                finished = True
                for lesson in lessons:
                    leave_chance = 1 - stay + (0.18 if lesson.order == hard_lesson else 0)
                    if lesson.order > 1 and rnd.random() < leave_chance:
                        finished = False
                        break
                    test = lesson.test
                    passed = False
                    for attempt_no in range(rnd.choice([1, 1, 2, 3])):
                        moment = min(moment + timedelta(hours=rnd.randint(6, 60)), now)
                        results = []
                        for q in questions[lesson.pk]:
                            ok = rnd.random() > errs[q.pk] * (0.7 ** attempt_no)
                            results.append((q, ok))
                        score = round(sum(ok for _, ok in results) * 100 / len(results))
                        passed = score >= test.pass_score
                        attempt = TestAttempt.objects.create(user=user, test=test, score=score, passed=passed,
                                                             created_at=moment)
                        AttemptAnswer.objects.bulk_create(
                            [AttemptAnswer(attempt=attempt, question=q, is_correct=ok) for q, ok in results])
                        n_attempts += 1
                        if passed:
                            break
                    if not passed:
                        finished = False
                        break
                if finished:
                    enrollment.completed_at = moment
                    enrollment.save(update_fields=['completed_at'])

        self.stdout.write(self.style.SUCCESS(
            f'Готово: курсов {len(courses)}, демо-пользователей {len(users)}, попыток тестов {n_attempts}, '
            f'публикаций в ленте {n_posts}. Пароль демо-пользователей: {PASSWORD}'
        ))

    def make_posts(self):
        """Публикации ленты для главной страницы (ФТ-26, ФТ-27, ФТ-28)."""
        from feed.models import Post

        by_title = {course.title: course for course in Course.objects.all()}
        created = 0
        for title, text, pinned, course_title in POSTS:
            if Post.objects.filter(title=title).exists():
                continue
            Post.objects.create(
                title=title,
                text=text,
                pinned=pinned,
                course=by_title.get(course_title),
            )
            created += 1
        return created
