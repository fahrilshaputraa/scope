from django import forms

from apps.projects.models import Project

from .models import Issue, IssueStatus, Task, TaskComment


def _style():
    return {
        "class": (
            "flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 "
            "text-sm shadow-sm transition-colors focus-visible:outline-none "
            "focus-visible:ring-1 focus-visible:ring-ring"
        )
    }


def _style_textarea():
    return {
        "class": (
            "flex min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 "
            "text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 "
            "focus-visible:ring-ring"
        )
    }


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            "title",
            "description",
            "phase",
            "milestone",
            "assignee",
            "status",
            "priority",
            "start_date",
            "due_date",
            "progress",
            "weight",
            "labels",
            "order",
            "parent_task",
            "blocked_reason",
            "blocked_dependency",
        ]

    def __init__(self, *args, project=None, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update(
                _style_textarea() if field in ("description", "blocked_reason") else _style()
            )
        if self.project:
            self.fields["phase"].queryset = self.project.phases.all()
            self.fields["milestone"].queryset = self.project.milestones.all()
            self.fields["parent_task"].queryset = self.project.tasks.all()


class IssueForm(forms.ModelForm):
    class Meta:
        model = Issue
        fields = [
            "project",
            "title",
            "description",
            "task",
            "severity",
            "priority",
            "status",
            "owner",
            "due_date",
            "resolution",
        ]

    def __init__(self, *args, project=None, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update(
                _style_textarea() if field in ("description", "resolution") else _style()
            )
        # bila form dipakai dalam konteks project, project diambil dari context
        if project is not None:
            self.fields["project"].widget = forms.HiddenInput()
            self.fields["project"].queryset = Project.objects.filter(pk=project.pk)
        if self.project:
            self.fields["task"].queryset = self.project.tasks.all()
        if not self.instance.pk and self.project:
            self.fields["owner"].initial = None
        # status default open hanya saat create
        if not self.instance.pk:
            self.fields["status"].initial = IssueStatus.OPEN


class TaskCommentForm(forms.ModelForm):
    class Meta:
        model = TaskComment
        fields = ["content"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["content"].widget.attrs.update(_style_textarea())