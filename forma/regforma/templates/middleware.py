from django.shortcuts import redirect
from django.urls import reverse

class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated and request.path != reverse('login'):
            return redirect('login')
        response = self.get_response(request)
        return response
    
# middleware.py
class DisableCachingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith('/api/'):
            response['Cache-Control'] = 'no-store, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = 'Fri, 01 Jan 1990 00:00:00 GMT'
        return response