from django import forms
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Role, UserProfile


class LocalUserCreateForm(UserCreationForm):
    role = forms.ChoiceField(choices=Role.choices, initial=Role.MEMBER, label="Peran")
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
        self.fields["username"].help_text = (
            "Maksimal 150 karakter. Huruf, angka, dan @/./+/-/_ saja."
        )
        self.fields["password1"].help_text = (
            "Minimal 8 karakter. Gunakan kombinasi yang sulit ditebak."
        )
        self.fields["password2"].help_text = "Masukkan kata sandi yang sama untuk verifikasi."
        self.order_fields(
            [
                "username",
                "first_name",
                "last_name",
                "email",
                "role",
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
            profile.role = self.cleaned_data["role"]
            profile.display_name = self.cleaned_data["display_name"]
            profile.job_title = self.cleaned_data["job_title"]
            profile.save()
        return user


class UserEditForm(forms.ModelForm):
    role = forms.ChoiceField(choices=Role.choices, label="Peran")
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
            self.initial["role"] = profile.role
            self.initial["display_name"] = profile.display_name
            self.initial["job_title"] = profile.job_title
        self.order_fields(
            [
                "first_name",
                "last_name",
                "email",
                "username",
                "role",
                "is_active",
                "display_name",
                "job_title",
            ]
        )

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            profile = user.pcc_profile
            profile.role = self.cleaned_data["role"]
            profile.display_name = self.cleaned_data["display_name"]
            profile.job_title = self.cleaned_data["job_title"]
            profile.save()
        return user


class StaffPasswordResetForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "Kata sandi baru"
        self.fields["new_password1"].help_text = (
            "Minimal 8 karakter dan tidak terlalu mirip dengan data akun."
        )
        self.fields["new_password2"].label = "Konfirmasi kata sandi baru"
        self.fields["new_password2"].help_text = (
            "Masukkan kata sandi yang sama untuk verifikasi."
        )

    def clean_new_password1(self):
        password = self.cleaned_data.get("new_password1", "")
        if len(password) < 8:
            raise forms.ValidationError("Kata sandi minimal 8 karakter.")
        return password
