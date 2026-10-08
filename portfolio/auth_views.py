from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy

class LoginView(LoginView):
    template_name = "portfolio/login.html"
    redirect_authenticated_user = True  # Sends already-logged-in users straight to the dashboard
    
    def get_success_url(self):
        return reverse_lazy("dashboard")

    def form_invalid(self, form):
        messages.error(self.request, "Invalid username or password.")
        return super().form_invalid(form)


class LogoutView(LogoutView):
    # Sends user back to the login page after logging out
    next_page = reverse_lazy("login")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            messages.info(request, "You have been logged out.")
        return super().dispatch(request, *args, **kwargs)