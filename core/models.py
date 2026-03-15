"""
ClassIsland 集控服务 数据模型
对应 ClassIsland.Shared 中的模型与枚举定义。
"""
import uuid

from django.db import models
from django.utils import timezone


# ────────────────────────────────────────────────────
# 组织（集控服务器实例）
# ────────────────────────────────────────────────────
class Organization(models.Model):
    """组织/学校 —— 一个集控服务器实例对应一个组织"""
    name = models.CharField("组织名称", max_length=200, default="ClassIsland 集控")
    core_version = models.CharField("核心版本", max_length=20, default="2.0.0.0")
    management_server = models.CharField(
        "HTTP 地址",
        max_length=255,
        default="http://127.0.0.1:20721",
    )
    management_server_grpc = models.CharField(
        "gRPC 地址",
        max_length=255,
        default="http://127.0.0.1:20722",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "组织"
        verbose_name_plural = "组织"

    def __str__(self):
        return self.name


# ────────────────────────────────────────────────────
# 班级组
# ────────────────────────────────────────────────────
class ClassGroup(models.Model):
    """
    班级组 —— 对应客户端的 ClassIdentity。
    一个班级组共享同一套课表、时间表、科目、设置、策略。
    """
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="class_groups"
    )
    name = models.CharField("班级名称", max_length=100)
    class_identity = models.CharField(
        "班级标识 (ClassIdentity)", max_length=100, unique=True, db_index=True
    )

    # ── 资源 JSON（直接存 DB，简单方案） ──
    class_plans_json = models.JSONField("课表 JSON", default=dict, blank=True)
    class_plans_version = models.IntegerField("课表版本", default=0)

    time_layouts_json = models.JSONField("时间表 JSON", default=dict, blank=True)
    time_layouts_version = models.IntegerField("时间表版本", default=0)

    subjects_json = models.JSONField("科目 JSON", default=dict, blank=True)
    subjects_version = models.IntegerField("科目版本", default=0)

    settings_json = models.JSONField("默认设置 JSON", default=dict, blank=True)
    settings_version = models.IntegerField("默认设置版本", default=0)

    policy_json = models.JSONField("策略 JSON", default=dict, blank=True)
    policy_version = models.IntegerField("策略版本", default=0)

    components_json = models.JSONField("组件 JSON", default=dict, blank=True)
    components_version = models.IntegerField("组件版本", default=0)

    credential_json = models.JSONField("凭据 JSON", default=dict, blank=True)
    credential_version = models.IntegerField("凭据版本", default=0)

    # ── 关联配置（从"编辑配置"中选择已创建的配置） ──
    linked_class_plan = models.ForeignKey(
        "ClassPlanConfig", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="class_groups",
        verbose_name="关联课表配置",
    )
    linked_subjects = models.ForeignKey(
        "SubjectConfig", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="class_groups",
        verbose_name="关联科目配置",
    )
    linked_default_settings = models.ForeignKey(
        "DefaultSettingsConfig", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="class_groups",
        verbose_name="关联默认设置",
    )
    linked_policy = models.ForeignKey(
        "PolicyConfig", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="class_groups",
        verbose_name="关联策略",
    )
    linked_credential = models.ForeignKey(
        "CredentialConfig", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="class_groups",
        verbose_name="关联凭据",
    )
    linked_component = models.ForeignKey(
        "ComponentConfig", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="class_groups",
        verbose_name="关联组件",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "班级组"
        verbose_name_plural = "班级组"

    def __str__(self):
        return f"{self.name} ({self.class_identity})"


# ────────────────────────────────────────────────────
# 客户端实例
# ────────────────────────────────────────────────────
class ClientStatusChoices(models.IntegerChoices):
    PENDING = 0, "待审批"
    APPROVED = 1, "已批准"
    BLOCKED = 2, "已封禁"


class Client(models.Model):
    """
    客户端实例 —— 对应 ManagementClientPersistConfig。
    每台运行 ClassIsland 的机器注册后产生一条记录。
    """
    client_uid = models.UUIDField(
        "客户端 UID", unique=True, db_index=True, default=uuid.uuid4
    )
    class_group = models.ForeignKey(
        ClassGroup, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="clients",
        verbose_name="所属班级组"
    )
    client_id = models.CharField(
        "客户端班级标识", max_length=100, blank=True, default=""
    )
    client_mac = models.CharField("MAC 地址", max_length=20, blank=True, default="")
    hostname = models.CharField("主机名", max_length=200, blank=True, default="")

    status = models.IntegerField(
        "状态", choices=ClientStatusChoices.choices, default=ClientStatusChoices.APPROVED
    )

    # 会话
    current_session_id = models.CharField(
        "当前会话 ID", max_length=100, blank=True, default=""
    )
    last_seen = models.DateTimeField("最后在线", null=True, blank=True)
    is_online = models.BooleanField("是否在线", default=False)

    registered_at = models.DateTimeField("注册时间", auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "客户端"
        verbose_name_plural = "客户端"

    def __str__(self):
        return f"{self.client_uid} ({self.client_id or '未分配'})"


# ────────────────────────────────────────────────────
# PGP 密钥对
# ────────────────────────────────────────────────────
class ServerKeyPair(models.Model):
    """PGP 密钥对，用于握手认证"""
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="keypairs"
    )
    key_id = models.BigIntegerField("PGP Key ID", db_index=True)
    public_key_armored = models.TextField("公钥 (ASCII Armored)")
    private_key_armored = models.TextField("私钥 (ASCII Armored)")
    is_active = models.BooleanField("当前使用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "服务器密钥"
        verbose_name_plural = "服务器密钥"

    def __str__(self):
        return f"Key {self.key_id} ({'活跃' if self.is_active else '已停用'})"


# ────────────────────────────────────────────────────
# 审计日志
# ────────────────────────────────────────────────────
class AuditEventType(models.IntegerChoices):
    DEFAULT = 0, "默认事件"
    AUTHORIZE_SUCCESS = 1, "授权成功"
    AUTHORIZE_FAILED = 2, "授权失败"
    APP_SETTINGS_UPDATED = 4, "应用设置更新"
    CLASS_CHANGE_COMPLETED = 5, "换课完成"
    CLASS_PLAN_UPDATED = 6, "课表更新"
    TIME_LAYOUT_UPDATED = 7, "时间表更新"
    SUBJECT_UPDATED = 8, "科目更新"
    APP_CRASHED = 9, "应用崩溃"
    APP_STARTED = 10, "应用启动"
    APP_EXITED = 11, "应用退出"
    PLUGIN_INSTALLED = 12, "插件安装"
    PLUGIN_UNINSTALLED = 13, "插件卸载"


class AuditLog(models.Model):
    """审计日志 —— 对应 Audit.LogEvent"""
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="audit_logs"
    )
    event_type = models.IntegerField(
        "事件类型", choices=AuditEventType.choices, default=AuditEventType.DEFAULT
    )
    payload = models.BinaryField("载荷 (protobuf bytes)", blank=True, default=b"")
    timestamp_utc = models.DateTimeField("事件时间 (UTC)")
    received_at = models.DateTimeField("接收时间", auto_now_add=True)

    class Meta:
        verbose_name = "审计日志"
        verbose_name_plural = "审计日志"
        ordering = ["-timestamp_utc"]

    def __str__(self):
        return f"[{self.get_event_type_display()}] {self.client.client_uid} @ {self.timestamp_utc}"


# ────────────────────────────────────────────────────
# 待下发命令队列
# ────────────────────────────────────────────────────
class CommandType(models.IntegerChoices):
    PING = 10, "Ping"
    PONG = 11, "Pong"
    RESTART_APP = 101, "重启应用"
    SEND_NOTIFICATION = 102, "发送通知"
    DATA_UPDATED = 103, "数据更新"
    GET_CLIENT_CONFIG = 104, "获取客户端配置"


class PendingCommand(models.Model):
    """
    待下发的命令 —— 管理面板创建后，gRPC 命令流会推送给在线客户端。
    """
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="pending_commands"
    )
    command_type = models.IntegerField(
        "命令类型", choices=CommandType.choices
    )
    payload = models.BinaryField("载荷 (protobuf bytes)", blank=True, default=b"")
    created_at = models.DateTimeField(auto_now_add=True)
    delivered = models.BooleanField("已送达", default=False)
    delivered_at = models.DateTimeField("送达时间", null=True, blank=True)

    class Meta:
        verbose_name = "待下发命令"
        verbose_name_plural = "待下发命令"
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.get_command_type_display()}] -> {self.client.client_uid}"


