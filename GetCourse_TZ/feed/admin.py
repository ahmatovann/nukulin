"""Управление лентой для администратора (ФТ-28, UC-21)."""
from django.contrib import admin, messages

from .models import MAX_PINNED, Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'pinned', 'created_at')
    list_filter = ('pinned', 'created_at')
    search_fields = ('title', 'text')
    list_editable = ('pinned',)
    date_hierarchy = 'created_at'
    actions = ['pin_posts', 'unpin_posts']

    fieldsets = (
        (None, {'fields': ('title', 'text')}),
        ('Оформление', {'fields': ('image', 'course')}),
        ('Размещение', {
            'fields': ('pinned',),
            'description': f'Закреплённые публикации показываются в начале ленты. '
                           f'Больше {MAX_PINNED} закрепить нельзя.',
        }),
    )

    @admin.action(description='Закрепить вверху ленты')
    def pin_posts(self, request, queryset):
        already = Post.objects.filter(pinned=True).exclude(pk__in=queryset.values('pk')).count()
        free = MAX_PINNED - already
        if free <= 0:
            self.message_user(
                request,
                f'Уже закреплено {MAX_PINNED} публикаций. Сначала открепите одну из них.',
                messages.ERROR,
            )
            return

        chosen = list(queryset.values_list('pk', flat=True))
        updated = Post.objects.filter(pk__in=chosen[:free]).update(pinned=True)
        self.message_user(request, f'Закреплено публикаций: {updated}.', messages.SUCCESS)
        if len(chosen) > free:
            self.message_user(
                request,
                f'Остальные оставлены без закрепления: разрешено не больше {MAX_PINNED}.',
                messages.WARNING,
            )

    @admin.action(description='Открепить')
    def unpin_posts(self, request, queryset):
        updated = queryset.update(pinned=False)
        self.message_user(request, f'Откреплено публикаций: {updated}.', messages.SUCCESS)
