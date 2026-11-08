"""Adaptive Card payloads for Teams webhooks.

Both Incoming Webhooks and Workflows ("When a Teams webhook request is
received") accept a ``message`` envelope with one Adaptive Card attachment.
Version 1.4 is the highest version Workflows renders reliably.
"""

from apps.notifications.delivery import absolute_url

CARD_VERSION = "1.4"
CARD_SCHEMA = "http://adaptivecards.io/schemas/adaptive-card.json"
#: Teams rejects messages above ~28 KB; keep text well below that.
MAX_TEXT = 1500
MAX_FACTS = 12

#: Adaptive Card text colors: default, accent, good, warning, attention.
TONES = {"default", "accent", "good", "warning", "attention"}


def _clip(value, limit=MAX_TEXT) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_card(
    title: str,
    *,
    text: str = "",
    facts=None,
    url: str = "",
    tone: str = "default",
    context: str = "Scope",
    items=None,
) -> dict:
    """Return a Teams ``message`` with a single Adaptive Card attachment."""
    tone = tone if tone in TONES else "default"
    body = [
        {
            "type": "TextBlock",
            "text": _clip(context, 120),
            "size": "Small",
            "isSubtle": True,
            "spacing": "None",
            "wrap": True,
        },
        {
            "type": "TextBlock",
            "text": _clip(title, 200),
            "size": "Medium",
            "weight": "Bolder",
            "color": tone,
            "wrap": True,
        },
    ]
    if text:
        body.append({"type": "TextBlock", "text": _clip(text), "wrap": True})
    fact_rows = [
        {"title": _clip(label, 60), "value": _clip(value, 300)}
        for label, value in (facts or [])
        if value not in (None, "")
    ][:MAX_FACTS]
    if fact_rows:
        body.append({"type": "FactSet", "facts": fact_rows})
    for line in (items or [])[:15]:
        body.append(
            {"type": "TextBlock", "text": f"- {_clip(line, 300)}", "wrap": True, "spacing": "Small"}
        )
    card = {
        "$schema": CARD_SCHEMA,
        "type": "AdaptiveCard",
        "version": CARD_VERSION,
        "body": body,
        "msteams": {"width": "Full"},
    }
    if url:
        card["actions"] = [
            {"type": "Action.OpenUrl", "title": "Buka di Scope", "url": absolute_url(url)}
        ]
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": card,
            }
        ],
    }


def card_title(payload: dict) -> str:
    try:
        return payload["attachments"][0]["content"]["body"][1]["text"]
    except (KeyError, IndexError, TypeError):
        return ""
