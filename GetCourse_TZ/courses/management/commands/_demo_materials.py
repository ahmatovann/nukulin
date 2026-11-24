"""Прикрепление готовых материалов (презентация и конспект в PDF) к урокам демо-курсов."""
import json

from django.conf import settings
from django.core.files import File

from courses.models import LessonFile

DEMO_DIR = settings.BASE_DIR / 'static' / 'demo'
HANDOUT_NAME = 'Конспект урока (PDF)'


def load_manifest():
    path = DEMO_DIR / 'materials.json'
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def attach_materials(lesson, manifest=None):
    """Добавляет к уроку презентацию и конспект, если их ещё нет. Возвращает число добавленного."""
    manifest = load_manifest() if manifest is None else manifest
    entry = manifest.get(f'{lesson.course.title}|{lesson.title}')
    if not entry:
        return 0
    added = 0

    name = entry.get('presentation')
    source = DEMO_DIR / 'presentations' / name if name else None
    if source and source.exists() and not lesson.has_presentation:
        with source.open('rb') as handle:
            lesson.presentation_file.save(name, File(handle), save=True)
        added += 1

    name = entry.get('handout')
    source = DEMO_DIR / 'files' / name if name else None
    if source and source.exists() and not lesson.files.filter(name=HANDOUT_NAME).exists():
        with source.open('rb') as handle:
            item = LessonFile(lesson=lesson, name=HANDOUT_NAME)
            item.file.save(name, File(handle), save=True)
        added += 1
    return added
