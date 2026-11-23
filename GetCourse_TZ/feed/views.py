"""Страницы ленты."""
from django.shortcuts import get_object_or_404, render

from .models import Post


def post_detail(request, pk):
    """Полный текст одной публикации (ФТ-26)."""
    post = get_object_or_404(Post.objects.select_related('course'), pk=pk)
    others = Post.objects.exclude(pk=post.pk).select_related('course')[:3]
    return render(request, 'feed/post_detail.html', {
        'post': post,
        'others': others,
    })
