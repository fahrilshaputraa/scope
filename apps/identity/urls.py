from django.urls import path

from . import views

app_name = "identity"

urlpatterns = [
    path("settings/", views.settings_view, name="settings"),
    path("users/create/", views.user_create, name="user_create"),
    path("login/", views.login_view, name="login"),
    path("authorize/", views.authorize_view, name="authorize"),
    path("callback/", views.callback_view, name="callback"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile_view, name="profile"),
]
