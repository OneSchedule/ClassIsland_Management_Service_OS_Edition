# ClassIsland gRPC Contract Summary（逆向整理）

> 来源：`ClassIsland.Shared/Protobuf/**/*.proto` + 客户端调用实现。
> 日期：2026-03-12

## 1) 通用约定

## 1.1 Metadata

客户端会附带以下 metadata（键名均为小写）：

- `cuid`: 客户端 GUID
- `protocol_name`: 固定 `Cyrene_MSP`
- `protocol_version`: 固定 `2.0.0.0`
- `session`: 会话 ID（握手前为空字符串，握手后为服务端返回）

实现：`ClassIsland/Services/Management/ManagementServerConnection.cs`

## 1.2 Retcode（`Enum.Retcode`）

- `Unspecified = 0`
- `Success = 200`
- `ServerInternalError = 500`
- `InvalidRequest = 404`
- `HandshakeClientRejected = 1001`
- `Registered = 10001`
- `ClientNotFound = 10002`

---

## 2) Service: `ClientRegister`

Proto: `Protobuf/Service/ClientRegister.proto`

## 2.1 RPC: `Register`

`Register(ClientRegisterCsReq) returns (ClientRegisterScRsp)`

### Request `ClientRegisterCsReq`

- `ClientUid` (string) 客户端 GUID
- `ClientId` (string) 班级标识
- `ClientMac` (string) 设备 MAC

### Response `ClientRegisterScRsp`

- `Retcode` (`Enum.Retcode`)
- `Message` (string)
- `ServerPublicKey` (string, ASCII armored PGP 公钥)

### 客户端行为

- 接受 `Retcode=Success` 或 `Retcode=Registered`
- 其他返回码直接失败
- 成功后会将 `ServerPublicKey` 保存到本地并继续获取 manifest

## 2.2 RPC: `UnRegister`

Proto 已定义；当前主程序流程未见使用。

---

## 3) Service: `Handshake`

Proto: `Protobuf/Service/Handshake.proto`

## 3.1 RPC: `BeginHandshake`

`BeginHandshake(HandshakeScBeginHandShakeReq) returns (HandshakeScBeginHandShakeRsp)`

### Request `HandshakeScBeginHandShakeReq`

- `ClientUid` (string)
- `ClientMac` (string)
- `ChallengeTokenEncrypted` (string)
- `RequestedServerKeyId` (int64)

### Response `HandshakeScBeginHandShakeRsp`

- `Retcode` (`Enum.Retcode`)
- `Message` (string)
- `ChallengeTokenDecrypted` (string)
- `ServerPublicKey` (string)

### 客户端校验

客户端会本地生成随机 challenge，并用服务器公钥加密后发送；
若返回的 `ChallengeTokenDecrypted` 与本地原文不一致，则视为不信任。

## 3.2 RPC: `CompleteHandshake`

`CompleteHandshake(HandshakeScCompleteHandshakeReq) returns (HandshakeScCompleteHandshakeRsp)`

### Request `HandshakeScCompleteHandshakeReq`

- `Accepted` (bool)

### Response `HandshakeScCompleteHandshakeRsp`

- `Retcode` (`Enum.Retcode`)
- `Message` (string)
- `SessionId` (string)

### 客户端行为

- 若 `Accepted=true` 且流程成功，则保存 `SessionId`
- 后续 gRPC 调用 metadata 会携带该 session

---

## 4) Service: `ClientCommandDeliver`（双向流）

Proto: `Protobuf/Service/ClientCommandDeliver.proto`

RPC:

`ListenCommand(stream ClientCommandDeliverScReq) returns (stream ClientCommandDeliverScRsp)`

## 4.1 Client -> Server: `ClientCommandDeliverScReq`

- `Type` (`Enum.CommandTypes`)
- `Payload` (bytes)

客户端当前主要用于发送心跳：

- 每 10 秒发送 `Type=Ping`。

## 4.2 Server -> Client: `ClientCommandDeliverScRsp`

- `RetCode` (`Enum.Retcode`)
- `Type` (`Enum.CommandTypes`)
- `Payload` (bytes)

客户端仅处理 `RetCode=Success` 的消息。

## 4.3 `CommandTypes`

- `Ping = 10`
- `Pong = 11`
- `RestartApp = 101`
- `SendNotification = 102`
- `DataUpdated = 103`
- `GetClientConfig = 104`

