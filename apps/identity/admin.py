from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Membership, RoleDefinition, UserProfile, Workspace


class ProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False


class MembershipInline(admin.TabularInline):
    model = Membership
    fk_name = "user"
    extra = 0


class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline, MembershipInline]


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "display_name", "job_title", "sso_subject"]
    search_fields = ["user__username", "user__email", "display_name"]


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "status"]


@admin.register(RoleDefinition)
class RoleDefinitionAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "scope"]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "workspace", "role", "status", "assigned_at"]
    list_filter = ["role", "status", "workspace"]
