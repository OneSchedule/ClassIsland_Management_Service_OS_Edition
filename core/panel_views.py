"""
管理面板页面视图
"""
import json

from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages

from core.models import (
    Organization, ClassGroup, Client, AuditLog, TimeLayoutConfig,
    SubjectConfig, ClassPlanConfig, DefaultSettingsConfig,
    PolicyConfig, CredentialConfig, ComponentConfig,
)
from core.crypto import generate_server_keypair, get_active_keypair


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("dashboard")
        else:
            messages.error(request, "用户名或密码错误")
    return render(request, "manage/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def dashboard(request):
    """仪表盘首页"""
    org = Organization.objects.first()
    if org is None:
        # 自动创建默认组织
        org = Organization.objects.create(name="ClassIsland 集控")

    keypair = get_active_keypair(org)
    if keypair is None:
        # 自动生成密钥
        keypair = generate_server_keypair(org)

    context = {
        "org": org,
        "total_clients": Client.objects.count(),
        "online_clients": Client.objects.filter(is_online=True).count(),
        "total_groups": ClassGroup.objects.count(),
        "recent_logs": AuditLog.objects.select_related("client")[:10],
        "keypair": keypair,
    }
    return render(request, "manage/dashboard.html", context)


@login_required
def class_groups(request):
    """班级组管理"""
    groups = ClassGroup.objects.select_related("organization").all()
    return render(request, "manage/class_groups.html", {"groups": groups})


@login_required
def class_group_detail(request, pk):
    """班级组详情编辑 —— 选择已创建的配置"""
    group = get_object_or_404(ClassGroup, pk=pk)
    if request.method == "POST":
        group.name = request.POST.get("name", group.name)
        # 关联配置（下拉选择）
        for fk_field, key in [
            ("linked_class_plan_id", "linked_class_plan"),
            ("linked_subjects_id", "linked_subjects"),
            ("linked_default_settings_id", "linked_default_settings"),
            ("linked_policy_id", "linked_policy"),
            ("linked_credential_id", "linked_credential"),
            ("linked_component_id", "linked_component"),
        ]:
            val = request.POST.get(key)
            setattr(group, fk_field, int(val) if val else None)

        # 当关联配置变化时，自动同步 JSON 并递增版本
        _sync_linked_json(group)
        group.save()
        messages.success(request, "已保存")
        return redirect("class_group_detail", pk=pk)

    context = {
        "group": group,
        "class_plans": ClassPlanConfig.objects.all().order_by("name"),
        "subjects_list": SubjectConfig.objects.all().order_by("name"),
        "default_settings_list": DefaultSettingsConfig.objects.all().order_by("name"),
        "policy_list": PolicyConfig.objects.all().order_by("name"),
        "credential_list": CredentialConfig.objects.all().order_by("name"),
        "component_list": ComponentConfig.objects.all().order_by("name"),
    }
    return render(request, "manage/class_group_detail.html", context)


def _sync_linked_json(group):
    """根据关联的配置对象同步 JSON 字段和版本号"""
    mapping = [
        ("linked_class_plan", "class_plans_json", "class_plans_version"),
        ("linked_subjects", "subjects_json", "subjects_version"),
        ("linked_default_settings", "settings_json", "settings_version"),
        ("linked_policy", "policy_json", "policy_version"),
        ("linked_credential", "credential_json", "credential_version"),
        ("linked_component", "components_json", "components_version"),
    ]
    for fk_attr, json_field, ver_field in mapping:
        linked = getattr(group, fk_attr)
        if linked:
            new_data = linked.data_json
            old_data = getattr(group, json_field)
            if new_data != old_data:
                setattr(group, json_field, new_data)
                setattr(group, ver_field, getattr(group, ver_field) + 1)
    # 如果课表有关联，同步其时间表 JSON
    if group.linked_class_plan and group.linked_class_plan.time_layout:
        tl_data = group.linked_class_plan.time_layout.data_json
        if tl_data != group.time_layouts_json:
            group.time_layouts_json = tl_data
            group.time_layouts_version += 1


@login_required
def clients(request):
    """客户端列表"""
    clients_qs = Client.objects.select_related("class_group").all()
    return render(request, "manage/clients.html", {"clients": clients_qs})


@login_required
def download_management_settings(request, client_uid):
    """下载客户端管理连接配置 JSON"""
    client = get_object_or_404(Client, client_uid=client_uid)
    org = Organization.objects.first()
    if org is None:
        org = Organization.objects.create(name="ClassIsland 集控")

    payload = {
        "IsManagementEnabled": False,
        "ManagementServerKind": 1,
        "ManagementServer": org.management_server,
        "ManagementServerGrpc": org.management_server_grpc,
        "ManifestUrlTemplate": "",
        "ClassIdentity": client.client_id or "",
        "IsActive": False,
    }

    response = HttpResponse(
        json.dumps(payload, ensure_ascii=False, indent=2),
        content_type="application/json; charset=utf-8",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="management-settings-{client.client_uid}.json"'
    )
    return response


@login_required
def download_management_settings_template(request):
    """下载通用管理连接配置 JSON（ClassIdentity 为空）"""
    org = Organization.objects.first()
    if org is None:
        org = Organization.objects.create(name="ClassIsland 集控")

    payload = {
        "IsManagementEnabled": False,
        "ManagementServerKind": 1,
        "ManagementServer": org.management_server,
        "ManagementServerGrpc": org.management_server_grpc,
        "ManifestUrlTemplate": "",
        "ClassIdentity": "",
        "IsActive": False,
    }

    response = HttpResponse(
        json.dumps(payload, ensure_ascii=False, indent=2),
        content_type="application/json; charset=utf-8",
    )
    response["Content-Disposition"] = 'attachment; filename="management-settings-template.json"'
    return response


@login_required
def client_detail(request, client_uid):
    """客户端详情"""
    client = get_object_or_404(Client.objects.select_related("class_group"), client_uid=client_uid)
    groups = ClassGroup.objects.all()
    if request.method == "POST":
        group_id = request.POST.get("class_group_id")
        client.class_group_id = int(group_id) if group_id else None
        status_val = request.POST.get("status")
        if status_val is not None:
            client.status = int(status_val)
        client.save()
        messages.success(request, "已更新")
        return redirect("client_detail", client_uid=client.client_uid)
    audit_logs = AuditLog.objects.filter(client=client).order_by("-timestamp_utc")[:20]
    return render(request, "manage/client_detail.html", {
        "client": client,
        "groups": groups,
        "audit_logs": audit_logs,
    })


@login_required
def audit_logs(request):
    """审计日志列表"""
    logs = AuditLog.objects.select_related("client").order_by("-timestamp_utc")[:200]
    return render(request, "manage/audit_logs.html", {"logs": logs})


@login_required
def send_command(request):
    """发送命令页面"""
    clients_qs = Client.objects.select_related("class_group").all()
    groups = ClassGroup.objects.all()
    return render(request, "manage/send_command.html", {
        "clients": clients_qs,
        "groups": groups,
    })


@login_required
def organization_settings(request):
    """组织设置"""
    org = Organization.objects.first()
    if org is None:
        org = Organization.objects.create(name="ClassIsland 集控")

    if request.method == "POST":
        org.name = request.POST.get("name", org.name)
        org.core_version = request.POST.get("core_version", org.core_version)
        org.management_server = request.POST.get("management_server", org.management_server)
        org.management_server_grpc = request.POST.get("management_server_grpc", org.management_server_grpc)
        org.save()

        if "regenerate_key" in request.POST:
            generate_server_keypair(org)
            messages.success(request, "已重新生成密钥对")

        messages.success(request, "已保存")
        return redirect("organization_settings")

    keypair = get_active_keypair(org)
    return render(request, "manage/organization.html", {
        "org": org,
        "keypair": keypair,
    })


CONFIG_TABS = [
    ("class_plans", "课表"),
    ("time_layouts", "时间表"),
    ("subjects", "科目"),
    ("default_settings", "默认设置"),
    ("policy", "策略"),
    ("credential", "凭据"),
    ("components", "组件"),
]


@login_required
def config_editor(request, config_type=None):
    """编辑配置页面"""
    if config_type is None:
        config_type = "class_plans"
    tab_dict = dict(CONFIG_TABS)
    if config_type not in tab_dict:
        config_type = "class_plans"

    context = {
        "config_tabs": CONFIG_TABS,
        "active_tab": config_type,
        "active_label": tab_dict[config_type],
    }
    # 课表需要时间表列表用于选择
    if config_type == "class_plans":
        context["time_layouts"] = TimeLayoutConfig.objects.all().order_by("name")
    return render(request, "manage/config_editor.html", context)
