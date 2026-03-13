"""
管理面板 REST API —— 供管理面板 AJAX 调用。
需要管理员认证。
"""
import json
import uuid

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.models import (
    Organization, ClassGroup, Client, AuditLog,
    PendingCommand, CommandType, ConfigType, ConfigUploadRecord,
)
from core.connection_manager import connection_manager
from core.proto_gen.Protobuf.Server import ClientCommandDeliverScRsp_pb2
from core.proto_gen.Protobuf.Enum import Retcode_pb2, CommandTypes_pb2
from core.proto_gen.Protobuf.Command import (
    GetClientConfig_pb2,
    SendNotification_pb2,
)


def _to_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "on"}:
            return True
        if v in {"0", "false", "no", "off", ""}:
            return False
    return default


def _to_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


class DashboardStatsAPI(LoginRequiredMixin, View):
    """GET /manage/api/stats — 仪表盘统计"""

    def get(self, request):
        return JsonResponse({
            "total_clients": Client.objects.count(),
            "online_clients": Client.objects.filter(is_online=True).count(),
            "total_groups": ClassGroup.objects.count(),
            "total_audit_logs": AuditLog.objects.count(),
            "connected_uids": connection_manager.get_connected_uids(),
        })


class ClassGroupListAPI(APIView):
    """GET/POST /manage/api/groups/"""

    def get(self, request):
        groups = ClassGroup.objects.select_related("organization").all()
        data = [{
            "id": g.id,
            "name": g.name,
            "class_identity": g.class_identity,
            "organization": g.organization.name if g.organization else "",
            "client_count": g.clients.count(),
            "class_plans_version": g.class_plans_version,
            "time_layouts_version": g.time_layouts_version,
            "subjects_version": g.subjects_version,
            "settings_version": g.settings_version,
            "policy_version": g.policy_version,
        } for g in groups]
        return Response(data)

    def post(self, request):
        org = Organization.objects.first()
        if not org:
            return Response({"error": "请先创建组织"}, status=400)
        name = request.data.get("name", "")
        identity = request.data.get("class_identity", "")
        if not name or not identity:
            return Response({"error": "name 和 class_identity 必填"}, status=400)
        if ClassGroup.objects.filter(class_identity=identity).exists():
            return Response({"error": "班级标识已存在"}, status=400)
        g = ClassGroup.objects.create(
            organization=org, name=name, class_identity=identity,
        )
        return Response({"id": g.id, "name": g.name, "class_identity": g.class_identity}, status=201)


class ClassGroupDetailAPI(APIView):
    """GET/PUT/DELETE /manage/api/groups/{id}/"""

    def get(self, request, pk):
        try:
            g = ClassGroup.objects.get(pk=pk)
        except ClassGroup.DoesNotExist:
            return Response({"error": "不存在"}, status=404)
        return Response({
            "id": g.id,
            "name": g.name,
            "class_identity": g.class_identity,
            "class_plans_json": g.class_plans_json,
            "class_plans_version": g.class_plans_version,
            "time_layouts_json": g.time_layouts_json,
            "time_layouts_version": g.time_layouts_version,
            "subjects_json": g.subjects_json,
            "subjects_version": g.subjects_version,
            "settings_json": g.settings_json,
            "settings_version": g.settings_version,
            "policy_json": g.policy_json,
            "policy_version": g.policy_version,
            "components_json": g.components_json,
            "components_version": g.components_version,
            "credential_json": g.credential_json,
            "credential_version": g.credential_version,
        })

    def put(self, request, pk):
        try:
            g = ClassGroup.objects.get(pk=pk)
        except ClassGroup.DoesNotExist:
            return Response({"error": "不存在"}, status=404)

        data = request.data
        for field in ["name", "class_identity"]:
            if field in data:
                setattr(g, field, data[field])

        # 更新资源 JSON
        resource_fields = [
            "class_plans", "time_layouts", "subjects",
            "settings", "policy", "components", "credential",
        ]
        for rf in resource_fields:
            json_key = f"{rf}_json"
            ver_key = f"{rf}_version"
            if json_key in data:
                setattr(g, json_key, data[json_key])
                # 自动递增版本
                current_ver = getattr(g, ver_key)
                setattr(g, ver_key, current_ver + 1)
            if ver_key in data:
                setattr(g, ver_key, data[ver_key])

        g.save()
        return Response({"id": g.id, "message": "已更新"})

    def delete(self, request, pk):
        try:
            g = ClassGroup.objects.get(pk=pk)
        except ClassGroup.DoesNotExist:
            return Response({"error": "不存在"}, status=404)
        g.delete()
        return Response({"message": "已删除"})


