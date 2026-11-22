from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect

BLOCKED_MESSAGE = 'Ваша учётная запись заблокирована, обратитесь к администратору.'


class BlockedUserMiddleware:
    """Если администратор заблокировал пользователя, его текущий сеанс сразу завершается."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated and getattr(user, 'blocked', False):
            logout(request)
            messages.error(request, BLOCKED_MESSAGE)
            return redirect('accounts:login')
        return self.get_response(request)
