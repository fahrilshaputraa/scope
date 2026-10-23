from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.form_widgets import fill_missing_defaults, style_form
from apps.projects.models import Project
from apps.richtext import SanitizeRichTextMixin

from .models import TASK_STATUS_LABELS, Issue, IssueStatus, Task, TaskComment


class TaskForm(SanitizeRichTextMixin, forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            "title",
            "description",
            "phase",
            "milestone",
            "assignee",
            "collaborators",
            "status",
            "priority",
            "start_date",
            "due_date",
            "progress",
            "weight",
            "labels",
            "order",
            "parent_task",
            "dependencies",
            "baseline_start_date",
            "baseline_end_date",
            "blocked_reason",
            "blocked_dependency",
        ]

    def __init__(self, *args, project=None, can_plan=True, parent=None, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)
        if project:
            self.instance.project = project
        if parent:
            self.instance.parent_task = parent
            self.instance.phase_id = parent.phase_id
            self.initial.update(parent_task=parent.pk, phase=parent.phase_id)
        if not can_plan:
            allowed = {"status", "progress", "blocked_reason", "blocked_dependency"}
            for name in list(self.fields):
                if name not in allowed:
                    self.fields.pop(name)
        self.fields["status"].choices = list(TASK_STATUS_LABELS.items())
        fill_missing_defaults(self, ["status", "priority", "progress", "weight", "order"])
        primary = (
            ["title", "assignee", "collaborators", "due_date"]
            if not self.instance.pk
            else ["title", "assignee", "collaborators", "due_date", "status", "progress"]
        )
        if not can_plan:
            primary = ["status", "progress", "blocked_reason", "blocked_dependency"]
        elif parent or self.instance.parent_task_id:
            primary.append("parent_task")
        if self.project and can_plan:
            self.fields["phase"].queryset = self.project.phases.all()
            self.fields["milestone"].queryset = self.project.milestones.all()
            self.fields["parent_task"].queryset = self.project.tasks.filter(
                parent_task__isnull=True
            ).exclude(pk=self.instance.pk)
            if self.instance.has_details:
                self.fields["parent_task"].queryset = self.project.tasks.none()
            self.fields["dependencies"].queryset = self.project.tasks.exclude(pk=self.instance.pk)
            from django.contrib.auth.models import User

            self.fields["assignee"].queryset = (
                User.objects.filter(is_active=True)
                .filter(
                    Q(member_projects=self.project)
                    | Q(pk=self.project.manager_id)
                    | Q(assigned_tasks__project=self.project)
                    | Q(collaborating_tasks__project=self.project)
                )
                .distinct()
            )

            self.fields["collaborators"].queryset = self.fields["assignee"].queryset
        if "parent_task" in self.fields:
            self.fields["parent_task"].help_text = (
                "Opsional. Pilih untuk menjadikan pekerjaan ini detail activity. "
                "Phase mengikuti induk."
            )
            if parent:
                self.fields["parent_task"].disabled = True
        if "phase" in self.fields and (parent or self.instance.parent_task_id):
            self.fields["phase"].disabled = True
            self.initial["phase"] = self.instance.parent_task.phase_id
            self.fields["phase"].help_text = "Mengikuti phase activity induk."
        if self.instance.has_details:
            self.fields["progress"].disabled = True
            self.initial["progress"] = self.instance.display_progress
            self.fields["progress"].help_text = "Otomatis dihitung dari bobot detail activity."
        style_form(self, primary=primary)
        if "collaborators" in self.fields:
            self.fields[
                "collaborators"
            ].help_text = "Pilih satu rekan. Kedua orang dapat update pekerjaan yang sama."
        if "title" in self.fields:
            self.fields["title"].widget.attrs["placeholder"] = "Apa yang perlu dikerjakan?"

    @property
    def work_fields(self):
        names = {
            "title",
            "description",
            "status",
            "progress",
            "blocked_reason",
            "blocked_dependency",
        }
        return [self[name] for name in self.fields if name in names]

    @property
    def plan_fields(self):
        names = {field.name for field in self.work_fields}
        return [self[name] for name in self.fields if name not in names]

    def clean(self):
        data = super().clean()
        collaborators = data.get("collaborators")
        if collaborators is not None:
            if collaborators.count() > 1:
                self.add_error(
                    "collaborators", "Pilih maksimal satu rekan; total dua orang per task."
                )
            if collaborators.exists() and not data.get("assignee"):
                self.add_error("assignee", "Pilih orang pertama sebelum menambahkan rekan.")
            if data.get("assignee") and collaborators.filter(pk=data["assignee"].pk).exists():
                self.add_error("collaborators", "Rekan harus berbeda dari orang pertama.")
        dependencies = data.get("dependencies")
        if dependencies is None and self.instance.pk:
            dependencies = self.instance.dependencies.all()
        if (
            dependencies is not None
            and data.get("status") in ("in_progress", "done")
            and dependencies.exclude(status="done").exists()
        ):
            self.add_error("status", "Selesaikan dependency terlebih dahulu.")
        return data

    def clean_dependencies(self):
        dependencies = self.cleaned_data.get("dependencies")
        if not self.instance.pk:
            return dependencies
        seen, pending = set(), list(dependencies)
        while pending:
            task = pending.pop()
            if task.pk == self.instance.pk:
                raise ValidationError("Dependency membentuk siklus. Pilih task lain.")
            if task.pk not in seen:
                seen.add(task.pk)
                pending.extend(task.dependencies.all())
        return dependencies

    def clean_parent_task(self):
        parent = self.cleaned_data.get("parent_task")
        if parent:
            # Let model validation own depth/project rules and inherited phase.
            self.cleaned_data["phase"] = parent.phase
        return parent


