"""Восстановление пароля по e-mail (UC-6, альтернативный сценарий 1а).

В письме приходят 6-значный код и ссылка (ссылка сама подставляет код).
Код живёт 10 минут, на ввод даётся 5 попыток, повторно отправить можно через 60 секунд.
"""
import hashlib
import logging
import hmac
import secrets
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from .models import User

CODE_TTL = 10 * 60
MAX_TRIES = 5
RESEND_AFTER = 60
log = logging.getLogger(__name__)


def _key(email):
    return f'pwd-reset:{email}'


def _hash(email, code):
    msg = f'{email}:{code}'.encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def can_resend(email):
    return cache.get(f'pwd-reset-sent:{email}') is None


def send_code(request, email):
    """Отправляет код, если такой пользователь есть. Для несуществующего e-mail
    ответ такой же, как для существующего, — так нельзя узнать, зарегистрирован ли он.
    Возвращает False, только если письмо не удалось отправить."""
    email = email.strip().lower()
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    cache.set(f'pwd-reset-sent:{email}', 1, RESEND_AFTER)
    if not user:
        return True
    code = f'{secrets.randbelow(1_000_000):06d}'
    cache.set(_key(email), {'hash': _hash(email, code), 'tries': 0, 'user_id': user.pk}, CODE_TTL)
    link = request.build_absolute_uri(reverse('accounts:password_reset_code')) + '?' + urlencode({'email': user.email, 'code': code})
    context = {'user': user, 'code': code, 'link': link, 'minutes': CODE_TTL // 60}
    # Если Telegram привязан — код приходит ещё и в бот (удобно, когда почта не работает).
    from . import telegram
    tg_ok = bool(user.telegram_chat_id) and telegram.send_message(
        user.telegram_chat_id,
        f'🔐 Код для восстановления пароля GetCourse: <b>{code}</b>\n\n'
        f'Код действует {CODE_TTL // 60} минут. Если это были не вы — просто проигнорируйте сообщение.',
        button=('Открыть страницу ввода кода', link),
    )
    try:
        send_mail(
            subject=render_to_string('accounts/emails/password_reset_subject.txt').strip(),
            message=render_to_string('accounts/emails/password_reset_email.txt', context),
            from_email=None,
            recipient_list=[user.email],
        )
    except Exception:  # нет интернета, неверный пароль почты и т. п.
        log.exception('Не удалось отправить письмо для восстановления пароля')
        if tg_ok:
            return True  # письмо не ушло, но код уже в Telegram
        cache.delete(f'pwd-reset-sent:{email}')
        return False
    return True


def check_code(email, code):
    """Возвращает (user_id или None, сообщение об ошибке или None)."""
    data = cache.get(_key(email))
    if not data:
        return None, 'Код устарел или не запрашивался. Отправьте новый код.'
    if data['tries'] >= MAX_TRIES:
        return None, 'Слишком много попыток. Отправьте новый код.'
    if hmac.compare_digest(data['hash'], _hash(email, code)):
        cache.delete(_key(email))
        return data['user_id'], None
    data['tries'] += 1
    cache.set(_key(email), data, CODE_TTL)
    left = MAX_TRIES - data['tries']
    if left <= 0:
        return None, 'Неверный код. Попытки закончились — отправьте новый код.'
    return None, f'Неверный код. Осталось попыток: {left}.'