# ────────────────────────────────────────────────────
# 配置回传记录
# ────────────────────────────────────────────────────
class ConfigType(models.IntegerChoices):
    UNSPECIFIED = 0, "未指定"
    APP_SETTINGS = 1, "应用设置"
    PROFILE = 2, "档案"
    CURRENT_COMPONENT = 3, "当前组件"
    CURRENT_AUTOMATION = 4, "工作流"
    LOGS = 5, "日志"
    PLUGIN_LIST = 6, "插件列表"


class ConfigUploadRecord(models.Model):
    """客户端配置回传记录"""
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="config_uploads"
    )
    request_guid = models.CharField("请求 GUID", max_length=100)
    config_type = models.IntegerField(
        "配置类型", choices=ConfigType.choices, default=ConfigType.UNSPECIFIED
    )
    payload_json = models.JSONField("配置 JSON", default=dict)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "配置回传"
        verbose_name_plural = "配置回传"
        ordering = ["-received_at"]

    def __str__(self):
        return f"[{self.get_config_type_display()}] {self.client.client_uid}"


# ────────────────────────────────────────────────────
# 配置管理：可复用的配置项
# ────────────────────────────────────────────────────
class TimeLayoutConfig(models.Model):
    """时间表配置"""
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="time_layouts"
    )
    name = models.CharField("名称", max_length=200)
    identifier = models.CharField("标识", max_length=200, unique=True, db_index=True)
    data_json = models.JSONField("时间表 JSON", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "时间表配置"
        verbose_name_plural = "时间表配置"

    def __str__(self):
        return f"{self.name} ({self.identifier})"


class SubjectConfig(models.Model):
    """科目配置"""
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="subjects"
    )
    name = models.CharField("名称", max_length=200)
    identifier = models.CharField("标识", max_length=200, unique=True, db_index=True)
    data_json = models.JSONField("科目 JSON", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "科目配置"
        verbose_name_plural = "科目配置"

    def __str__(self):
        return f"{self.name} ({self.identifier})"


class ClassPlanConfig(models.Model):
    """课表配置 —— 必须依赖一个时间表"""
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="class_plans"
    )
    name = models.CharField("名称", max_length=200)
    identifier = models.CharField("标识", max_length=200, unique=True, db_index=True)
    time_layout = models.ForeignKey(
        TimeLayoutConfig, on_delete=models.PROTECT,
        related_name="class_plans",
        verbose_name="依赖时间表",
    )
    data_json = models.JSONField("课表 JSON", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "课表配置"
        verbose_name_plural = "课表配置"

    def __str__(self):
        return f"{self.name} ({self.identifier})"


class DefaultSettingsConfig(models.Model):
    """默认设置配置"""
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="default_settings"
    )
    name = models.CharField("名称", max_length=200)
    identifier = models.CharField("标识", max_length=200, unique=True, db_index=True)
    data_json = models.JSONField("设置 JSON", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "默认设置配置"
        verbose_name_plural = "默认设置配置"

    def __str__(self):
        return f"{self.name} ({self.identifier})"


class PolicyConfig(models.Model):
    """策略配置"""
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="policies"
    )
    name = models.CharField("名称", max_length=200)
    identifier = models.CharField("标识", max_length=200, unique=True, db_index=True)
    data_json = models.JSONField("策略 JSON", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "策略配置"
        verbose_name_plural = "策略配置"

    def __str__(self):
        return f"{self.name} ({self.identifier})"


class CredentialConfig(models.Model):
    """凭据配置"""
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="credentials"
    )
    name = models.CharField("名称", max_length=200)
    identifier = models.CharField("标识", max_length=200, unique=True, db_index=True)
    data_json = models.JSONField("凭据 JSON", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "凭据配置"
        verbose_name_plural = "凭据配置"

    def __str__(self):
        return f"{self.name} ({self.identifier})"


class ComponentConfig(models.Model):
    """组件配置"""
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="components"
    )
    name = models.CharField("名称", max_length=200)
    identifier = models.CharField("标识", max_length=200, unique=True, db_index=True)
    data_json = models.JSONField("组件 JSON", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "组件配置"
        verbose_name_plural = "组件配置"

    def __str__(self):
        return f"{self.name} ({self.identifier})"
