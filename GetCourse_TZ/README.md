# GetCourse — система онлайн-обучения

Учебный проект по дисциплине «Процессы проектирования и разработки программного
обеспечения». Система позволяет школе выкладывать курсы, а пользователям —
проходить уроки по порядку, сдавать тесты и видеть свой прогресс.

Стек: Python 3.11+, Django 5.2, PostgreSQL 15, HTML/CSS/JavaScript.

## Запуск

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux и macOS

pip install -r requirements.txt
```

Скопируйте `.env.example` в `.env` и впишите свои данные для PostgreSQL.
Если файла `.env` нет, проект запустится на SQLite — так удобно посмотреть
сайт сразу после скачивания.

```bash
python manage.py migrate
python manage.py demo_data          # демонстрационные курсы, пользователи и лента
python manage.py createsuperuser    # учётная запись администратора
python manage.py runserver
```

Сайт откроется по адресу `http://127.0.0.1:8000/`.

Демонстрационные данные удаляются командой `python manage.py demo_data --clear`,
собственные курсы и пользователи при этом не трогаются.

### Telegram-бот

Бот присылает коды восстановления пароля и напоминания тем, кто давно не заходил.
Токен выдаёт `@BotFather`, его вписывают в `.env`:

```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_BOT_USERNAME=...
```

Бот запускается отдельной командой, в своём окне терминала:

```bash
python manage.py run_bot
```

Без токена сайт работает как обычно, просто без Telegram: письма для
восстановления пароля печатаются в терминал.

## Структура проекта

| Папка | Что внутри |
|---|---|
| `config/` | настройки проекта и список адресов страниц |
| `accounts/` | пользователи, вход, профиль, Telegram-бот |
| `courses/` | курсы, уроки, тесты, прогресс, статистика |
| `feed/` | лента анонсов на главной странице |
| `templates/` | шаблоны страниц |
| `static/` | стили и скрипты |

Отдельные файлы, которые стоит знать:

- `courses/progress.py` — правило открытия уроков: первый открыт сразу,
  следующий — после сдачи теста предыдущего;
- `courses/stats.py` — расчёт статистики и аналитики для администратора;
- `courses/admin_views.py` — страницы статистики и выгрузка отчёта;
- `feed/services.py` — расчёт популярных курсов недели;
- `courses/templatetags/ru.py` — склонение слов после числа по-русски.

## Где выполнено каждое требование ТЗ

| Требование | Где реализовано |
|---|---|
| ФТ-1 Каталог курсов | `courses/views.py` → `catalog`, `templates/courses/catalog.html` |
| ФТ-2 Поиск и фильтрация | `courses/views.py` → `catalog` |
| ФТ-3 Страница курса | `courses/views.py` → `course_detail` |
| ФТ-4 Регистрация | `accounts/forms.py` → `RegisterForm` |
| ФТ-5 Вход, блокировка после 5 попыток | `accounts/forms.py` → `LoginForm` |
| ФТ-6 Выход | `accounts/views.py` → `LogoutView` |
| ФТ-7 Восстановление пароля | `accounts/reset.py`, `accounts/views.py` |
| ФТ-8 Запись на курс | `courses/views.py` → `enroll` |
| ФТ-9 Раздел «Мои курсы» | `courses/views.py` → `my_courses` |
| ФТ-10 Уроки по порядку | `courses/progress.py` → `build_track` |
| ФТ-11 Просмотр урока | `courses/views.py` → `lesson_detail` |
| ФТ-12 Прохождение теста | `courses/views.py` → `test_take` |
| ФТ-13 Автоматическая проверка | `courses/views.py` → `check_answers` |
| ФТ-14 Повторная сдача | `courses/views.py` → `test_take`, `test_result` |
| ФТ-15 Просмотр прогресса | `courses/views.py` → `course_progress_page` |
| ФТ-16 Завершение курса | `courses/views.py` → `_sync_completion` |
| ФТ-17 Редактирование профиля | `accounts/views.py` → `profile_edit` |
| ФТ-18 Управление курсами | `courses/admin.py` → `CourseAdmin` |
| ФТ-19 Управление уроками | `courses/admin.py` → `LessonAdmin`, `LessonInline` |
| ФТ-20 Управление тестами | `courses/admin.py` → `TestAdmin`, `QuestionInline` |
| ФТ-21 Защита от удаления | `courses/admin.py` → предупреждения перед удалением |
| ФТ-22 Статистика | `courses/stats.py`, `courses/admin_views.py` → `statistics` |
| ФТ-23 Управление пользователями | `accounts/admin.py` → `UserAdmin` |
| ФТ-24 Аналитика курса | `courses/stats.py` → `course_stats` |
| ФТ-25 Выгрузка отчёта | `courses/admin_views.py` → `export_report` |
| ФТ-26 Лента для гостей | `feed/models.py`, `courses/views.py` → `home` |
| ФТ-27 Популярные курсы недели | `feed/services.py` → `popular_courses_of_week` |
| ФТ-28 Управление лентой | `feed/admin.py` → `PostAdmin` |