class ClientListAPI(APIView):
    """GET /manage/api/clients/"""

    def get(self, request):
        clients = Client.objects.select_related("class_group").all()
        data = [{
            "id": c.id,
            "client_uid": str(c.client_uid),
            "client_id": c.client_id,
            "client_mac": c.client_mac,
            "class_group": c.class_group.name if c.class_group else "未分配",
            "class_group_id": c.class_group_id,
            "status": c.get_status_display(),
            "status_code": c.status,
            "is_online": connection_manager.is_connected(str(c.client_uid)),
            "last_seen": c.last_seen.isoformat() if c.last_seen else None,
            "registered_at": c.registered_at.isoformat(),
        } for c in clients]
        return Response(data)


class ClientDetailAPI(APIView):
    """GET/PUT/DELETE /manage/api/clients/{id}/"""

    def get(self, request, pk):
        try:
            c = Client.objects.select_related("class_group").get(pk=pk)
        except Client.DoesNotExist:
            return Response({"error": "不存在"}, status=404)
        return Response({
            "id": c.id,
            "client_uid": str(c.client_uid),
            "client_id": c.client_id,
            "client_mac": c.client_mac,
            "hostname": c.hostname,
            "class_group_id": c.class_group_id,
            "class_group_name": c.class_group.name if c.class_group else "未分配",
            "status": c.status,
            "is_online": connection_manager.is_connected(str(c.client_uid)),
            "last_seen": c.last_seen.isoformat() if c.last_seen else None,
        })

    def put(self, request, pk):
        try:
            c = Client.objects.get(pk=pk)
        except Client.DoesNotExist:
            return Response({"error": "不存在"}, status=404)

        data = request.data
        if "class_group_id" in data:
            c.class_group_id = data["class_group_id"] or None
        if "status" in data:
            c.status = data["status"]
        if "client_id" in data:
            c.client_id = data["client_id"]
        c.save()
        return Response({"message": "已更新"})

    def delete(self, request, pk):
        try:
            c = Client.objects.get(pk=pk)
        except Client.DoesNotExist:
            return Response({"error": "不存在"}, status=404)
        c.delete()
        return Response({"message": "已删除"})


