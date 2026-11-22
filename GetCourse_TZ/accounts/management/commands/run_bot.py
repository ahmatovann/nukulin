"""Запуск Telegram-бота GetCourse:  python manage.py run_bot
Бот принимает привязку аккаунтов (/start из профиля) и отвечает на команды.
Остановить — Ctrl+C."""
import time
import urllib.error

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from accounts import telegram
from accounts.models import User

HELP = (
    'Я бот GetCourse 👋\n\n'
    'Сюда приходят напоминания о курсах и коды для восстановления пароля.\n\n'
    'Чтобы подключить аккаунт, откройте на сайте «Профиль» и нажмите «Подключить Telegram».\n\n'
    '/status — к какому аккаунту я подключён\n'
    '/stop — отключить уведомления'
)


class Command(BaseCommand):
    help = 'Запускает Telegram-бота GetCourse (long polling).'

    def handle(self, *args, **options):
        if not telegram.is_configured():
            raise CommandError('Бот не настроен: добавьте TELEGRAM_BOT_TOKEN и TELEGRAM_BOT_USERNAME в файл .env')
        try:
            me = telegram.api('getMe')
        except Exception as error:
            raise CommandError(f'Не удалось подключиться к Telegram: {error}')
        self.stdout.write(self.style.SUCCESS(f'Бот @{me["username"]} запущен. Остановить: Ctrl+C'))

        offset = None
        while True:
            try:
                updates = telegram.api('getUpdates', {'timeout': 25, 'offset': offset,
                                                      'allowed_updates': ['message']}, timeout=35)
            except KeyboardInterrupt:
                break
            except (urllib.error.URLError, OSError, RuntimeError) as error:
                self.stderr.write(f'Нет связи с Telegram ({error}), повтор через 5 секунд…')
                time.sleep(5)
                continue
            for update in updates:
                offset = update['update_id'] + 1
                message = update.get('message') or {}
                if message.get('text'):
                    close_old_connections()
                    try:
                        self.handle_message(message)
                    except Exception as error:  # бот не должен падать из-за одного сообщения
                        self.stderr.write(f'Ошибка обработки сообщения: {error}')

    def reply(self, chat_id, text):
        telegram.send_message(chat_id, text)

    def handle_message(self, message):
        chat_id = message['chat']['id']
        text = message['text'].strip()
        username = (message.get('from') or {}).get('username', '') or ''
        command, _, arg = text.partition(' ')
        command = command.split('@')[0].lower()

        if command == '/start' and arg:
            user_id = telegram.read_link_token(arg.strip())
            user = User.objects.filter(pk=user_id).first() if user_id else None
            if not user:
                self.reply(chat_id, 'Ссылка устарела или неверна. Откройте профиль на сайте и нажмите «Подключить Telegram» ещё раз.')
                return
            User.objects.filter(telegram_chat_id=chat_id).exclude(pk=user.pk).update(telegram_chat_id=None, telegram_username='')
            user.telegram_chat_id = chat_id
            user.telegram_username = username
            user.save(update_fields=['telegram_chat_id', 'telegram_username'])
            self.reply(chat_id, f'Готово! Аккаунт <b>{user.first_name} {user.last_name}</b> ({user.email}) подключён.\n\n'
                                'Сюда будут приходить напоминания о курсах и коды для восстановления пароля.')
            self.stdout.write(f'Подключён Telegram для {user.email}')
            return

        user = User.objects.filter(telegram_chat_id=chat_id).first()
        if command == '/stop':
            if user:
                user.telegram_chat_id = None
                user.telegram_username = ''
                user.save(update_fields=['telegram_chat_id', 'telegram_username'])
                self.reply(chat_id, 'Уведомления отключены. Подключить снова можно в профиле на сайте.')
            else:
                self.reply(chat_id, 'Этот чат и так не подключён к аккаунту.')
        elif command == '/status':
            if user:
                self.reply(chat_id, f'Подключён аккаунт: <b>{user.first_name} {user.last_name}</b> ({user.email}).')
            else:
                self.reply(chat_id, 'Аккаунт не подключён. Откройте профиль на сайте и нажмите «Подключить Telegram».')
        else:
            self.reply(chat_id, HELP)
