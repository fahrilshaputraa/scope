from django import forms

from apps.form_widgets import style_form

from .models import ApprovalMode, ApprovalType, ChangeRequest, Deliverable
from .services import MAX_APPROVERS, approver_candidates


class ApprovalPolicyForm(forms.Form):
    enabled = forms.BooleanField(required=False, label="Wajib persetujuan")
    mode = forms.ChoiceField(choices=ApprovalMode.choices, label="Urutan persetujuan")
    allow_self_approval = forms.BooleanField(
        required=False,
        label="Izinkan self-approval",
        help_text="Bila tidak dicentang, pengaju tidak bisa menyetujui pengajuannya sendiri.",
    )

    def __init__(self, *args, project, approval_type, policy=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.approval_type = approval_type
        candidates = approver_candidates(project, approval_type)
        current = policy.ordered_approvers() if policy else []
        for index in range(1, MAX_APPROVERS + 1):
            name = f"approver_{index}"
            self.fields[name] = forms.ModelChoiceField(
                queryset=candidates,
                required=False,
                label=f"Approver {index}",
            )
            if len(current) >= index:
                self.initial[name] = current[index - 1].pk
        if policy:
            self.initial.update(
                enabled=policy.enabled,
                mode=policy.mode,
                allow_self_approval=policy.allow_self_approval,
            )
        style_form(self)
        defaults = {
            ApprovalType.TASK: "Kosongkan untuk memakai reviewer task, atau PM bila task "
            "tidak punya reviewer.",
            ApprovalType.DELIVERABLE: "Kosongkan untuk memakai reviewer deliverable atau "
            "Project Owner.",
        }
        self.fields["approver_1"].help_text = defaults.get(
            approval_type, "Kosongkan untuk memakai Project Owner."
        )
        self.fields[
            "enabled"
        ].help_text = "Default mati: alur berjalan tanpa persetujuan sampai diaktifkan."
        for index in range(1, MAX_APPROVERS + 1):
            self.fields[f"approver_{index}"].empty_label = "Belum dipilih"

    def approvers(self):
        return [
            self.cleaned_data.get(f"approver_{i}")
            for i in range(1, MAX_APPROVERS + 1)
            if self.cleaned_data.get(f"approver_{i}")
        ]


class DecisionForm(forms.Form):
    decision = forms.ChoiceField(
        choices=[("approve", "Setujui"), ("reject", "Tolak")],
        label="Keputusan",
        widget=forms.RadioSelect,
    )
    reason = forms.CharField(
        required=False,
        label="Alasan atau catatan",
        widget=forms.Textarea,
        help_text="Wajib diisi bila menolak.",
        max_length=2000,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)
        self.fields["decision"].widget.attrs.pop("class", None)

    def clean(self):
        data = super().clean()
        if data.get("decision") == "reject" and not (data.get("reason") or "").strip():
            self.add_error("reason", "Alasan penolakan wajib diisi.")
        return data


class NoteForm(forms.Form):
    note = forms.CharField(
        required=False,
        label="Catatan untuk approver",
        widget=forms.Textarea,
        max_length=2000,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)


class ChangeRequestForm(forms.ModelForm):
    class Meta:
        model = ChangeRequest
        fields = [
            "title",
            "reason",
            "impact_assessment",
            "proposed_end_date",
            "classification",
            "description",
            "schedule_impact",
            "scope_impact",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self, primary=["title", "reason", "impact_assessment", "proposed_end_date"])
        labels = {
            "title": "Judul perubahan",
            "reason": "Alasan perubahan",
            "impact_assessment": "Penilaian dampak",
            "proposed_end_date": "Target selesai baru (opsional)",
            "classification": "Klasifikasi",
            "description": "Rincian perubahan",
            "schedule_impact": "Dampak jadwal",
            "scope_impact": "Dampak scope",
        }
        for name, label in labels.items():
            self.fields[name].label = label
        self.fields["classification"].help_text = (
            "Major: deadline, scope, bobot, milestone, atau deliverable. "
            "Minor: koreksi teks dan informasi tambahan."
        )
        self.fields["title"].widget.attrs["placeholder"] = "Contoh: Mundurkan go-live 2 minggu"


class ChangeControlForm(forms.Form):
    change_control = forms.BooleanField(
        required=False,
        label="Aktifkan kontrol perubahan",
        help_text="Setelah baseline berlaku, perubahan deadline project, tanggal milestone, "
        "bobot task, dan deliverable harus melalui change request yang disetujui.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)


class DeliverableForm(forms.ModelForm):
    class Meta:
        model = Deliverable
        fields = [
            "name",
            "task",
            "acceptance_criteria",
            "owner",
            "reviewer",
            "due_date",
            "description",
            "evidence",
        ]

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth.models import User
        from django.db.models import Q

        self.instance.project = project
        self.fields["task"].queryset = project.tasks.all()
        people = Q(member_projects=project) | Q(pk=project.manager_id) | Q(pk=project.owner_id)
        self.fields["owner"].queryset = (
            User.objects.filter(is_active=True).filter(people).distinct()
        )
        self.fields["reviewer"].queryset = approver_candidates(project, ApprovalType.DELIVERABLE)
        style_form(self, primary=["name", "task", "acceptance_criteria", "owner", "due_date"])
        labels = {
            "name": "Nama deliverable",
            "task": "Task terkait",
            "acceptance_criteria": "Kriteria penerimaan",
            "owner": "Pemilik deliverable",
            "reviewer": "Penerima (reviewer)",
            "due_date": "Target diserahkan",
            "description": "Deskripsi",
            "evidence": "Bukti hasil kerja",
        }
        for name, label in labels.items():
            self.fields[name].label = label
        self.fields["reviewer"].empty_label = "Project Owner"
        self.fields["reviewer"].help_text = "Kosongkan agar diterima oleh Project Owner."


class EvidenceForm(forms.ModelForm):
    class Meta:
        model = Deliverable
        fields = ["evidence"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)
        self.fields["evidence"].label = "Bukti hasil kerja"
