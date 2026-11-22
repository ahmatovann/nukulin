@echo off
rem Запуск GetCourse: сайт + Telegram-бот (бот откроется в отдельном окне)
cd /d "%~dp0"
start "GetCourse - Telegram-бот" .venv311\Scripts\python.exe manage.py run_bot
start "" http://127.0.0.1:8000/
.venv311\Scripts\python.exe manage.py runserver
