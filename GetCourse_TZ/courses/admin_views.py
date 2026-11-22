"""Страница статистики (UC-18) и выгрузка отчёта (UC-19) в админ-панели."""
import csv
from io import BytesIO

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.contrib import messages
from django.core.cache import cache
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .models import Course
from accounts import telegram

from .stats import INACTIVE_DAYS, MIN_ATTEMPTS_FOR_HARD, course_stats

REMIND_PAUSE = 24 * 60 * 60  # одному пользователю — не чаще раза в сутки по одному курсу


@staff_member_required
def statistics(request):
    courses = Course.objects.annotate(n=Count('enrollments')).order_by('-n', 'title')
    course = None
    course_id = request.GET.get('course', '')
    if course_id.isdigit():
        course = get_object_or_404(Course, pk=int(course_id))
    elif courses:
        course = courses[0]

    stats = course_stats(course) if course else {'has_data': False}
    context = {
        **admin.site.each_context(request),
        'title': 'Статистика курса',
        'courses': courses,
        'course': course,
        's': stats,
        'inactive_days': INACTIVE_DAYS,
        'min_attempts': MIN_ATTEMPTS_FOR_HARD,
        'telegram_ready': telegram.is_configured(),
        'tg_inactive': sum(1 for r in stats.get('inactive', []) if r['user'].telegram_chat_id),
    }
    return render(request, 'admin/courses/statistics.html', context)


