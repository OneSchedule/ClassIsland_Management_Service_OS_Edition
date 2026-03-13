"""
在线客户端连接管理 —— 跟踪活跃的 gRPC 双向流连接。
"""
import logging
import queue
import threading
import uuid

logger = logging.getLogger(__name__)


def _normalize_uid(client_uid: str) -> str:
    try:
        return str(uuid.UUID(str(client_uid)))
    except Exception:
        return str(client_uid).strip().lower()


class ConnectionManager:
    """
    管理所有在线客户端的命令流连接。
    线程安全：gRPC 服务在独立线程池中运行。
    """

    def __init__(self):
        self._lock = threading.Lock()
        # client_uid -> queue.Queue for pending server->client messages
        self._queues: dict[str, queue.Queue] = {}

    def register(self, client_uid: str) -> queue.Queue:
        normalized_uid = _normalize_uid(client_uid)
        with self._lock:
            q = queue.Queue()
            self._queues[normalized_uid] = q
            logger.info("Client %s connected to command stream", normalized_uid)
            return q

    def unregister(self, client_uid: str):
        normalized_uid = _normalize_uid(client_uid)
        with self._lock:
            self._queues.pop(normalized_uid, None)
            logger.info("Client %s disconnected from command stream", normalized_uid)

    def is_connected(self, client_uid: str) -> bool:
        normalized_uid = _normalize_uid(client_uid)
        with self._lock:
            return normalized_uid in self._queues

    def get_connected_uids(self) -> list[str]:
        with self._lock:
            return list(self._queues.keys())

    def enqueue_command(self, client_uid: str, message) -> bool:
        """将命令放入客户端的队列，返回是否成功"""
        normalized_uid = _normalize_uid(client_uid)
        with self._lock:
            q = self._queues.get(normalized_uid)
            if q is None:
                return False
            q.put_nowait(message)
            return True


# 全局单例
connection_manager = ConnectionManager()
