from django import forms

from .models import NotificationPreference


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = ["in_app", "email", "digest"]
        labels = {
            "in_app": "Notifikasi dalam aplikasi",
            "email": "Notifikasi email",
            "digest": "Frekuensi digest",
        }
        help_texts = {
            "in_app": "Tampilkan notifikasi di lonceng aplikasi.",
            "email": "Kirim notifikasi ke alamat email akun Anda.",
            "digest": (
                "Mati mengirim email per notifikasi. Harian atau mingguan "
                "menggabungkan beberapa notifikasi menjadi satu ringkasan."
            ),
        }