class IssueForm(SanitizeRichTextMixin, forms.ModelForm):
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

    def __init__(self, *args, project=None, user=None, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)
        if user:
            from apps.identity.permissions import is_pm

            if not user.is_staff and not is_pm(user):
                for name in ("status", "owner", "resolution"):
                    self.fields.pop(name)
        fill_missing_defaults(self, ["severity", "priority", "status"])
        if user:
            from apps.identity.permissions import visible_projects

            self.fields["project"].queryset = visible_projects(user)
            self.fields["task"].queryset = self.fields["task"].queryset.filter(
                project__in=visible_projects(user)
            )
        # bila form dipakai dalam konteks project, project diambil dari context
        if project is not None:
            self.fields["project"].widget = forms.HiddenInput()
            self.fields["project"].queryset = Project.objects.filter(pk=project.pk)
        if self.project:
            self.fields["task"].queryset = self.project.tasks.all()
        if not self.instance.pk and self.project and "owner" in self.fields:
            self.fields["owner"].initial = None
        # status default open hanya saat create
        if not self.instance.pk and "status" in self.fields:
            self.fields["status"].initial = IssueStatus.OPEN

        if "status" in self.fields:
            self.fields["status"].choices = [
                ("open", "Terbuka"),
                ("in_progress", "Sedang ditangani"),
                ("blocked", "Terhambat"),
                ("resolved", "Diselesaikan"),
                ("closed", "Ditutup"),
            ]
        style_form(
            self,
            primary=(
                ["status", "resolution", "owner", "due_date", "title", "description"]
                if self.instance.pk
                else ["project", "title", "description", "severity", "task"]
            ),
        )

    def clean(self):
        data = super().clean()
        project = self.project or data.get("project")
        task = data.get("task")
        if task and task.project_id != getattr(project, "pk", None):
            self.add_error("task", "Task harus berasal dari project yang dipilih.")
        return data


class TaskCommentForm(forms.ModelForm):
    class Meta:
        model = TaskComment
        fields = ["content"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)


class AttachmentForm(forms.Form):
    file = forms.FileField(label="Lampiran")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].help_text = "Maksimal 10 MB per file."
        style_form(self)

    def clean_file(self):
        file = self.cleaned_data["file"]
        if file.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Maksimal ukuran lampiran 10 MB.")
        return file
