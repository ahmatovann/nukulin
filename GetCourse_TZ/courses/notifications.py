"""Уведомления пользователю в Telegram. Если бот не настроен или аккаунт не подключён, ничего не происходит."""
from accounts import telegram

SOURCE_TEXT = {
    'payment': 'Оплата прошла',
    'code': 'Код доступа принят',
    'admin': 'Администратор открыл вам доступ',
}


def _send(user, text, site_url, path='/'):
    if not getattr(user, 'telegram_chat_id', None):
        return False
    button = ('Открыть на сайте', site_url.rstrip('/') + path) if site_url else None
    return telegram.send_message(user.telegram_chat_id, text, button=button)


def access_granted(user, course, source, site_url=''):
    from django.urls import reverse
    text = (
        f'✅ <b>{SOURCE_TEXT.get(source, "Доступ открыт")}</b>\n\n'
        f'Курс «{course.title}» теперь доступен. Первый урок уже открыт — можно начинать.'
    )
    return _send(user, text, site_url, reverse('courses:course_detail', args=[course.pk]))


def comment_reply(reply, site_url=''):
    """Автору комментария приходит сообщение, когда ему ответили."""
    from django.urls import reverse
    parent = reply.parent
    if parent is None or parent.user_id == reply.user_id:
        return False
    author = f'{reply.user.first_name} {reply.user.last_name[:1]}.'
    text = (
        f'💬 <b>{author}</b> ответил(а) на ваш комментарий к уроку «{reply.lesson.title}»:\n\n'
        f'{reply.text[:300]}'
    )
    return _send(user=parent.user, text=text, site_url=site_url,
                 path=reverse('courses:lesson_detail', args=[reply.lesson_id]) + f'#comment-{reply.pk}')


def course_completed(user, course, site_url=''):
    from django.urls import reverse
    text = f'🎉 <b>Курс пройден!</b>\n\nВы сдали тесты всех уроков курса «{course.title}». Оставьте отзыв — это поможет другим.'
    return _send(user, text, site_url, reverse('courses:course_detail', args=[course.pk]) + '#reviews')
