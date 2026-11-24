from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse

from . import reset, telegram
from .forms import (
    ChangePasswordForm,
    LoginForm,
    ProfileForm,
    RegisterForm,
    ResetRequestForm,
    ResetSetPasswordForm,
    clear_login_failures,
)
from .models import User


# UC-5: регистрация
def register(request):
    if request.user.is_authenticated:
        return redirect('courses:home')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'Добро пожаловать, {user.first_name}! Регистрация прошла успешно.')
        return redirect('accounts:profile')  # UC-5, шаг 6: система открывает личный кабинет
    return render(request, 'accounts/register.html', {'form': form})


# UC-6: вход
class LoginView(auth_views.LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_redirect_url(self):
        url = super().get_redirect_url()
        # Обычного пользователя не пускаем по ссылке в админ-панель (иначе бесконечный круг).
        if url.startswith('/admin') and not self.request.user.is_staff:
            return ''
        return url

    def get_default_redirect_url(self):
        # Шаг 5 сценария: администратору — панель администратора.
        if self.request.user.is_staff:
            return reverse('admin:index')
        return super().get_default_redirect_url()

    def form_valid(self, form):
        clear_login_failures(form.get_user().email)
        messages.success(self.request, f'Здравствуйте, {form.get_user().first_name}!')
        return super().form_valid(form)


def admin_login_redirect(request):
    """Вход в /admin/ идёт через общую страницу входа — там работают блокировки из ТЗ."""
    url = reverse('accounts:login')
    if request.GET:
        url += '?' + request.GET.urlencode()
    return HttpResponseRedirect(url)


# UC-7: выход
class LogoutView(auth_views.LogoutView):
    def post(self, request, *args, **kwargs):
        messages.info(request, 'Вы вышли из системы.')
        return super().post(request, *args, **kwargs)


# UC-14: профиль — и для пользователя, и для администратора
def profile_completeness(user):
    """Насколько заполнен профиль: имя, фамилия, e-mail, фото — по 25%."""
    filled = [bool(user.first_name), bool(user.last_name), bool(user.email), bool(user.avatar)]
    return round(sum(filled) * 100 / len(filled))


@login_required
def profile(request):
    user = request.user
    if user.is_staff:
        from courses.models import Course, Test  # подсчёты для администратора
        from .models import User
        stats = [
            (Course.objects.count(), 'Курсов'),
            (Course.objects.filter(status='published').count(), 'Опубликовано'),
            (User.objects.filter(is_staff=False).count(), 'Пользователей'),
        ]
        extra = [(Test.objects.count(), 'Тестов в системе')]
    else:
        from django.db.models import Avg, Max
        from courses.models import Enrollment, TestAttempt
        from courses.progress import course_progress

        enrollments = list(Enrollment.objects.filter(user=user).select_related('course').order_by('-enrolled_at'))
        lessons_done = 0
        certificates = []
        for enrollment in enrollments:
            summary = course_progress(user, enrollment.course)
            lessons_done += summary['done']
            if summary['completed']:
                certificates.append(enrollment)
        best = (TestAttempt.objects.filter(user=user).values('test')
                .annotate(top=Max('score')).aggregate(avg=Avg('top'))['avg'])
        stats = [
            (len(enrollments), 'Курсов'),
            (lessons_done, 'Уроков пройдено'),
            (f'{round(best)}%' if best is not None else '—', 'Средний балл'),
        ]
        extra = []
    return render(request, 'accounts/profile.html', {
        'certificates': certificates if not user.is_staff else [],
        'telegram_ready': telegram.is_configured(),
        'completeness': profile_completeness(user),
        'stats': stats,
        'extra': extra,
    })


@login_required
def telegram_connect(request):
    """Открывает бота со ссылкой-приглашением (действует 1 час)."""
    if not telegram.is_configured():
        messages.error(request, 'Telegram-бот ещё не настроен администратором.')
        return redirect('accounts:profile')
    return HttpResponseRedirect(telegram.link_url(request.user))


@login_required
def telegram_disconnect(request):
    if request.method == 'POST' and request.user.telegram_chat_id:
        chat_id = request.user.telegram_chat_id
        request.user.telegram_chat_id = None
        request.user.telegram_username = ''
        request.user.save(update_fields=['telegram_chat_id', 'telegram_username'])
        telegram.send_message(chat_id, 'Telegram отключён от аккаунта GetCourse. Подключить снова можно в профиле на сайте.')
        messages.success(request, 'Telegram отключён.')
    return redirect('accounts:profile')


@login_required
def profile_edit(request):
    user = request.user
    profile_form = ProfileForm(instance=user)
    password_form = ChangePasswordForm(user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'profile':
            profile_form = ProfileForm(request.POST, request.FILES, instance=user)
            if request.POST.get('remove_avatar') and not request.FILES.get('avatar'):
                if user.avatar:
                    user.avatar.delete(save=False)
                user.avatar = None
                profile_form = ProfileForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Изменения сохранены.')
                return redirect('accounts:profile')
        elif action == 'password':
            password_form = ChangePasswordForm(user, request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, 'Пароль изменён.')
                return redirect('accounts:profile')
        user.refresh_from_db()

    return render(request, 'accounts/profile_edit.html', {
        'completeness': profile_completeness(user),
        'profile_form': profile_form,
        'password_form': password_form,
    })


# UC-6, 1а: восстановление пароля — код и ссылка на e-mail
SESSION_EMAIL = 'reset_email'
SESSION_USER = 'reset_user_id'


def password_reset(request):
    """Шаг 1: пользователь вводит e-mail."""
    form = ResetRequestForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].strip().lower()
        if reset.can_resend(email) and not reset.send_code(request, email):
            messages.error(request, 'Не удалось отправить письмо. Проверьте подключение к интернету и настройки почты, затем попробуйте ещё раз.')
            return render(request, 'accounts/password_reset_form.html', {'form': form})
        request.session[SESSION_EMAIL] = email
        request.session.pop(SESSION_USER, None)
        return redirect('accounts:password_reset_code')
    return render(request, 'accounts/password_reset_form.html', {'form': form})


def password_reset_code(request):
    """Шаг 2: ввод 6-значного кода (или переход по ссылке из письма)."""
    if request.GET.get('email') and request.GET.get('code'):
        request.session[SESSION_EMAIL] = request.GET['email'].strip().lower()
    email = request.session.get(SESSION_EMAIL)
    if not email:
        return redirect('accounts:password_reset')

    error = None
    code = ''
    if request.method == 'POST' and request.POST.get('action') == 'resend':
        if reset.can_resend(email):
            if reset.send_code(request, email):
                messages.success(request, 'Новый код отправлен.')
            else:
                messages.error(request, 'Не удалось отправить письмо. Попробуйте ещё раз чуть позже.')
        else:
            messages.info(request, f'Новый код можно запросить через {reset.RESEND_AFTER} секунд.')
        return redirect('accounts:password_reset_code')

    if request.method == 'POST' or request.GET.get('code'):
        code = ''.join(ch for ch in (request.POST.get('code') or request.GET.get('code', '')) if ch.isdigit())[:6]
        if len(code) != 6:
            error = 'Введите все 6 цифр кода.'
        else:
            user_id, error = reset.check_code(email, code)
            if user_id:
                request.session[SESSION_USER] = user_id
                return redirect('accounts:password_reset_new')

    return render(request, 'accounts/password_reset_code.html', {
        'email': email,
        'error': error,
        'resend_after': reset.RESEND_AFTER,
        'can_resend': reset.can_resend(email),
    })


def password_reset_new(request):
    """Шаг 3: код подтверждён — задаём новый пароль."""
    user_id = request.session.get(SESSION_USER)
    user = User.objects.filter(pk=user_id).first() if user_id else None
    if not user:
        return redirect('accounts:password_reset')

    form = ResetSetPasswordForm(user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        clear_login_failures(user.email)
        request.session.pop(SESSION_USER, None)
        request.session.pop(SESSION_EMAIL, None)
        request.session['reset_done'] = True
        return redirect('accounts:password_reset_complete')
    return render(request, 'accounts/password_reset_new.html', {'form': form, 'verified_now': request.method == 'GET'})


def password_reset_complete(request):
    """Шаг 4: «Пароль изменён»."""
    if not request.session.pop('reset_done', False):
        return redirect('accounts:login')
    return render(request, 'accounts/password_reset_complete.html')
