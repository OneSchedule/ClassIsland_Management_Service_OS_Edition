from django.urls import path
from core import api_views, manage_api, panel_views

# ── 客户端 API（无需认证）──
client_api_patterns = [
    path(
        "api/v1/client/<uuid:cuid>/manifest",
        api_views.ClientManifestView.as_view(),
        name="client_manifest",
    ),
    path(
        "api/v1/objects/<str:class_identity>/<str:resource_type>.json",
        api_views.ResourceView.as_view(),
        name="client_resource",
    ),
]

# ── 管理面板 API（需要认证）──
manage_api_patterns = [
    path("manage/api/stats/", manage_api.DashboardStatsAPI.as_view(), name="api_stats"),
    path("manage/api/groups/", manage_api.ClassGroupListAPI.as_view(), name="api_groups"),
    path("manage/api/groups/<int:pk>/", manage_api.ClassGroupDetailAPI.as_view(), name="api_group_detail"),
    path("manage/api/clients/", manage_api.ClientListAPI.as_view(), name="api_clients"),
    path("manage/api/clients/<int:pk>/", manage_api.ClientDetailAPI.as_view(), name="api_client_detail"),
    path("manage/api/commands/send/", manage_api.SendCommandAPI.as_view(), name="api_send_command"),
    path("manage/api/commands/broadcast/", manage_api.BroadcastCommandAPI.as_view(), name="api_broadcast"),
    path("manage/api/audit-logs/", manage_api.AuditLogListAPI.as_view(), name="api_audit_logs"),
    path("manage/api/config-uploads/", manage_api.ConfigUploadListAPI.as_view(), name="api_config_uploads"),
]

# ── 管理面板页面 ──
panel_patterns = [
    path("", panel_views.dashboard, name="dashboard"),
    path("login/", panel_views.login_view, name="login"),
    path("logout/", panel_views.logout_view, name="logout"),
    path("manage/groups/", panel_views.class_groups, name="class_groups"),
    path("manage/groups/<int:pk>/", panel_views.class_group_detail, name="class_group_detail"),
    path("manage/clients/", panel_views.clients, name="clients"),
    path("manage/clients/<int:pk>/", panel_views.client_detail, name="client_detail"),
    path("manage/audit/", panel_views.audit_logs, name="audit_logs"),
    path("manage/commands/", panel_views.send_command, name="send_command"),
    path("manage/settings/", panel_views.organization_settings, name="organization_settings"),
]

urlpatterns = client_api_patterns + manage_api_patterns + panel_patterns
