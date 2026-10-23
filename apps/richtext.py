"""Konten kaya (WYSIWYG): sanitasi HTML agar aman dari XSS, plus helper render.

Nilai disimpan sebagai HTML dari editor ringan. Setiap kali ditampilkan, HTML
disanitasi lewat allowlist nh3, dan teks lama (tanpa tag) diubah newline menjadi
<br> supaya tetap terbaca.
"""

import re

import nh3
from django.utils.html import escape

# Field model yang memakai editor kaya.
RICH_FIELDS = {
    "content",
    "description",
    "decision",
    "context",
    "reason",
    "impact",
    "mitigation",
    "resolution",
}

ALLOWED_TAGS = {
    "a", "b", "strong", "i", "em", "u", "s", "p", "br",
    "ul", "ol", "li", "blockquote", "code", "pre", "h3", "h4",
}
ALLOWED_ATTRIBUTES = {"a": {"href", "title"}}


def sanitize_html(value: str) -> str:
    """Buang tag/atribut di luar allowlist. Aman dipakai untuk disimpan."""
    return nh3.clean(
        value or "",
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        link_rel="noopener noreferrer nofollow",
    )


def strip_html(value: str) -> str:
    """Teks polos tanpa tag, untuk kartu ringkas/preview."""
    return nh3.clean(value or "", tags=set(), strip_comments=True)


def render_html(value: str, mentions: bool = False) -> str:
    """HTML siap tampil: teks lama di-escape + newline jadi <br>, HTML disanitasi."""
    value = value or ""
    if "<" not in value:
        rendered = escape(value).replace("\n", "<br>")
    else:
        rendered = sanitize_html(value)
    return highlight_mentions(rendered) if mentions else rendered


#: Handles are limited to the same characters Django allows in a username, so the
#: match itself is safe to place back into HTML without further escaping.
MENTION_RE = re.compile(r"(?<![A-Za-z0-9_.@+\-])@([A-Za-z0-9_.@+\-]+)")
MENTION_TAG = '<strong class="mention">@{}</strong>'


def highlight_mentions(value: str) -> str:
    """Wrap ``@username`` in a span, only inside text nodes of sanitized HTML."""
    parts = re.split(r"(<[^>]*>)", value or "")
    for index, part in enumerate(parts):
        if not part or part.startswith("<"):
            continue
        parts[index] = MENTION_RE.sub(
            lambda match: MENTION_TAG.format(match.group(1)),
            part,
        )
    return "".join(parts)


class SanitizeRichTextMixin:
    """Form mixin: sanitasi field kaya sebelum disimpan."""

    def clean(self):
        data = super().clean()
        for name in RICH_FIELDS:
            if isinstance(data.get(name), str):
                data[name] = sanitize_html(data[name])
        return data