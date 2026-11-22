"""Telegram-бот GetCourse: привязка аккаунта, напоминания и коды восстановления пароля.

Сообщения отправляются напрямую через Telegram Bot API (обычный HTTPS-запрос),
поэтому для отправки бот не обязан быть запущен. Команда `python manage.py run_bot`
нужна только для того, чтобы бот отвечал пользователям и принимал привязку аккаунтов.
"""
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)
LINK_TTL = 60 * 60  # ссылка для привязки действует 1 час


def is_configured():
    return bool(getattr(settings, 'TELEGRAM_BOT_TOKEN', '') and getattr(settings, 'TELEGRAM_BOT_USERNAME', ''))


def api(method, payload=None, timeout=30):
    url = f'https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}'
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode())
    if not body.get('ok'):
        raise RuntimeError(body.get('description', 'Telegram API error'))
    return body['result']


def send_message(chat_id, text, button=None):
    """Отправляет сообщение. Возвращает True/False — сайт не падает, если Telegram недоступен."""
    if not is_configured() or not chat_id:
        return False
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
    if button:
        payload['reply_markup'] = {'inline_keyboard': [[{'text': button[0], 'url': button[1]}]]}
    try:
        api('sendMessage', payload, timeout=15)
        return True
    except urllib.error.HTTPError as error:
        if error.code == 400 and button:
            # Telegram не принимает кнопки со ссылкой на localhost — отправим ссылку текстом.
            payload.pop('reply_markup', None)
            payload['text'] = f'{text}\n\n{button[1]}'
            try:
                api('sendMessage', payload, timeout=15)
                return True
            except Exception:
                log.exception('Telegram: не удалось отправить сообщение')
        else:
            log.warning('Telegram: ошибка %s при отправке в чат %s', error.code, chat_id)
    except Exception:
        log.exception('Telegram: не удалось отправить сообщение')
    return False


# --- Ссылка для привязки: t.me/<бот>?start=<user_id>-<время>-<подпись> -------------

def _sign(value):
    return hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()[:20]


def make_link_token(user):
    value = f'{user.pk}-{int(time.time())}'
    return f'{value}-{_sign(value)}'


def read_link_token(token):
    """Возвращает id пользователя или None, если ссылка поддельная или устарела."""
    try:
        user_id, ts, sig = token.split('-')
        value = f'{user_id}-{ts}'
        if not hmac.compare_digest(sig, _sign(value)):
            return None
        if time.time() - int(ts) > LINK_TTL:
            return None
        return int(user_id)
    except (ValueError, TypeError):
        return None


def link_url(user):
    return f'https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={make_link_token(user)}'