class SendCommandAPI(APIView):
    """POST /manage/api/commands/send/"""

    def post(self, request):
        client_id = request.data.get("client_id")
        command_type = request.data.get("command_type")

        try:
            client = Client.objects.get(pk=client_id)
        except Client.DoesNotExist:
            return Response({"error": "客户端不存在"}, status=404)

        cmd_type = _to_int(command_type, -1)
        if cmd_type < 0:
            return Response({"error": "command_type 无效"}, status=400)
        payload = b""

        # 构建特殊命令的 payload
        if cmd_type == CommandType.SEND_NOTIFICATION:
            notif = SendNotification_pb2.SendNotification(
                MessageMask=request.data.get("message_mask", ""),
                MessageContent=request.data.get("message_content", ""),
                IsEmergency=_to_bool(request.data.get("is_emergency"), False),
                DurationSeconds=_to_float(request.data.get("duration_seconds"), 5.0),
                RepeatCounts=_to_int(request.data.get("repeat_counts"), 1),
                IsSpeechEnabled=_to_bool(request.data.get("is_speech_enabled"), False),
                IsEffectEnabled=_to_bool(request.data.get("is_effect_enabled"), True),
                IsSoundEnabled=_to_bool(request.data.get("is_sound_enabled"), True),
                IsTopmost=_to_bool(request.data.get("is_topmost"), False),
            )
            payload = notif.SerializeToString()

        elif cmd_type == CommandType.GET_CLIENT_CONFIG:
            config_type = _to_int(request.data.get("config_type"), 0)
            req_guid = str(uuid.uuid4())
            get_cfg = GetClientConfig_pb2.GetClientConfig(
                RequestGuid=req_guid,
                ConfigType=config_type,
            )
            payload = get_cfg.SerializeToString()

        # 先持久化命令，兼容 runserver / grpcserver 分进程部署
        pending = PendingCommand.objects.create(
            client=client,
            command_type=cmd_type,
            payload=payload,
        )

        # 尝试直接推送给在线客户端（仅当前进程内可见连接）
        cuid = str(client.client_uid)
        msg = ClientCommandDeliverScRsp_pb2.ClientCommandDeliverScRsp(
            RetCode=Retcode_pb2.Success,
            Type=cmd_type,
            Payload=payload,
        )
        delivered_now = connection_manager.enqueue_command(cuid, msg)

        # 本进程内已直推，标记为已送达
        if delivered_now:
            from django.utils import timezone as tz
            pending.delivered = True
            pending.delivered_at = tz.now()
            pending.save(update_fields=["delivered", "delivered_at"])

        likely_online = bool(client.is_online)
        if delivered_now:
            message = "已发送"
        elif likely_online:
            message = "客户端在线（跨进程），已加入队列待下发"
        else:
            message = "客户端离线，已加入队列"

        return Response({
            "message": message,
            "delivered": delivered_now,
            "queued": True,
            "client_online": likely_online,
        })


class BroadcastCommandAPI(APIView):
    """POST /manage/api/commands/broadcast/ — 向所有客户端/班级组广播"""

    def post(self, request):
        command_type = int(request.data.get("command_type", CommandType.DATA_UPDATED))
        group_id = request.data.get("group_id")  # 可选，指定班级组

        if group_id:
            clients = Client.objects.filter(class_group_id=group_id)
        else:
            clients = Client.objects.all()

        sent = 0
        queued = 0
        for client in clients:
            cuid = str(client.client_uid)
            msg = ClientCommandDeliverScRsp_pb2.ClientCommandDeliverScRsp(
                RetCode=Retcode_pb2.Success,
                Type=command_type,
            )
            if connection_manager.enqueue_command(cuid, msg):
                sent += 1
            else:
                PendingCommand.objects.create(
                    client=client,
                    command_type=command_type,
                )
                queued += 1

        return Response({
            "message": f"已发送 {sent} 台, 已排队 {queued} 台",
            "sent": sent,
            "queued": queued,
        })


class AuditLogListAPI(APIView):
    """GET /manage/api/audit-logs/"""

    def get(self, request):
        limit = int(request.query_params.get("limit", 100))
        logs = AuditLog.objects.select_related("client").order_by("-timestamp_utc")[:limit]
        data = [{
            "id": log.id,
            "client_uid": str(log.client.client_uid),
            "event_type": log.get_event_type_display(),
            "event_type_code": log.event_type,
            "timestamp_utc": log.timestamp_utc.isoformat(),
            "received_at": log.received_at.isoformat(),
        } for log in logs]
        return Response(data)


class ConfigUploadListAPI(APIView):
    """GET /manage/api/config-uploads/"""

    def get(self, request):
        limit = int(request.query_params.get("limit", 50))
        client_id = request.query_params.get("client_id")
        qs = ConfigUploadRecord.objects.select_related("client").order_by("-received_at")
        if client_id:
            qs = qs.filter(client_id=client_id)
        records = qs[:limit]
        data = [{
            "id": r.id,
            "client_uid": str(r.client.client_uid),
            "config_type": r.get_config_type_display(),
            "request_guid": r.request_guid,
            "payload_json": r.payload_json,
            "received_at": r.received_at.isoformat(),
        } for r in records]
        return Response(data)
