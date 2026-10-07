from django import forms

from .models import Decision, Milestone, Note, Phase, ProgressBaselinePoint, Project


def _style(attrs=None):
    base = (
        "flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm "
        "shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 "
        "focus-visible:ring-ring"
    )
    if attrs:
        attrs = dict(attrs)
        attrs["class"] = base + " " + attrs.get("class", "")
        return attrs
    return {"class": base}


def _style_textarea():
    return {
        "class": (
            "flex min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 "
            "text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 "
            "focus-visible:ring-ring"
        )
    }


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            "name",
            "code",
            "description",
            "manager",
            "team",
            "start_date",
            "target_end_date",
            "status",
            "progress_override",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field == "description":
                self.fields[field].widget.attrs.update(_style_textarea())
            else:
                self.fields[field].widget.attrs.update(_style())


class PhaseForm(forms.ModelForm):
    class Meta:
        model = Phase
        fields = ["name", "sequence", "start_date", "end_date", "status"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update(_style())


class MilestoneForm(forms.ModelForm):
    class Meta:
        model = Milestone
        fields = ["name", "date", "status", "owner", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update(
                _style_textarea() if field == "description" else _style()
            )


class BaselinePointForm(forms.ModelForm):
    class Meta:
        model = ProgressBaselinePoint
        fields = ["date", "planned_percent", "label"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update(_style())


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ["title", "content", "tags"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update(
                _style_textarea() if field == "content" else _style()
            )


class DecisionForm(forms.ModelForm):
    class Meta:
        model = Decision
        fields = ["title", "decision", "context", "reason", "impact", "decision_maker"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            textarea = field in ("decision", "context", "reason", "impact")
            self.fields[field].widget.attrs.update(
                _style_textarea() if textarea else _style()
            )