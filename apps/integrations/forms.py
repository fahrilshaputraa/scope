from django import forms

from .models import DEFAULT_EVENTS, SELECTABLE_EVENTS
from .validators import validate_webhook_url

GLOBAL_SCOPE = "global"


class TeamsWebhookForm(forms.Form):
    name = forms.CharField(
        label="Nama",
        max_length=120,
        help_text="Contoh: Channel PM · Proyek Alpha.",
    )
    scope = forms.ChoiceField(
        label="Cakupan",
        help_text="Global menerima event dari semua project aktif.",
    )
    url = forms.CharField(
        label="URL webhook",
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "off"}),
        help_text=(
            "Tempel URL dari Teams (Incoming Webhook) atau Workflows. URL disimpan "
            "terenkripsi dan tidak ditampilkan lagi."
        ),
    )
    events = forms.MultipleChoiceField(
        label="Event yang dikirim",
        choices=SELECTABLE_EVENTS,
        widget=forms.CheckboxSelectMultiple,
        initial=DEFAULT_EVENTS,
    )
    is_active = forms.BooleanField(label="Aktif", required=False, initial=True)

    def __init__(self, *args, projects=None, allow_global=False, instance=None, **kwargs):
        self.instance = instance
        if instance is not None and "initial" not in kwargs:
            kwargs["initial"] = {
                "name": instance.name,
                "scope": str(instance.project_id) if instance.project_id else GLOBAL_SCOPE,
                "events": instance.events,
                "is_active": instance.is_active,
            }
        super().__init__(*args, **kwargs)
        self.projects = {str(project.pk): project for project in (projects or [])}
        choices = []
        if allow_global:
            choices.append((GLOBAL_SCOPE, "Global (semua project)"))
        choices += [(pk, f"{p.code} · {p.name}") for pk, p in self.projects.items()]
        self.fields["scope"].choices = choices
        if instance is not None:
            self.fields[
                "url"
            ].help_text = f"Tersimpan: {instance.url_hint}. Kosongkan untuk mempertahankan URL ini."
        else:
            self.fields["url"].required = True
        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.CheckboxSelectMultiple, forms.CheckboxInput)):
                continue
            field.widget.attrs["class"] = "pcc-field"
            if field.help_text:
                field.widget.attrs["aria-describedby"] = f"help-{name}"

    def clean_url(self):
        value = self.cleaned_data.get("url", "").strip()
        if not value and self.instance is not None:
            return ""
        return validate_webhook_url(value)

    def clean_scope(self):
        value = self.cleaned_data["scope"]
        if value == GLOBAL_SCOPE:
            return None
        project = self.projects.get(value)
        if project is None:
            raise forms.ValidationError("Pilih project yang Anda kelola.")
        return project

    def save(self, user):
        from .models import TeamsWebhook

        webhook = self.instance or TeamsWebhook(created_by=user)
        webhook.name = self.cleaned_data["name"]
        webhook.project = self.cleaned_data["scope"]
        webhook.events = list(self.cleaned_data["events"])
        webhook.is_active = self.cleaned_data["is_active"]
        if self.cleaned_data.get("url"):
            webhook.set_url(self.cleaned_data["url"])
        webhook.save()
        return webhook
