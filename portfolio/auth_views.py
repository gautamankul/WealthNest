from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.contrib.auth import login
from django.shortcuts import redirect
from django.views.generic import CreateView
from .forms import RegisterForm



class RegisterView(CreateView):
    form_class = RegisterForm
    template_name = "portfolio/register.html"
    success_url = reverse_lazy("dashboard")

    def dispatch(self, request, *args, **kwargs):
        # Redirect already-logged-in users straight to the dashboard
        if request.user.is_authenticated:
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        # Automatically log the user in after successful creation
        login(self.request, user)
        return redirect(self.success_url)

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