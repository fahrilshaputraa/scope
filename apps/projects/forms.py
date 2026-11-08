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
            "project_type",
            "description",
            "manager",
            "owner",
            "members",
            "current_phase",
            "team",
            "start_date",
            "target_end_date",
            "lifecycle_status",
            "cancellation_reason",
            "progress_override",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth.models import User

        self.fields["manager"].queryset = (
            User.objects.filter(is_active=True)
            .filter(Q(memberships__role__code="pm") | Q(is_staff=True))
            .distinct()
        )
        self.fields["owner"].queryset = (
            User.objects.filter(is_active=True)
            .filter(Q(memberships__role__code="owner") | Q(is_staff=True))
            .distinct()
        )
        # Owner wajib untuk project baru; project lama tanpa owner boleh tetap kosong.
        self.fields["owner"].required = not (self.instance.pk and not self.instance.owner_id)
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
            from .models import ProjectTemplate

            self.fields["template"] = forms.ModelChoiceField(
                queryset=ProjectTemplate.objects.filter(is_active=True),
                required=False,
                label="Mulai dari template",
                empty_label="Tanpa template (rencana kosong)",
                help_text="Phase, work package, task, milestone, dan aturan disalin ke project. "
                "Mengubah template nanti tidak mengubah project ini.",
            )
        from uuid import uuid4

        from django.utils import timezone

        self._new_code = "PRJ-" + uuid4().hex[:10].upper()
        self.fields["code"].required = False
        self.fields["code"].help_text = "Dibuat otomatis jika dikosongkan."
        if not self.instance.pk:
            self.initial["manager"] = self.initial.get("manager") or user
            # Default pintar: pembuat menjadi Project Owner bila boleh, atau satu-satunya
            # calon Owner yang tersedia.
            if not self.initial.get("owner"):
                candidates = self.fields["owner"].queryset
                if user is not None and candidates.filter(pk=user.pk).exists():
                    self.initial["owner"] = user
                else:
                    owners = list(candidates[:2])
                    if len(owners) == 1:
                        self.initial["owner"] = owners[0]
            self.initial["start_date"] = self.initial.get("start_date") or timezone.localdate()
            self.initial["target_end_date"] = self.initial.get("target_end_date") or (
                timezone.localdate() + timezone.timedelta(days=30)
            )
        fill_missing_defaults(
            self, ["manager", "start_date", "target_end_date", "lifecycle_status", "project_type"]
        )
        style_form(
            self,
            primary=["name", "template", "project_type", "owner", "target_end_date", "members"],
        )
        self.fields["project_type"].label = "Jenis project"
        self.fields["owner"].label = "Project Owner"
        self.fields["owner"].help_text = "Penanggung jawab outcome project."
        self.fields["name"].widget.attrs["placeholder"] = "Contoh: Peluncuran portal pelanggan"
        self.fields[
            "members"
        ].help_text = "Pilih tim yang akan mengerjakan project. Bisa ditambah nanti."

    def clean_code(self):
        return self.cleaned_data.get("code") or self.instance.code or self._new_code


PLAN_SOURCES = [
    ("blank", "Mulai kosong"),
    ("paste", "Tempel daftar task"),
    ("template", "Dari template"),
    ("ai", "Import rencana dari AI"),
]