@staff_member_required
def export_report(request, pk, fmt):
    course = get_object_or_404(Course, pk=pk)
    s = course_stats(course)
    if not s['has_data']:
        raise Http404('Нет данных для отчёта')

    stamp = timezone.localtime().strftime('%Y-%m-%d')
    filename = f'GetCourse_report_course{course.pk}_{stamp}'

    users_header = ['Фамилия', 'Имя', 'E-mail', 'Дата записи', 'Прогресс, %', 'Пройдено уроков',
                    'Текущий урок', 'Средний лучший балл, %', 'Последний вход', 'Не заходил > 14 дней']
    users_rows = [[
        r['user'].last_name, r['user'].first_name, r['user'].email,
        timezone.localtime(r['enrolled_at']).strftime('%d.%m.%Y'),
        r['progress'], r['done'], r['current'],
        r['avg_best'] if r['avg_best'] is not None else '',
        timezone.localtime(r['last_login']).strftime('%d.%m.%Y %H:%M') if r['last_login'] else 'никогда',
        'да' if r['inactive'] else 'нет',
    ] for r in s['rows']]
    funnel_header = ['№ урока', 'Урок', 'Дошли до урока', '% от записавшихся', 'Ушли перед уроком']
    funnel_rows = [[f['number'], f['title'], f['reached'], f['pct'], f['drop']] for f in s['funnel']]
    tests_header = ['№ урока', 'Тест к уроку', 'Проходной балл, %', 'Средний балл, %', 'Среднее число попыток', 'Сдали, %']
    tests_rows = [[t['number'], t['title'], t['pass_score'], t['avg_score'] if t['avg_score'] is not None else '',
                   t['avg_attempts'] if t['avg_attempts'] is not None else '', t['pass_rate']] for t in s['tests']]
    hard_header = ['№ урока', 'Вопрос', 'Ответов', 'Ошибок, %']
    hard_rows = [[q['lesson'], q['text'], q['answers'], q['error_pct']] for q in s['hard']]
    summary = [
        ['Курс', course.title],
        ['Дата отчёта', timezone.localtime().strftime('%d.%m.%Y %H:%M')],
        ['Записано пользователей', s['total']],
        ['Средний прогресс, %', s['avg_progress']],
        ['Завершили курс', f"{s['completed']} ({s['completed_pct']}%)"],
        [f'Не заходили больше {INACTIVE_DAYS} дней', s['inactive_count']],
    ]

    if fmt == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        response.write('﻿')  # чтобы Excel правильно открыл кириллицу
        w = csv.writer(response, delimiter=';')
        for block_title, header, rows in [
            ('Сводка', None, summary),
            ('Пользователи и прогресс', users_header, users_rows),
            ('Воронка прохождения', funnel_header, funnel_rows),
            ('Тесты', tests_header, tests_rows),
            ('Сложные вопросы', hard_header, hard_rows),
        ]:
            w.writerow([block_title])
            if header:
                w.writerow(header)
            w.writerows(rows)
            w.writerow([])
        return response

    if fmt == 'xlsx':
        from openpyxl import Workbook
        from openpyxl.chart import BarChart, Reference
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter

        wb = Workbook()
        head_font = Font(bold=True, color='FFFFFF')
        head_fill = PatternFill('solid', fgColor='7442B8')

        def sheet(ws, title, header, rows):
            ws.title = title
            ws.append(header)
            for cell in ws[1]:
                cell.font, cell.fill = head_font, head_fill
                cell.alignment = Alignment(vertical='center', wrap_text=True)
            for row in rows:
                ws.append(row)
            for i, col in enumerate(header, start=1):
                width = max([len(str(col))] + [len(str(r[i - 1])) for r in rows]) + 2
                ws.column_dimensions[get_column_letter(i)].width = min(max(width, 10), 60)
            ws.freeze_panes = 'A2'

        ws = wb.active
        ws.title = 'Сводка'
        for row in summary:
            ws.append(row)
        for cell in ws['A']:
            cell.font = Font(bold=True)
        ws.column_dimensions['A'].width = 34
        ws.column_dimensions['B'].width = 40

        sheet(wb.create_sheet(), 'Пользователи', users_header, users_rows)
        fw = wb.create_sheet()
        sheet(fw, 'Воронка', funnel_header, funnel_rows)
        if funnel_rows:
            chart = BarChart()
            chart.type = 'bar'
            chart.title = 'Сколько пользователей дошло до урока'
            chart.y_axis.title = 'Пользователей'
            chart.legend = None
            data = Reference(fw, min_col=3, min_row=1, max_row=len(funnel_rows) + 1)
            cats = Reference(fw, min_col=2, min_row=2, max_row=len(funnel_rows) + 1)
            chart.add_data(data, titles_from_data=True)
            chart.set_categories(cats)
            chart.x_axis.scaling.orientation = 'maxMin'
            chart.series[0].graphicalProperties.solidFill = '7442B8'
            chart.height, chart.width = 8, 16
            fw.add_chart(chart, 'G2')
        sheet(wb.create_sheet(), 'Тесты', tests_header, tests_rows)
        sheet(wb.create_sheet(), 'Сложные вопросы', hard_header, hard_rows)

        buf = BytesIO()
        wb.save(buf)
        response = HttpResponse(
            buf.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
        return response

    raise Http404('Неизвестный формат')


@staff_member_required
def remind_inactive(request, pk):
    """Напомнить в Telegram тем, кто не заходил больше 14 дней (ФТ-22 + бот)."""
    course = get_object_or_404(Course, pk=pk)
    back = reverse('admin_statistics') + f'?course={course.pk}#inactive'
    if request.method != 'POST':
        return redirect(back)
    if not telegram.is_configured():
        messages.error(request, 'Telegram-бот не настроен: добавьте TELEGRAM_BOT_TOKEN и TELEGRAM_BOT_USERNAME в .env.')
        return redirect(back)

    s = course_stats(course)
    site = request.build_absolute_uri('/')
    sent = no_telegram = already = failed = 0
    for row in s.get('inactive', []):
        user = row['user']
        if not user.telegram_chat_id:
            no_telegram += 1
            continue
        key = f'tg-remind:{course.pk}:{user.pk}'
        if cache.get(key):
            already += 1
            continue
        away = f'{row["days_away"]} дн.' if row['days_away'] is not None else 'давно.'
        text = (
            f'Здравствуйте, {user.first_name}! 👋\n\n'
            f'Вы не заходили на курс <b>«{course.title}»</b> уже {away}\n'
            f'Ваш прогресс: <b>{row["progress"]}%</b>. '
            + (f'Следующий урок: «{row["current"]}».' if not row['completed'] else '')
            + '\n\nВаш прогресс сохранён — продолжите с того места, где остановились.'
        )
        if telegram.send_message(user.telegram_chat_id, text, button=('Продолжить обучение', site)):
            cache.set(key, 1, REMIND_PAUSE)
            sent += 1
        else:
            failed += 1

    parts = [f'Напоминание отправлено: {sent}']
    if already:
        parts.append(f'уже напоминали сегодня: {already}')
    if no_telegram:
        parts.append(f'без Telegram: {no_telegram}')
    if failed:
        parts.append(f'не доставлено: {failed}')
    messages.success(request, ', '.join(parts) + '.') if sent else messages.warning(request, ', '.join(parts) + '.')
    return redirect(back)
