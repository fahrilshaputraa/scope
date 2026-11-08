from django.contrib import admin

from .models import (
    CalendarFeedToken,
    DeliveryLog,
    OutlookConnection,
    OutlookEvent,
    ProjectHealthMark,
    TeamsWebhook,
)


@admin.register(TeamsWebhook)
class TeamsWebhookAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "is_active", "url_hint", "last_status", "last_delivery_at")
    list_filter = ("is_active", "last_status")
    search_fields = ("name", "project__name", "project__code")
    # The encrypted URL is never editable or shown in admin.
    exclude = ("url_encrypted",)
    readonly_fields = ("url_hint", "last_delivery_at", "last_status", "last_error", "created_by")


@admin.register(DeliveryLog)
class DeliveryLogAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "webhook",
        "event",
        "status",
        "attempts",
        "response_code",
        "created_at",
    )
    list_filter = ("status", "event")
    search_fields = ("title", "dedupe_key")
    readonly_fields = [field.name for field in DeliveryLog._meta.fields]


@admin.register(CalendarFeedToken)
class CalendarFeedTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "last_accessed_at")
    exclude = ("token",)
    readonly_fields = ("user", "created_at", "last_accessed_at")


@admin.register(OutlookConnection)
class OutlookConnectionAdmin(admin.ModelAdmin):
    list_display = ("user", "account_email", "expires_at", "connected_at")
    exclude = ("access_token_encrypted", "refresh_token_encrypted")
    readonly_fields = ("user", "account_email", "scope", "expires_at", "connected_at")


admin.site.register(OutlookEvent)
admin.site.register(ProjectHealthMark)
