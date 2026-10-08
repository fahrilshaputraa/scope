from django import forms
from django.db.models import Q

from apps.form_widgets import fill_missing_defaults, style_form
from apps.richtext import SanitizeRichTextMixin

from .models import Decision, Milestone, Note, Phase, ProgressBaselinePoint, Project, Risk


class ProjectForm(SanitizeRichTextMixin, forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            "name",
            "code",
            "description",
            "manager",
            "members",
            "current_phase",
            "team",
            "start_date",
            "target_end_date",
            "status",
            "progress_override",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth.models import User

        self.fields["manager"].queryset = User.objects.filter(is_active=True).filter(
            Q(pcc_profile__role="pm") | Q(is_staff=True)
        )
        self.fields["members"].queryset = User.objects.filter(is_active=True)
        self.fields["current_phase"].queryset = (
            self.instance.phases.all() if self.instance.pk else Phase.objects.none()
        )
        if user and not user.is_staff:
            self.fields["manager"].queryset = User.objects.filter(pk=user.pk)
            self.fields["manager"].initial = user
            self.fields["manager"].required = True
        if not self.instance.pk:
            self.fields.pop("current_phase")
        from uuid import uuid4

        from django.utils import timezone

        self._new_code = "PRJ-" + uuid4().hex[:10].upper()
        self.fields["code"].required = False
        self.fields["code"].help_text = "Dibuat otomatis jika dikosongkan."
        if not self.instance.pk:
            self.initial["manager"] = self.initial.get("manager") or user
            self.initial["start_date"] = self.initial.get("start_date") or timezone.localdate()
            self.initial["target_end_date"] = self.initial.get("target_end_date") or (
                timezone.localdate() + timezone.timedelta(days=30)
            )
        fill_missing_defaults(self, ["manager", "start_date", "target_end_date", "status"])
        style_form(self, primary=["name", "target_end_date", "members"])
        self.fields["name"].widget.attrs["placeholder"] = "Contoh: Peluncuran portal pelanggan"
        self.fields[
            "members"
        ].help_text = "Pilih tim yang akan mengerjakan project. Bisa ditambah nanti."

    def clean_code(self):
        return self.cleaned_data.get("code") or self.instance.code or self._new_code


class PhaseForm(forms.ModelForm):
    class Meta:
        model = Phase
        fields = ["name", "sequence", "start_date", "end_date", "status"]

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project:
            self.instance.project = project
        if project and not self.instance.pk:
            from django.db.models import Max

            self.initial["sequence"] = (
                project.phases.aggregate(last=Max("sequence"))["last"] or 0
            ) + 1
        fill_missing_defaults(self, ["sequence", "status"])
        style_form(self, primary=["name", "start_date", "end_date"])

    def clean_sequence(self):
        sequence = self.cleaned_data["sequence"]
        if (
            self.instance.project_id
            and Phase.objects.filter(project_id=self.instance.project_id, sequence=sequence)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError("Urutan phase sudah digunakan. Pilih urutan lain.")
        return sequence


class MilestoneForm(SanitizeRichTextMixin, forms.ModelForm):
    class Meta:
        model = Milestone
        fields = ["name", "date", "status", "owner", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self, primary=["name", "date", "owner"])


class BaselinePointForm(forms.ModelForm):
    class Meta:
        model = ProgressBaselinePoint
        fields = ["date", "planned_percent", "label"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self, primary=["date", "planned_percent"])


class NoteForm(SanitizeRichTextMixin, forms.ModelForm):
    class Meta:
        model = Note
        fields = ["title", "content", "tags"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self, primary=["title", "content"])


class DecisionForm(SanitizeRichTextMixin, forms.ModelForm):
    class Meta:
        model = Decision
        fields = ["title", "decision", "context", "reason", "impact", "decision_maker"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self, primary=["title", "decision", "decision_maker"])


class RiskForm(SanitizeRichTextMixin, forms.ModelForm):
    class Meta:
        model = Risk
        fields = ["title", "severity", "status", "owner", "due_date", "mitigation"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self, primary=["title", "mitigation", "owner"])


class MembersForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["members"]
        widgets = {"members": forms.CheckboxSelectMultiple()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["members"].queryset = self.fields["members"].queryset.filter(is_active=True)
        style_form(self)
