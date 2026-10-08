from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def nav_active(context, *prefixes):
    """Kembalikan class CSS aktif bila request.path cocok dengan salah satu prefix.

    Contoh: {% nav_active "/projects" as active %} → class string.
    """
    path = context["request"].path
    for prefix in prefixes:
        if prefix == "/":
            if path == "/":
                return "is-active"
            continue
        clean = prefix.rstrip("/")
        if path == clean or path.startswith(clean + "/"):
            return "is-active"
    return ""
