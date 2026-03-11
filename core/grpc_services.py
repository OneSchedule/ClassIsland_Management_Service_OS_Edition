"""
gRPC 服务实现 —— 对应 ClassIsland 集控协议五大 Service。
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

import grpc

from core.proto_gen.Protobuf.Enum import Retcode_pb2, CommandTypes_pb2
from core.proto_gen.Protobuf.Client import (
    ClientRegisterCsReq_pb2,
    HandshakeScReq_pb2,
    ClientCommandDeliverScReq_pb2,
    AuditScReq_pb2,
    ConfigUploadScReq_pb2,
)
from core.proto_gen.Protobuf.Server import (
    ClientRegisterScRsp_pb2,
    HandshakeScRsp_pb2,
    ClientCommandDeliverScRsp_pb2,
    AuditScRsp_pb2,
    ConfigUploadScRsp_pb2,
)
from core.proto_gen.Protobuf.Service import (
    ClientRegister_pb2_grpc,
    Handshake_pb2_grpc,
    ClientCommandDeliver_pb2_grpc,
    Audit_pb2_grpc,
    ConfigUpload_pb2_grpc,
)
from core.connection_manager import connection_manager

logger = logging.getLogger(__name__)

PROTOCOL_NAME = "Cyrene_MSP"
PROTOCOL_VERSION = "2.0.0.0"


def _get_metadata(context) -> dict:
    """从 gRPC metadata 中提取客户端信息"""
    md = dict(context.invocation_metadata())
    return {
        "cuid": md.get("cuid", ""),
        "protocol_name": md.get("protocol_name", ""),
        "protocol_version": md.get("protocol_version", ""),
        "session": md.get("session", ""),
    }


def _get_client_or_none(cuid: str):
    """通过 UID 查找客户端（延迟导入避免循环）"""
    from core.models import Client
    try:
        return Client.objects.get(client_uid=cuid)
    except Client.DoesNotExist:
        return None


# ────────────────────────────────────────────────────
# 1. ClientRegister
# ────────────────────────────────────────────────────
class ClientRegisterService(ClientRegister_pb2_grpc.ClientRegisterServicer):

    def Register(self, request, context):
        from core.models import Client, ClassGroup, ClientStatusChoices
        from core.crypto import get_active_keypair
        from core.models import Organization

        cuid = request.ClientUid
        client_id = request.ClientId
        client_mac = request.ClientMac

        logger.info("ClientRegister.Register: uid=%s id=%s mac=%s", cuid, client_id, client_mac)

        org = Organization.objects.first()
        if org is None:
            return ClientRegisterScRsp_pb2.ClientRegisterScRsp(
                Retcode=Retcode_pb2.ServerInternalError,
                Message="服务器未初始化组织",
            )

        keypair = get_active_keypair(org)
        if keypair is None:
            return ClientRegisterScRsp_pb2.ClientRegisterScRsp(
                Retcode=Retcode_pb2.ServerInternalError,
                Message="服务器未生成密钥对",
            )

        # 查找或创建客户端
        client, created = Client.objects.get_or_create(
            client_uid=cuid,
            defaults={
                "client_id": client_id,
                "client_mac": client_mac,
                "status": ClientStatusChoices.APPROVED,
            }
        )
        if not created:
            client.client_id = client_id
            client.client_mac = client_mac
            client.save(update_fields=["client_id", "client_mac", "updated_at"])

        # 尝试将客户端分配到班级组
        if client_id and not client.class_group:
            try:
                group = ClassGroup.objects.get(class_identity=client_id)
                client.class_group = group
                client.save(update_fields=["class_group"])
            except ClassGroup.DoesNotExist:
                pass

        retcode = Retcode_pb2.Success if created else Retcode_pb2.Registered
        return ClientRegisterScRsp_pb2.ClientRegisterScRsp(
            Retcode=retcode,
            Message="OK",
            ServerPublicKey=keypair.public_key_armored,
        )

    def UnRegister(self, request, context):
        cuid = request.ClientUid
        client = _get_client_or_none(cuid)
        if client is None:
            return ClientRegisterScRsp_pb2.ClientRegisterScRsp(
                Retcode=Retcode_pb2.ClientNotFound,
                Message="客户端未注册",
            )
        client.delete()
        return ClientRegisterScRsp_pb2.ClientRegisterScRsp(
            Retcode=Retcode_pb2.Success,
            Message="已注销",
        )


# ────────────────────────────────────────────────────
# 2. Handshake
# ────────────────────────────────────────────────────
class HandshakeService(Handshake_pb2_grpc.HandshakeServicer):

    def BeginHandshake(self, request, context):
        from core.models import Organization
        from core.crypto import get_active_keypair, decrypt_with_private_key

        md = _get_metadata(context)
        cuid = md["cuid"]
        client = _get_client_or_none(cuid)
        if client is None:
            return HandshakeScRsp_pb2.HandshakeScBeginHandShakeRsp(
                Retcode=Retcode_pb2.ClientNotFound,
                Message="客户端未注册，请先注册",
            )

        org = Organization.objects.first()
        keypair = get_active_keypair(org)
        if keypair is None:
            return HandshakeScRsp_pb2.HandshakeScBeginHandShakeRsp(
                Retcode=Retcode_pb2.ServerInternalError,
                Message="服务器密钥未生成",
            )

        # 解密挑战令牌
        try:
            decrypted_token = decrypt_with_private_key(
                keypair.private_key_armored,
                request.ChallengeTokenEncrypted,
            )
        except Exception as e:
            logger.error("解密挑战令牌失败: %s", e)
            return HandshakeScRsp_pb2.HandshakeScBeginHandShakeRsp(
                Retcode=Retcode_pb2.ServerInternalError,
                Message=f"解密失败: {e}",
            )

        # 保存临时握手状态到 context（grpc-python 不支持跨 RPC 共享状态，
        # 这里将解密令牌放入客户端记录的 session 字段暂存）
        client.current_session_id = f"handshake:{decrypted_token}"
        client.save(update_fields=["current_session_id"])

        return HandshakeScRsp_pb2.HandshakeScBeginHandShakeRsp(
            Retcode=Retcode_pb2.Success,
            Message="OK",
            ChallengeTokenDecrypted=decrypted_token,
            ServerPublicKey=keypair.public_key_armored,
        )

    def CompleteHandshake(self, request, context):
        md = _get_metadata(context)
        cuid = md["cuid"]
        client = _get_client_or_none(cuid)
        if client is None:
            return HandshakeScRsp_pb2.HandshakeScCompleteHandshakeRsp(
                Retcode=Retcode_pb2.ClientNotFound,
                Message="客户端未注册",
            )

        if not request.Accepted:
            return HandshakeScRsp_pb2.HandshakeScCompleteHandshakeRsp(
                Retcode=Retcode_pb2.HandshakeClientRejected,
                Message="客户端拒绝了握手",
            )

        # 生成正式会话 ID
        session_id = str(uuid.uuid4())
        client.current_session_id = session_id
        client.is_online = True
        from django.utils import timezone as tz
        client.last_seen = tz.now()
        client.save(update_fields=["current_session_id", "is_online", "last_seen"])

        return HandshakeScRsp_pb2.HandshakeScCompleteHandshakeRsp(
            Retcode=Retcode_pb2.Success,
            Message="握手完成",
            SessionId=session_id,
        )


# ────────────────────────────────────────────────────
# 3. ClientCommandDeliver (双向流)
# ────────────────────────────────────────────────────
class ClientCommandDeliverService(ClientCommandDeliver_pb2_grpc.ClientCommandDeliverServicer):

    def ListenCommand(self, request_iterator, context):
        md = _get_metadata(context)
        cuid = md["cuid"]
        session = md["session"]

        client = _get_client_or_none(cuid)
        if client is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "客户端未注册")
            return

        # 注册连接
        queue = connection_manager.register(cuid)
        client.is_online = True
        from django.utils import timezone as tz
        client.last_seen = tz.now()
        client.save(update_fields=["is_online", "last_seen"])

        try:
            # 启动一个线程读取客户端发来的消息
            import threading

            def _read_requests():
                try:
                    for req in request_iterator:
                        if req.Type == CommandTypes_pb2.Ping:
                            # 回复 Pong
                            pong = ClientCommandDeliverScRsp_pb2.ClientCommandDeliverScRsp(
                                RetCode=Retcode_pb2.Success,
                                Type=CommandTypes_pb2.Pong,
                            )
                            queue.put_nowait(pong)
                            # 更新最后在线时间
                            from core.models import Client as C
                            C.objects.filter(client_uid=cuid).update(last_seen=tz.now())
                except Exception:
                    pass

            reader = threading.Thread(target=_read_requests, daemon=True)
            reader.start()

            # 发送待下发命令
            self._flush_pending_commands(cuid, queue)

            # 主循环：从队列中取消息发给客户端
            while not context.is_active() is False:
                try:
                    msg = queue.get(timeout=1.0)
                    yield msg
                except Exception:
                    if not context.is_active():
                        break
                    continue

        finally:
            connection_manager.unregister(cuid)
            from core.models import Client as C
            C.objects.filter(client_uid=cuid).update(is_online=False)

    def _flush_pending_commands(self, cuid: str, queue):
        """发送数据库中的待下发命令"""
        from core.models import PendingCommand, Client
        from django.utils import timezone as tz
        try:
            client = Client.objects.get(client_uid=cuid)
            pending = PendingCommand.objects.filter(
                client=client, delivered=False
            ).order_by("created_at")
            for cmd in pending:
                msg = ClientCommandDeliverScRsp_pb2.ClientCommandDeliverScRsp(
                    RetCode=Retcode_pb2.Success,
                    Type=cmd.command_type,
                    Payload=bytes(cmd.payload),
                )
                queue.put_nowait(msg)
                cmd.delivered = True
                cmd.delivered_at = tz.now()
                cmd.save(update_fields=["delivered", "delivered_at"])
        except Exception as e:
            logger.error("发送待下发命令失败: %s", e)


# ────────────────────────────────────────────────────
# 4. Audit
# ────────────────────────────────────────────────────
class AuditService(Audit_pb2_grpc.AuditServicer):

    def LogEvent(self, request, context):
        from core.models import AuditLog

        md = _get_metadata(context)
        cuid = md["cuid"]
        client = _get_client_or_none(cuid)
        if client is None:
            return AuditScRsp_pb2.AuditScRsp(
                Retcode=Retcode_pb2.ClientNotFound,
                Message="客户端未注册",
            )

        ts = datetime.fromtimestamp(request.TimestampUtc, tz=timezone.utc)
        AuditLog.objects.create(
            client=client,
            event_type=request.Event,
            payload=bytes(request.Payload),
            timestamp_utc=ts,
        )

        return AuditScRsp_pb2.AuditScRsp(
            Retcode=Retcode_pb2.Success,
            Message="OK",
        )


# ────────────────────────────────────────────────────
# 5. ConfigUpload
# ────────────────────────────────────────────────────
class ConfigUploadService(ConfigUpload_pb2_grpc.ConfigUploadServicer):

    def UploadConfig(self, request, context):
        from core.models import ConfigUploadRecord

        md = _get_metadata(context)
        cuid = md["cuid"]
        client = _get_client_or_none(cuid)
        if client is None:
            return ConfigUploadScRsp_pb2.ConfigUploadScRsp(
                Retcode=Retcode_pb2.ClientNotFound,
                Message="客户端未注册",
            )

        try:
            payload_dict = json.loads(request.Payload)
        except json.JSONDecodeError:
            payload_dict = {"raw": request.Payload}

        ConfigUploadRecord.objects.create(
            client=client,
            request_guid=request.RequestGuidId,
            payload_json=payload_dict,
        )

        return ConfigUploadScRsp_pb2.ConfigUploadScRsp(
            Retcode=Retcode_pb2.Success,
            Message="OK",
        )
