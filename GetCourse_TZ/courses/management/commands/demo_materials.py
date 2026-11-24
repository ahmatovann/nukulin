"""Добавляет к урокам презентации и файлы для скачивания (ФТ-29).

Запуск:  python manage.py demo_materials

Курсы, записи и оплаты не меняются: команда только прикрепляет к урокам готовые PDF
(презентация и конспект) и пропускает то, что уже прикреплено, поэтому её можно
запускать повторно. Видео и аудио добавляются вручную в админ-панели (поля «Видео» и «Аудио»).
"""
from django.core.management.base import BaseCommand

from courses.models import Lesson

from ._demo_materials import attach_materials, load_manifest


class Command(BaseCommand):
    help = 'Прикрепляет презентации и конспекты к урокам демо-курсов.'

    def handle(self, *args, **options):
        manifest = load_manifest()
        if not manifest:
            self.stdout.write('Готовых материалов нет (static/demo/materials.json).')
            return
        lessons = Lesson.objects.select_related('course')
        added = sum(attach_materials(lesson, manifest) for lesson in lessons)
        self.stdout.write(self.style.SUCCESS(f'Готово: добавлено файлов — {added}.'))
