"""
管理面板页面视图
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages

from core.models import Organization, ClassGroup, Client, AuditLog
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
    """班级组详情编辑"""
    group = get_object_or_404(ClassGroup, pk=pk)
    if request.method == "POST":
        group.name = request.POST.get("name", group.name)
        # 更新各资源 JSON
        import json
        for field in ["class_plans", "time_layouts", "subjects", "settings", "policy", "components", "credential"]:
            json_field = f"{field}_json"
            raw = request.POST.get(json_field, "")
            if raw.strip():
                try:
                    parsed = json.loads(raw)
                    setattr(group, json_field, parsed)
                    ver_field = f"{field}_version"
                    setattr(group, ver_field, getattr(group, ver_field) + 1)
                except json.JSONDecodeError:
                    messages.error(request, f"{field} JSON 格式错误")
        group.save()
        messages.success(request, "已保存")
        return redirect("class_group_detail", pk=pk)
    return render(request, "manage/class_group_detail.html", {"group": group})


@login_required
def clients(request):
    """客户端列表"""
    clients_qs = Client.objects.select_related("class_group").all()
    return render(request, "manage/clients.html", {"clients": clients_qs})


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