## 4.4 已实现命令消费

1. `RestartApp`
   - 客户端立即重启。
2. `DataUpdated`
   - 触发重载集控配置（manifest/policy/credential 与后续业务数据）。
3. `GetClientConfig`
   - `Payload` 解析为 `Command.GetClientConfig`。
   - 然后通过 `ConfigUpload.UploadConfig` 回传数据。
4. `SendNotification`
   - 对应 `Command.SendNotification`。
   - 当前实现在 `#if false` 代码块，默认可能不启用。

### `Command.GetClientConfig`

- `RequestGuid` (string)
- `ConfigType` (`Enum.ConfigTypes`)

### `Enum.ConfigTypes`

- `UnspecifiedConfig = 0`
- `AppSettings = 1`
- `Profile = 2`
- `CurrentComponent = 3`
- `CurrentAutomation = 4`
- `Logs = 5`
- `PluginList = 6`

### `Command.SendNotification`

- `MessageMask` (string)
- `MessageContent` (string)
- `OverlayIconLeft` (int32)
- `OverlayIconRight` (int32)
- `IsEmergency` (bool)
- `IsSpeechEnabled` (bool)
- `IsEffectEnabled` (bool)
- `IsSoundEnabled` (bool)
- `IsTopmost` (bool)
- `DurationSeconds` (double)
- `RepeatCounts` (int32)

---

## 5) Service: `ConfigUpload`

Proto: `Protobuf/Service/ConfigUpload.proto`

RPC:

`UploadConfig(ConfigUploadScReq) returns (ConfigUploadScRsp)`

## 5.1 Request `ConfigUploadScReq`

- `RequestGuidId` (string)
- `Payload` (string, JSON)

## 5.2 Response `ConfigUploadScRsp`

- `Retcode` (`Enum.Retcode`)
- `Message` (string)

## 5.3 客户端上传映射

收到 `GetClientConfig` 后：

- `AppSettings` -> `Settings` JSON
- `Profile` -> `Profile` JSON
- `CurrentComponent` -> 当前组件列表 JSON
- `CurrentAutomation` -> 当前工作流 JSON
- `Logs` -> 日志 JSON
- `PluginList` -> 已加载插件 ID 列表 JSON

---

## 6) Service: `Audit`

Proto: `Protobuf/Service/Audit.proto`

RPC:

`LogEvent(AuditScReq) returns (AuditScRsp)`

## 6.1 Request `AuditScReq`

- `Event` (`Enum.AuditEvents`)
- `Payload` (bytes)
- `TimestampUtc` (int64, Unix 秒)

## 6.2 Response `AuditScRsp`

- `Retcode` (`Enum.Retcode`)
- `Message` (string)

## 6.3 `AuditEvents`

- `AuthorizeSuccess = 1`
- `AuthorizeFailed = 2`
- `AppSettingsUpdated = 4`
- `ClassChangeCompleted = 5`
- `ClassPlanUpdated = 6`
- `TimeLayoutUpdated = 7`
- `SubjectUpdated = 8`
- `AppCrashed = 9`
- `AppStarted = 10`
- `AppExited = 11`
- `PluginInstalled = 12`
- `PluginUninstalled = 13`

## 6.4 常见 Payload 类型

- `AuthorizeSuccess/Failed` -> `AuditEvent.AuthorizeEvent`
- `AppSettingsUpdated` -> `AuditEvent.AppSettingsUpdated`
- `ClassChangeCompleted` -> `AuditEvent.ClassChangeCompleted`
- `ClassPlanUpdated/TimeLayoutUpdated/SubjectUpdated` -> `AuditEvent.ProfileItemUpdated`
- `AppCrashed` -> `AuditEvent.AppCrashed`
- `AppStarted/AppExited` -> `google.protobuf.Empty`
- `PluginInstalled` -> `AuditEvent.PluginInstalled`
- `PluginUninstalled` -> `AuditEvent.PluginUninstalled`

---

## 7) 服务端落地建议

1. 先完成 `Register + Handshake + ListenCommand(心跳)` 的最小闭环。
2. `Audit`、`ConfigUpload` 建议尽早实现并入库存证。
3. `Retcode` 尽量按枚举值返回，避免客户端误判。
4. `session` 建议服务端强校验，以区分握手前后与设备身份。
