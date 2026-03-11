"""
在线客户端连接管理 —— 跟踪活跃的 gRPC 双向流连接。
"""
import asyncio
import logging
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    管理所有在线客户端的命令流连接。
    线程安全：gRPC 服务在独立线程池中运行。
    """

    def __init__(self):
        self._lock = threading.Lock()
        # client_uid -> asyncio.Queue for pending server->client messages
        self._queues: dict[str, asyncio.Queue] = {}

    def register(self, client_uid: str) -> asyncio.Queue:
        with self._lock:
            q = asyncio.Queue()
            self._queues[client_uid] = q
            logger.info("Client %s connected to command stream", client_uid)
            return q

    def unregister(self, client_uid: str):
        with self._lock:
            self._queues.pop(client_uid, None)
            logger.info("Client %s disconnected from command stream", client_uid)

    def is_connected(self, client_uid: str) -> bool:
        with self._lock:
            return client_uid in self._queues

    def get_connected_uids(self) -> list[str]:
        with self._lock:
            return list(self._queues.keys())

    def enqueue_command(self, client_uid: str, message) -> bool:
        """将命令放入客户端的队列，返回是否成功"""
        with self._lock:
            q = self._queues.get(client_uid)
            if q is None:
                return False
            q.put_nowait(message)
            return True


# 全局单例
connection_manager = ConnectionManager()
