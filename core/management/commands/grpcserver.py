"""
gRPC 服务器启动器 —— 作为 Django management command 运行。
"""
import logging
from concurrent import futures

import grpc
from django.core.management.base import BaseCommand
from django.conf import settings

from core.grpc_services import (
    ClientRegisterService,
    HandshakeService,
    ClientCommandDeliverService,
    AuditService,
    ConfigUploadService,
)
from core.proto_gen.Protobuf.Service import (
    ClientRegister_pb2_grpc,
    Handshake_pb2_grpc,
    ClientCommandDeliver_pb2_grpc,
    Audit_pb2_grpc,
    ConfigUpload_pb2_grpc,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "启动 ClassIsland 集控 gRPC 服务器"

    def add_arguments(self, parser):
        parser.add_argument(
            "--port", type=int,
            default=settings.GRPC_SERVER_PORT,
            help="gRPC 监听端口 (默认 20722)",
        )
        parser.add_argument(
            "--max-workers", type=int, default=10,
            help="最大工作线程数",
        )

    def handle(self, *args, **options):
        port = options["port"]
        max_workers = options["max_workers"]

        server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))

        # 注册服务
        ClientRegister_pb2_grpc.add_ClientRegisterServicer_to_server(
            ClientRegisterService(), server
        )
        Handshake_pb2_grpc.add_HandshakeServicer_to_server(
            HandshakeService(), server
        )
        ClientCommandDeliver_pb2_grpc.add_ClientCommandDeliverServicer_to_server(
            ClientCommandDeliverService(), server
        )
        Audit_pb2_grpc.add_AuditServicer_to_server(
            AuditService(), server
        )
        ConfigUpload_pb2_grpc.add_ConfigUploadServicer_to_server(
            ConfigUploadService(), server
        )

        listen_addr = f"[::]:{port}"
        server.add_insecure_port(listen_addr)
        server.start()

        self.stdout.write(self.style.SUCCESS(
            f"gRPC 服务器已启动，监听 {listen_addr}"
        ))

        try:
            server.wait_for_termination()
        except KeyboardInterrupt:
            self.stdout.write("正在关闭 gRPC 服务器...")
            server.stop(grace=5)
