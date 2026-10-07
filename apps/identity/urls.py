from django.urls import path

from . import views

app_name = "identity"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("authorize/", views.authorize_view, name="authorize"),
    path("callback/", views.callback_view, name="callback"),
    path("logout/", views.logout_view, name="logout"),
    path("dev/", views.dev_login_view, name="dev"),
    path("profile/", views.profile_view, name="profile"),
]
