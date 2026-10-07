from django.contrib import admin

from .models import Issue, Task, TaskComment


class TaskCommentInline(admin.TabularInline):
    model = TaskComment
    extra = 0


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "project",
        "assignee",
        "status",
        "priority",
        "progress",
        "weight",
        "due_date",
    ]
    list_filter = ["status", "priority", "project"]
    search_fields = ["title", "description"]
    autocomplete_fields = ["assignee"]
    inlines = [TaskCommentInline]


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "project",
        "severity",
        "priority",
        "status",
        "owner",
        "due_date",
    ]
    list_filter = ["status", "severity", "project"]
    search_fields = ["title", "description"]
    autocomplete_fields = ["owner", "task"]
