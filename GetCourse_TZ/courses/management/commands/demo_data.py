"""Демо-данные для показа статистики на защите.

Запуск:   python manage.py demo_data
Удалить:  python manage.py demo_data --clear

Создаёт демонстрационные курсы с уроками и тестами, 45 демо-пользователей
(e-mail вида demo01@demo.getcourse.kg, пароль Demo2026!), их записи на курсы
и попытки тестов. Ваши собственные курсы и пользователи не изменяются.
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from courses.models import (
    Answer, AttemptAnswer, Category, Course, Enrollment, Lesson, Question, Test, TestAttempt,
)

from ._demo_content import LESSONS
from ._demo_courses import COURSES

DEMO_DOMAIN = 'demo.getcourse.kg'
DEMO_MARK = 'Демонстрационный курс.'
PASSWORD = 'Demo2026!'

FIRST = ['Айгерим', 'Нурлан', 'Алина', 'Бекзат', 'Мээрим', 'Тимур', 'Асель', 'Эрлан', 'Дарья', 'Азамат',
         'Жибек', 'Руслан', 'Камила', 'Данияр', 'Элина', 'Артём', 'Айжан', 'Максат', 'Сезим', 'Илья',
         'Нурай', 'Канат', 'Адилет', 'Зарина', 'Ислам']
LAST = ['Абдыкадырова', 'Токтогулов', 'Иванова', 'Садыков', 'Осмонова', 'Ким', 'Бакирова', 'Жумабеков',
        'Петрова', 'Сыдыков', 'Мамытова', 'Асанов', 'Орозова', 'Исаев', 'Кадырова', 'Смирнов', 'Темирова',
        'Алиев', 'Шаршеева', 'Ли']




# Публикации ленты.
# Поля: заголовок, тип, короткое описание, текст, закрепить, курс,
# имя файла фотографии и способ показа (cover — заполнить, contain — вписать целиком).
# Фотографии кладутся в папку static/img/demo/ — если файла нет, рисуется заглушка.
POSTS = [
    (
        'Открыт набор на курс «Дизайн одежды»',
        'announcement',
        'Учимся превращать эскиз в готовое изделие: от идеи до первой коллекции.',
        'Новая группа начинается в декабре. За курс вы пройдёте весь путь: придумать образ, '
        'перенести его на бумагу, построить выкройку и сшить готовое изделие.\n'
        'Опыт в шитье не нужен — начинаем с основ. Нужна только швейная машинка, '
        'список остальных материалов пришлём после записи.\n'
        'Занятия идут в своём темпе: уроки открываются по очереди, после каждого — '
        'короткое задание на проверку.',
        True, None, 'feed-moda.png', 'contain',
    ),
    (
        'Как устроено обучение в школе',
        'news',
        'Уроки открываются по очереди, а переход к следующему — только после теста.',
        'Каждый курс разбит на уроки, и они открываются по порядку. Следующий урок '
        'становится доступен только после того, как сдан тест предыдущего.\n'
        'Так материал не перескакивается: к новой теме вы приходите, уже разобравшись '
        'с предыдущей. Количество попыток в тесте не ограничено, засчитывается лучший '
        'результат — ошибиться не страшно.\n'
        'Свой прогресс по каждому курсу видно в разделе «Мои курсы»: сколько уроков '
        'пройдено, сколько осталось и какой процент курса позади.',
        True, None, 'feed-obuchenie.png', 'contain',
    ),
    (
        'Новый курс: архитектурный скетчинг',
        'announcement',
        'Быстрый рисунок от руки — как показать идею заказчику за пять минут.',
        'Запускаем курс для тех, кто хочет научиться быстро рисовать здания и интерьеры '
        'от руки. Такой навык нужен архитекторам и дизайнерам: идею гораздо проще '
        'объяснить рисунком, чем словами.\n'
        'Разберём перспективу, свет и тень, фактуры материалов, работу линером и '
        'маркерами. Никакой специальной подготовки не требуется.',
        False, None, 'feed-arhitektura.jpg', 'cover',
    ),
    (
        'Группа «Python с нуля» стартует в понедельник',
        'announcement',
        'Курс для тех, кто никогда не программировал. Места ещё есть.',
        'В понедельник открывается новая группа курса «Python с нуля». Это курс для '
        'полных новичков: начинаем с первой программы и доходим до списков и словарей.\n'
        'Записаться можно прямо сейчас — место закрепляется автоматически, и первый '
        'урок открывается сразу после записи.',
        False, 'Python с нуля', 'feed-python.jpg', 'cover',
    ),
    (
        'Три совета, как не бросить курс на середине',
        'tip',
        'Понемногу, но регулярно — и не пропускать тесты.',
        'Первое: занимайтесь понемногу, но регулярно. Полчаса каждый день дают больше, '
        'чем пять часов раз в неделю.\n'
        'Второе: не пропускайте тесты. Они не для оценки, а для вас: показывают, '
        'действительно ли тема понята или только кажется понятной.\n'
        'Третье: возвращайтесь к прошлым урокам, если что-то забылось. Пройденные уроки '
        'остаются открытыми навсегда.',
        False, None, 'feed-sovety.png', 'contain',
    ),
    (
        'Занимайтесь с телефона',
        'news',
        'Уроки, тесты и прогресс одинаково удобны на компьютере и на телефоне.',
        'Сайт рассчитан на экраны от 360 точек в ширину. Уроки, тесты и прогресс '
        'открываются с телефона так же, как с компьютера — ничего не уезжает и не '
        'приходится увеличивать текст пальцами.\n'
        'Прогресс общий: начали урок на компьютере, продолжили в транспорте с телефона.',
        False, None, 'feed-telefon.jpg', 'contain',
    ),
]


# Заголовки публикаций из прежней версии демо-данных — удаляются вместе с остальным,
# чтобы после обновления в ленте не оставалось дублей.
OLD_POST_TITLES = [
    'Набор на курс «Python с нуля» открыт',
    'Как устроено обучение в школе',
    'Добавили курс по базам данных',
    'Три совета, как не бросить курс на середине',
    'Занятия с телефона',
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

            titles = [post[0] for post in POSTS] + OLD_POST_TITLES
            n_posts = Post.objects.filter(title__in=titles).delete()[0]
            n_users = User.objects.filter(email__endswith='@' + DEMO_DOMAIN).delete()[0]
            course_titles = [item['title'] for item in COURSES]
            n_courses = Course.objects.filter(
                Q(title__in=course_titles) | Q(description__startswith=DEMO_MARK)
            ).delete()[0]
            self.stdout.write(self.style.SUCCESS(
                f'Удалено демо-записей: {n_users + n_courses + n_posts}'
            ))
            return

        rnd = random.Random(2026)
        now = timezone.now()

        courses = []
        for index, data in enumerate(COURSES):
            title = data['title']
            if Course.objects.filter(title=title).exists():
                self.stdout.write(f'Курс «{title}» уже есть — пропускаю.')
                continue

            category, _ = Category.objects.get_or_create(name=data['category'])
            course = Course.objects.create(
                title=title,
                category=category,
                difficulty=data['difficulty'],
                status='published',
                description=data['description'],
                learning_outcomes=data['outcomes'],
                # Курсы добавлялись в разное время — так каталог выглядит живым
                created_at=now - timedelta(weeks=9, days=-index * 2),
            )

            lessons_data = data['lessons']
            hard_lesson = rnd.randint(2, max(2, len(lessons_data) - 1))

            for order, item in enumerate(lessons_data, start=1):
                # Урок задан строкой — текст и вопросы берём из _demo_content.py
                if isinstance(item, str):
                    material = LESSONS.get(item, {})
                    lesson_title = item
                    content = material.get('text', f'Материал урока «{item}».')
                    questions = material.get('questions') or []
                else:
                    lesson_title, content, questions = item

                lesson = Lesson.objects.create(
                    course=course, order=order, title=lesson_title, content=content,
                )
                test = Test.objects.create(lesson=lesson, pass_score=70)

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
            for user in rnd.sample(users, k=rnd.randint(4, 18)):
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
        from django.conf import settings
        from django.core.files import File

        from feed.models import Post

        photo_dir = settings.BASE_DIR / 'static' / 'img' / 'demo'
        by_title = {course.title: course for course in Course.objects.all()}
        created = 0

        now = timezone.now()
        for index, (title, kind, summary, text, pinned, course_title, photo, fit) in enumerate(POSTS):
            if Post.objects.filter(title=title).exists():
                continue
            post = Post.objects.create(
                title=title, kind=kind, summary=summary, text=text,
                pinned=pinned, course=by_title.get(course_title), image_fit=fit,
            )
            # Если фотография положена в static/img/demo/, прикрепляем её к публикации
            source = photo_dir / photo
            if source.exists():
                with source.open('rb') as handle:
                    post.image.save(photo, File(handle), save=True)
            # Дату проставляем последней: сохранение фотографии вернуло бы старую
            Post.objects.filter(pk=post.pk).update(
                created_at=now - timedelta(days=index * 2)
            )
            created += 1
        return created

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
