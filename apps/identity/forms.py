from django import forms
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.contrib.auth.models import User
from django.template.loader import render_to_string

from .models import Role, UserProfile
from .permission_catalog import ROLE_DESCRIPTIONS
from .roles import assign_roles, stored_role_codes


class RolePickerWidget(forms.CheckboxSelectMultiple):
    """Kartu pilihan role dengan penjelasan singkat (template khusus)."""

    def render(self, name, value, attrs=None, renderer=None):
        context = self.get_context(name, value, attrs)
        context["widget"]["describedby"] = self.attrs.get("aria-describedby", "")
        return render_to_string("widgets/role_picker.html", context)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        option["description"] = ROLE_DESCRIPTIONS.get(str(value), "")
        return option


class UserFormSections:
    """Kelompokkan field form user menjadi bagian-bagian yang mudah dipindai."""

    section_layout = [
        (
            "Identitas",
            "Nama dan kontak yang tampil di aplikasi.",
            [
                ("first_name", "last_name"),
                "email",
                ("display_name", "job_title"),
            ],
        ),
        (
            "Akun",
            "Dipakai untuk masuk ke Scope.",
            [
                "username",
                ("password1", "password2"),
                "is_active",
            ],
        ),
        (
            "Peran",
            "Menentukan menu dan aksi yang tersedia. Pilih lebih dari satu bila perlu.",
            [
                "roles",
            ],
        ),
    ]

    @property
    def sections(self):
        result = []
        for title, hint, rows in self.section_layout:
            built = []
            for row in rows:
                names = [row] if isinstance(row, str) else list(row)
                fields = [self[name] for name in names if name in self.fields]
                if fields:
                    built.append(fields)
            if built:
                result.append({"title": title, "hint": hint, "rows": built})
        return result


class LocalUserCreateForm(UserFormSections, UserCreationForm):
    roles = forms.MultipleChoiceField(
        choices=Role.choices,
        initial=[Role.MEMBER],
        label="Peran",
        widget=RolePickerWidget,
        help_text="Satu akun dapat memiliki beberapa peran.",
    )
    display_name = forms.CharField(
        required=False,
        max_length=200,
        label="Nama tampilan",
        help_text="Kosongkan untuk memakai nama depan.",
    )
    job_title = forms.CharField(required=False, max_length=200, label="Jabatan")

    class Meta(UserCreationForm.Meta):
        fields = ["username", "first_name", "last_name", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[
            "username"
        ].help_text = "Maksimal 150 karakter. Huruf, angka, dan @/./+/-/_ saja."
        self.fields[
            "password1"
        ].help_text = "Minimal 8 karakter. Gunakan kombinasi yang sulit ditebak."
        self.fields["password2"].help_text = "Masukkan kata sandi yang sama untuk verifikasi."
        self.order_fields(
            [
                "username",
                "first_name",
                "last_name",
                "email",
                "roles",
                "password1",
                "password2",
                "display_name",
                "job_title",
            ]
        )

    def clean_password1(self):
        password = self.cleaned_data.get("password1", "")
        if len(password) < 8:
            raise forms.ValidationError("Kata sandi minimal 8 karakter.")
        return password

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            profile = user.pcc_profile
            assign_roles(user, self.cleaned_data["roles"])
            profile.display_name = self.cleaned_data["display_name"]
            profile.job_title = self.cleaned_data["job_title"]
            profile.save()
        return user


class UserEditForm(UserFormSections, forms.ModelForm):
    roles = forms.MultipleChoiceField(
        choices=Role.choices,
        label="Peran",
        widget=RolePickerWidget,
        help_text="Satu akun dapat memiliki beberapa peran.",
    )
    display_name = forms.CharField(
        required=False,
        max_length=200,
        label="Nama tampilan",
        help_text="Kosongkan untuk memakai nama depan.",
    )
    job_title = forms.CharField(required=False, max_length=200, label="Jabatan")
    is_active = forms.BooleanField(
        required=False,
        label="Akun aktif",
        help_text="Akun nonaktif tidak dapat masuk, tetapi seluruh datanya tetap tersimpan.",
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_active"]
        help_texts = {"username": "Dipakai untuk masuk. Ubah hanya bila diperlukan."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            return
        profile, _ = UserProfile.objects.get_or_create(user=self.instance)
        if not self.is_bound:
            self.initial["roles"] = stored_role_codes(self.instance)
            self.initial["display_name"] = profile.display_name
            self.initial["job_title"] = profile.job_title
        self.order_fields(
            [
                "first_name",
                "last_name",
                "email",
                "username",
                "roles",
                "is_active",
                "display_name",
                "job_title",
            ]
        )

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            profile = user.pcc_profile
            assign_roles(user, self.cleaned_data["roles"])
            profile.display_name = self.cleaned_data["display_name"]
            profile.job_title = self.cleaned_data["job_title"]
            profile.save()
        return user


class StaffPasswordResetForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "Kata sandi baru"
        self.fields[
            "new_password1"
        ].help_text = "Minimal 8 karakter dan tidak terlalu mirip dengan data akun."
        self.fields["new_password2"].label = "Konfirmasi kata sandi baru"
        self.fields["new_password2"].help_text = "Masukkan kata sandi yang sama untuk verifikasi."

    def clean_new_password1(self):
        password = self.cleaned_data.get("new_password1", "")
        if len(password) < 8:
            raise forms.ValidationError("Kata sandi minimal 8 karakter.")
        return password