class ProjectCreateForm(ProjectForm):
    """Wizard 'Buat project' tiga langkah: data inti, sumber rencana, tinjau."""

    STEP_ONE = ["name", "start_date", "target_end_date", "manager", "owner"]
    ADVANCED = ["code", "project_type", "team", "lifecycle_status", "description", "members"]

    source = forms.ChoiceField(
        choices=PLAN_SOURCES,
        initial="blank",
        required=False,
        widget=forms.RadioSelect,
        label="Sumber rencana",
    )
    plan_text = forms.CharField(
        required=False,
        label="Daftar task",
        widget=forms.Textarea(attrs={"rows": 8}),
        help_text="Satu task per baris. Tambahkan | jumlah hari untuk durasi (bawaan 5 hari). "
        "Baris tanpa awalan menjadi phase bila Anda memakai - untuk task.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("progress_override", "cancellation_reason"):
            self.fields.pop(name, None)
        status = self.fields["lifecycle_status"]
        status.choices = [c for c in status.choices if c[0] in ("draft", "planning")]
        status.help_text = "Project mulai dari Perencanaan; ubah ke Berjalan setelah siap."
        self.fields["plan_text"].widget.attrs.update(
            {
                "class": "pcc-field",
                "placeholder": "Analisis kebutuhan | 3\nDesain UI | 5\nPengembangan | 10\nUji coba",
                "aria-describedby": "help-plan_text",
            }
        )
        self.fields[
            "target_end_date"
        ].help_text = "Terisi otomatis dari tanggal mulai dan durasi rencana; boleh diubah."
        if "template" in self.fields:
            self.fields["template"].label = "Template"
            self.fields[
                "template"
            ].help_text = (
                "Phase, task, milestone, dan aturan disalin. Tanggal mengikuti tanggal mulai."
            )
        self._bound_fields_cache.clear()
        self.step_one = [self[name] for name in self.STEP_ONE if name in self.fields]
        self.advanced = [self[name] for name in self.ADVANCED if name in self.fields]

    def clean(self):
        cleaned = super().clean()
        # Tanpa pilihan eksplisit (klien lama): template bila dipilih, selain itu kosong.
        source = cleaned.get("source") or ("template" if cleaned.get("template") else "blank")
        cleaned["source"] = source
        if source == "template" and not cleaned.get("template"):
            self.add_error("template", "Pilih template, atau pilih sumber rencana lain.")
        if source == "paste":
            from django.core.exceptions import ValidationError

            from .project_templates import plain_list_structure

            try:
                cleaned["plan_structure"] = plain_list_structure(cleaned.get("plan_text", ""))
            except ValidationError as exc:
                self.add_error("plan_text", exc.messages[0])
        return cleaned


class ApplyTemplateForm(forms.Form):
    """Pakai template pada project yang jadwalnya masih kosong."""

    template = forms.ModelChoiceField(queryset=None, label="Template", empty_label="Pilih template")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import ProjectTemplate

        self.fields["template"].queryset = ProjectTemplate.objects.filter(is_active=True)
        self.fields[
            "template"
        ].help_text = "Phase, task, milestone, dan aturan disalin mulai dari tanggal mulai project."
        style_form(self)


class PasteTasksForm(forms.Form):
    """Tempel daftar task tanpa JavaScript Gantt (mis. dari Ringkasan atau mobile)."""

    plan_text = forms.CharField(
        label="Daftar task",
        widget=forms.Textarea(attrs={"rows": 10}),
        help_text="Satu task per baris; | jumlah hari untuk durasi (bawaan 5 hari). Baris tanpa "
        "awalan menjadi phase bila Anda memakai - untuk task.",
    )
    start_date = forms.DateField(label="Mulai dari")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)
        self.fields["plan_text"].widget.attrs["placeholder"] = (
            "Analisis kebutuhan | 3\nDesain UI | 5\nPengembangan | 10"
        )

    def clean_plan_text(self):
        from django.core.exceptions import ValidationError

        from .project_templates import plain_list_structure

        text = self.cleaned_data["plan_text"]
        try:
            self.structure = plain_list_structure(text)
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages[0]) from exc
        return text


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
        fields = [
            "title",
            "decision",
            "context",
            "reason",
            "impact",
            "decision_maker",
            "related_issue",
        ]

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project is not None:
            self.instance.project = project
            self.fields["related_issue"].queryset = project.issues.all()
        style_form(self, primary=["title", "decision", "decision_maker", "related_issue"])
        self.fields["related_issue"].label = "Issue terkait (opsional)"
        self.fields["related_issue"].empty_label = "Tidak terkait issue"


class RiskForm(SanitizeRichTextMixin, forms.ModelForm):
    class Meta:
        model = Risk
        fields = [
            "title",
            "probability",
            "impact",
            "owner",
            "mitigation",
            "review_date",
            "status",
            "description",
        ]

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("probability", "impact", "owner", "mitigation", "review_date"):
            self.fields[name].required = True
        if project is not None:
            from django.contrib.auth.models import User

            people = Q(member_projects=project) | Q(pk=project.manager_id) | Q(pk=project.owner_id)
            current = self.instance.owner_id or 0
            self.fields["owner"].queryset = (
                User.objects.filter(is_active=True).filter(people | Q(pk=current)).distinct()
            )
        self.fields["status"].choices = [
            ("open", "Terbuka"),
            ("mitigated", "Termitigasi"),
            ("closed", "Ditutup"),
        ] + ([("converted", "Menjadi masalah")] if self.instance.status == "converted" else [])
        style_form(
            self,
            primary=["title", "probability", "impact", "owner", "mitigation", "review_date"],
        )
        self.fields["probability"].label = "Kemungkinan terjadi"
        self.fields["impact"].label = "Dampak"
        self.fields["review_date"].label = "Tanggal tinjau"
        self.fields[
            "impact"
        ].help_text = "Skor risiko = kemungkinan × dampak (1–25). Tingkatnya dihitung otomatis."


class MembersForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["members"]
        widgets = {"members": forms.CheckboxSelectMultiple()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["members"].queryset = self.fields["members"].queryset.filter(is_active=True)
        style_form(self)
