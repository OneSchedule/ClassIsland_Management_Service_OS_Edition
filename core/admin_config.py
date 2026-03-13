from django.contrib import admin
from .models import (
    Organization, ClassGroup, Client, ServerKeyPair,
    AuditLog, PendingCommand, ConfigUploadRecord,
    TimeLayoutConfig, SubjectConfig, ClassPlanConfig,
    DefaultSettingsConfig, PolicyConfig, CredentialConfig, ComponentConfig,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "core_version", "created_at")


@admin.register(ClassGroup)
class ClassGroupAdmin(admin.ModelAdmin):
    list_display = (
        "name", "class_identity", "organization",
        "class_plans_version", "time_layouts_version", "subjects_version",
        "updated_at",
    )
    list_filter = ("organization",)
    search_fields = ("name", "class_identity")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "client_uid", "client_id", "client_mac",
        "class_group", "status", "is_online", "last_seen",
    )
    list_filter = ("status", "is_online", "class_group")
    search_fields = ("client_uid", "client_id", "client_mac")


@admin.register(ServerKeyPair)
class ServerKeyPairAdmin(admin.ModelAdmin):
    list_display = ("key_id", "organization", "is_active", "created_at")
    list_filter = ("is_active",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("client", "event_type", "timestamp_utc", "received_at")
    list_filter = ("event_type",)
    search_fields = ("client__client_uid",)
    readonly_fields = ("client", "event_type", "payload", "timestamp_utc", "received_at")


@admin.register(PendingCommand)
class PendingCommandAdmin(admin.ModelAdmin):
    list_display = ("client", "command_type", "delivered", "created_at", "delivered_at")
    list_filter = ("command_type", "delivered")


@admin.register(ConfigUploadRecord)
class ConfigUploadRecordAdmin(admin.ModelAdmin):
    list_display = ("client", "config_type", "request_guid", "received_at")
    list_filter = ("config_type",)
    readonly_fields = ("client", "request_guid", "config_type", "payload_json", "received_at")


@admin.register(TimeLayoutConfig)
class TimeLayoutConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "identifier", "updated_at")
    search_fields = ("name", "identifier")


@admin.register(SubjectConfig)
class SubjectConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "identifier", "updated_at")
    search_fields = ("name", "identifier")


@admin.register(ClassPlanConfig)
class ClassPlanConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "identifier", "time_layout", "updated_at")
    search_fields = ("name", "identifier")
    list_filter = ("time_layout",)


@admin.register(DefaultSettingsConfig)
class DefaultSettingsConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "identifier", "updated_at")
    search_fields = ("name", "identifier")


@admin.register(PolicyConfig)
class PolicyConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "identifier", "updated_at")
    search_fields = ("name", "identifier")


@admin.register(CredentialConfig)
class CredentialConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "identifier", "updated_at")
    search_fields = ("name", "identifier")


@admin.register(ComponentConfig)
class ComponentConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "identifier", "updated_at")
    search_fields = ("name", "identifier")
