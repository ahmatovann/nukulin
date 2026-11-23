"""Страницы для гостя и пользователя: лента, каталог, курс, уроки, тесты."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from feed.models import Post
from feed.services import popular_courses_of_week

from .models import Answer, AttemptAnswer, Category, Course, Enrollment, Lesson, Test, TestAttempt
from .progress import build_track, course_progress, lesson_state, track_summary

FEED_LIMIT = 10


def home(request):
    """Главная: лента анонсов и популярные курсы недели (ФТ-26, ФТ-27, UC-1)."""
    # Первая публикация показывается крупно, остальные — карточками разного
    # размера: две узкие рядом, затем одна во всю ширину, и так по кругу.
    posts = list(Post.objects.select_related('course')[:FEED_LIMIT])
    rest = posts[1:]
    for index, post in enumerate(rest):
        post.layout = 'wide' if index % 3 == 2 else 'tall'

    context = {
        'hero_post': posts[0] if posts else None,
        'posts': rest,
        'posts_total': len(posts),
        'popular_courses': popular_courses_of_week(),
    }

    if request.user.is_staff:
        context['counts'] = {
            'courses': Course.objects.count(),
            'drafts': Course.objects.filter(status='draft').count(),
            'categories': Category.objects.count(),
            'users': request.user.__class__.objects.filter(is_staff=False).count(),
            'enrollments': Enrollment.objects.count(),
        }

    return render(request, 'courses/home.html', context)


# ---------------------------------------------------------------------------
# Каталог и страница курса
# ---------------------------------------------------------------------------

def catalog(request):
    """Каталог опубликованных курсов с поиском и фильтрами (ФТ-1, ФТ-2, UC-2, UC-3)."""
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()
    difficulty = request.GET.get('difficulty', '').strip()

    courses = (
        Course.objects
        .filter(status='published')
        .select_related('category')
        .prefetch_related('lessons')
        .annotate(lessons_total=Count('lessons', distinct=True))
    )

    if query:
        courses = courses.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
    if category_id.isdigit():
        courses = courses.filter(category_id=int(category_id))
    if difficulty in dict(Course.DIFFICULTY_CHOICES):
        courses = courses.filter(difficulty=difficulty)

    # Карточка раскрывается прямо в каталоге, поэтому подробности нужны сразу:
    # чему научится студент и список уроков.
    courses = list(courses)
    enrolled_ids = set()
    if request.user.is_authenticated:
        enrolled_ids = set(
            Enrollment.objects.filter(user=request.user).values_list('course_id', flat=True)
        )
    for course in courses:
        course.outcome_list = [
            line.strip(' -–•\t')
            for line in (course.learning_outcomes or '').splitlines()
            if line.strip(' -–•\t')
        ]
        course.lesson_list = sorted(course.lessons.all(), key=lambda lesson: lesson.order)
        course.is_enrolled = course.pk in enrolled_ids

    return render(request, 'courses/catalog.html', {
        'courses': courses,
        'categories': Category.objects.all(),
        'difficulties': Course.DIFFICULTY_CHOICES,
        'query': query,
        'selected_category': category_id,
        'selected_difficulty': difficulty,
        'is_filtered': bool(query or category_id or difficulty),
    })


def course_detail(request, pk):
    """Страница курса: описание, программа, запись (ФТ-3, ФТ-8, UC-4)."""
    course = get_object_or_404(Course.objects.select_related('category'), pk=pk)

    # Черновик виден только администратору (ФТ-18)
    if course.status != 'published' and not request.user.is_staff:
        raise Http404('Курс не найден')

    enrollment = None
    if request.user.is_authenticated:
        enrollment = Enrollment.objects.filter(user=request.user, course=course).first()

    track = build_track(request.user if enrollment else _Anonymous(), course)
    summary = track_summary(track) if enrollment else None

    outcomes = [
        line.strip(' -–•\t')
        for line in (course.learning_outcomes or '').splitlines()
        if line.strip(' -–•\t')
    ]

    return render(request, 'courses/course_detail.html', {
        'course': course,
        'enrollment': enrollment,
        'track': track,
        'summary': summary,
        'outcomes': outcomes,
        'students_count': course.enrollments.count(),
    })


class _Anonymous:
    """Заглушка: для гостя и для незаписанного пользователя все уроки закрыты."""

    is_authenticated = False


@login_required
def enroll(request, pk):
    """Запись на курс одной кнопкой, повторно записаться нельзя (ФТ-8, UC-8)."""
    course = get_object_or_404(Course, pk=pk, status='published')

    if request.method != 'POST':
        return redirect('courses:course_detail', pk=course.pk)

    if not course.lessons.exists():
        messages.error(request, 'В этом курсе пока нет уроков, записаться нельзя.')
        return redirect('courses:course_detail', pk=course.pk)

    enrollment, created = Enrollment.objects.get_or_create(user=request.user, course=course)
    if created:
        messages.success(
            request,
            f'Вы записаны на курс «{course.title}». Первый урок уже открыт.',
        )
    else:
        messages.info(request, f'Вы уже записаны на курс «{course.title}».')

    return redirect('courses:course_detail', pk=course.pk)


@login_required
def my_courses(request):
    """Раздел «Мои курсы» с процентом прохождения (ФТ-9, UC-9)."""
    enrollments = (
        Enrollment.objects
        .filter(user=request.user)
        .select_related('course', 'course__category')
    )

    in_progress, completed = [], []
    for enrollment in enrollments:
        summary = course_progress(request.user, enrollment.course)
        row = {'enrollment': enrollment, 'course': enrollment.course, 'summary': summary}
        _sync_completion(enrollment, summary)
        (completed if summary['completed'] else in_progress).append(row)

    return render(request, 'courses/my_courses.html', {
        'in_progress': in_progress,
        'completed': completed,
        'total': len(in_progress) + len(completed),
    })


def _sync_completion(enrollment, summary):
    """Проставляет дату завершения курса, когда пройдены все уроки (ФТ-16)."""
    from django.utils import timezone

    if summary['completed'] and enrollment.completed_at is None:
        enrollment.completed_at = timezone.now()
        enrollment.save(update_fields=['completed_at'])
        return True
    if not summary['completed'] and enrollment.completed_at is not None:
        enrollment.completed_at = None
        enrollment.save(update_fields=['completed_at'])
    return False


@login_required
def course_progress_page(request, pk):
    """Подробный прогресс пользователя по курсу (ФТ-15, UC-13)."""
    course = get_object_or_404(Course, pk=pk)
    enrollment = Enrollment.objects.filter(user=request.user, course=course).first()
    if not enrollment:
        messages.error(request, 'Сначала запишитесь на курс.')
        return redirect('courses:course_detail', pk=course.pk)

    track = build_track(request.user, course)
    summary = track_summary(track)
    _sync_completion(enrollment, summary)

    rows = []
    for item in track:
        test = item['test']
        attempts = list(test.attempts.filter(user=request.user)) if test else []
        best = max(attempts, key=lambda a: a.score) if attempts else None
        rows.append({**item, 'best': best, 'attempts': len(attempts)})

    return render(request, 'courses/course_progress.html', {
        'course': course,
        'enrollment': enrollment,
        'summary': summary,
        'rows': rows,
    })


# ---------------------------------------------------------------------------
# Урок
# ---------------------------------------------------------------------------

def youtube_embed(url):
    """Превращает обычную ссылку на YouTube во встраиваемую (ФТ-11)."""
    if not url:
        return ''
    url = url.strip()
    if 'youtube.com/embed/' in url:
        return url
    video_id = ''
    if 'youtu.be/' in url:
        video_id = url.split('youtu.be/')[-1].split('?')[0].split('&')[0]
    elif 'watch?v=' in url:
        video_id = url.split('watch?v=')[-1].split('&')[0]
    return f'https://www.youtube.com/embed/{video_id}' if video_id else ''


@login_required
def lesson_detail(request, pk):
    """Просмотр урока: текст, видео, материалы (ФТ-10, ФТ-11, UC-10)."""
    lesson = get_object_or_404(
        Lesson.objects.select_related('course').prefetch_related('files'), pk=pk,
    )
    course = lesson.course

    enrollment = Enrollment.objects.filter(user=request.user, course=course).first()
    if not enrollment:
        messages.error(request, 'Сначала запишитесь на курс.')
        return redirect('courses:course_detail', pk=course.pk)

    state = lesson_state(request.user, lesson)
    if state is None or not state['item']['is_open']:
        messages.error(request, 'Сначала сдайте тест предыдущего урока.')
        return redirect('courses:course_detail', pk=course.pk)

    test = state['item']['test']
    best = None
    if test:
        best = test.attempts.filter(user=request.user).order_by('-score', '-created_at').first()

    return render(request, 'courses/lesson_detail.html', {
        'course': course,
        'lesson': lesson,
        'enrollment': enrollment,
        'track': state['track'],
        'item': state['item'],
        'previous': state['previous'],
        'next_item': state['next_item'],
        'summary': state['summary'],
        'test': test,
        'best': best,
        'video_embed': youtube_embed(lesson.video_url),
    })


# ---------------------------------------------------------------------------
# Тест
# ---------------------------------------------------------------------------

@login_required
def test_take(request, pk):
    """Прохождение теста и автоматическая проверка (ФТ-12, ФТ-13, ФТ-14, UC-11)."""
    test = get_object_or_404(
        Test.objects.select_related('lesson', 'lesson__course'), pk=pk,
    )
    lesson = test.lesson
    course = lesson.course

    enrollment = Enrollment.objects.filter(user=request.user, course=course).first()
    if not enrollment:
        messages.error(request, 'Сначала запишитесь на курс.')
        return redirect('courses:course_detail', pk=course.pk)

    state = lesson_state(request.user, lesson)
    if state is None or not state['item']['is_open']:
        messages.error(request, 'Сначала сдайте тест предыдущего урока.')
        return redirect('courses:course_detail', pk=course.pk)

    questions = list(test.questions.prefetch_related('answers'))
    if not questions:
        messages.error(request, 'В этом тесте пока нет вопросов.')
        return redirect('courses:lesson_detail', pk=lesson.pk)

    if request.method == 'POST':
        attempt = check_answers(request, test, questions)
        summary = course_progress(request.user, course)
        if _sync_completion(enrollment, summary):
            messages.success(request, f'Поздравляем, курс «{course.title}» пройден!')
        return redirect('courses:test_result', pk=attempt.pk)

    best = test.attempts.filter(user=request.user).order_by('-score', '-created_at').first()

    return render(request, 'courses/test_take.html', {
        'test': test,
        'lesson': lesson,
        'course': course,
        'questions': questions,
        'best': best,
        'attempts_count': test.attempts.filter(user=request.user).count(),
    })


def check_answers(request, test, questions):
    """Сверяет ответы с правильными и считает процент (ФТ-13, UC-12)."""
    attempt = TestAttempt.objects.create(user=request.user, test=test, score=0)

    correct_count = 0
    for question in questions:
        chosen_ids = {
            int(value)
            for value in request.POST.getlist(f'question_{question.pk}')
            if value.isdigit()
        }
        options = list(question.answers.all())
        valid_ids = {option.pk for option in options}
        chosen_ids &= valid_ids
        correct_ids = {option.pk for option in options if option.is_correct}

        is_correct = bool(chosen_ids) and chosen_ids == correct_ids
        if is_correct:
            correct_count += 1

        answer = AttemptAnswer.objects.create(
            attempt=attempt, question=question, is_correct=is_correct,
        )
        if chosen_ids:
            answer.selected.set(Answer.objects.filter(pk__in=chosen_ids))

    attempt.score = round(correct_count * 100 / len(questions))
    attempt.passed = attempt.score >= test.pass_score
    attempt.save(update_fields=['score', 'passed'])

    # Сохраняем для страницы результата, чтобы не считать заново
    attempt.correct_count = correct_count
    attempt.total_count = len(questions)
    return attempt


@login_required
def test_result(request, pk):
    """Результат попытки с разбором ответов (ФТ-13, ФТ-14)."""
    attempt = get_object_or_404(
        TestAttempt.objects.select_related('test', 'test__lesson', 'test__lesson__course'),
        pk=pk,
    )
    if attempt.user_id != request.user.pk:
        raise PermissionDenied('Чужой результат смотреть нельзя.')

    lesson = attempt.test.lesson
    course = lesson.course

    answers = list(
        attempt.answers
        .select_related('question')
        .prefetch_related('question__answers', 'selected')
    )
    correct_count = sum(1 for answer in answers if answer.is_correct)

    state = lesson_state(request.user, lesson)
    summary = state['summary'] if state else None

    return render(request, 'courses/test_result.html', {
        'attempt': attempt,
        'lesson': lesson,
        'course': course,
        'answers': answers,
        'correct_count': correct_count,
        'total_count': len(answers),
        'next_item': state['next_item'] if state else None,
        'summary': summary,
        'course_completed': bool(summary and summary['completed']),
    })
