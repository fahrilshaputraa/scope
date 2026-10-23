from django.urls import path

from . import documentation_views, views

app_name = "identity"

urlpatterns = [
    path("settings/", views.settings_view, name="settings"),
    path("settings/docs/", documentation_views.documentation_view, name="docs"),
    path(
        "settings/docs/<slug:slug>/",
        documentation_views.documentation_view,
        name="docs_article",
    ),
    path("users/", views.user_list, name="user_list"),
    path("users/create/", views.user_create, name="user_create"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("users/<int:pk>/password/", views.user_password, name="user_password"),
    path("users/<int:pk>/toggle/", views.user_toggle_active, name="user_toggle_active"),
    path("login/", views.login_view, name="login"),
    path("authorize/", views.authorize_view, name="authorize"),
    path("callback/", views.callback_view, name="callback"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile_view, name="profile"),
]
