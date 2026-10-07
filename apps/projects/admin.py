from django.contrib import admin

from .models import (
    ActivityEvent,
    Decision,
    Milestone,
    Note,
    Phase,
    ProgressBaselinePoint,
    ProgressSnapshot,
    Project,
)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "name",
        "manager",
        "status",
        "start_date",
        "target_end_date",
        "team",
    ]
    list_filter = ["status", "team"]
    search_fields = ["code", "name"]
    autocomplete_fields = ["manager", "current_phase"]


@admin.register(Phase)
class PhaseAdmin(admin.ModelAdmin):
    list_display = ["project", "sequence", "name", "start_date", "end_date", "status"]
    list_filter = ["status"]
    search_fields = ["name", "project__code"]


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ["project", "name", "date", "status", "owner"]
    list_filter = ["status"]
    search_fields = ["name", "project__code"]


@admin.register(ProgressBaselinePoint)
class ProgressBaselinePointAdmin(admin.ModelAdmin):
    list_display = ["project", "date", "planned_percent", "label"]
    list_filter = ["project"]


@admin.register(ProgressSnapshot)
class ProgressSnapshotAdmin(admin.ModelAdmin):
    list_display = ["project", "date", "planned_progress", "actual_progress", "variance"]
    list_filter = ["project"]


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ["project", "title", "author", "updated_at"]
    search_fields = ["title", "content"]


@admin.register(Decision)
class DecisionAdmin(admin.ModelAdmin):
    list_display = ["project", "title", "decision_maker", "created_at"]
    search_fields = ["title", "decision"]


@admin.register(ActivityEvent)
class ActivityEventAdmin(admin.ModelAdmin):
    list_display = ["project", "action", "actor", "message", "created_at"]
    list_filter = ["action"]
