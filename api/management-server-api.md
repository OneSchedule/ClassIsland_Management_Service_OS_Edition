# ClassIsland 集控服务器 API（从主程序逆向）

> 基于 `ClassIsland` 主程序当前代码（2026-03-12）反推。
> 这是**实现侧文档**，用于服务端对接；不是官方协议承诺，后续版本可能变更。

## 1. 总览

ClassIsland 集控有两种模式：

1. **Serverless**（静态 JSON）
   - 客户端只拉取 HTTP JSON（清单 + 各资源）。
   - 不需要 gRPC。
2. **ManagementServer**（完整集控服务器）
   - HTTP：拉取清单与资源 JSON。
   - gRPC：注册、握手、命令流、审计日志、配置回传。

---

## 2. 客户端标识与 URL 模板

客户端在请求资源 URL 时会替换模板变量：

- `{cuid}`：客户端唯一 ID（GUID）
- `{id}`：班级标识（`ClassIdentity`，可空字符串）
- `{host}`：集控服务器 HTTP 根地址（仅 `ManagementServerConnection` 支持）

代码位置：`ClassIsland/Services/Management/ServerlessConnection.cs`、`ClassIsland/Services/Management/ManagementServerConnection.cs`

---

## 3. HTTP API（ManagementServer 模式）

## 3.1 获取清单（固定路径）

- **Method**: `GET`
- **Path**: `/api/v1/client/{cuid}/manifest`
- **由客户端拼接**：`{ManagementServer}/api/v1/client/{clientUid}/manifest`

返回 JSON 结构对应 `ManagementManifest`：

```json
{
  "classPlanSource": { "value": "...", "version": 1 },
  "timeLayoutSource": { "value": "...", "version": 1 },
  "subjectsSource": { "value": "...", "version": 1 },
  "defaultSettingsSource": { "value": "...", "version": 1 },
  "policySource": { "value": "...", "version": 1 },
  "componentsSource": { "value": "...", "version": 1 },
  "credentialSource": { "value": "...", "version": 1 },
  "serverKind": 1,
  "organizationName": "组织名",
  "coreVersion": "2.0.0.0"
}
```

字段定义见：`ClassIsland.Shared/Models/Management/ManagementManifest.cs`

> `coreVersion` 主版本必须与客户端核心版本主版本一致，否则客户端拒绝继续。

## 3.2 清单内资源 URL

`*.Source.value` 由服务端提供，客户端会做模板替换后直接 `GET` JSON。

典型资源类型：

- `classPlanSource` → `Profile`（只用到课表相关字段）
- `timeLayoutSource` → `Profile`（只用到时间线字段）
- `subjectsSource` → `Profile`（只用到科目字段）
- `defaultSettingsSource` → `Settings`
- `policySource` → `ManagementPolicy`
- `credentialSource` → `ManagementCredentialConfig`
- `componentsSource`：当前客户端代码里版本字段已定义，但主流程未看到明确消费

版本控制规则：仅当 `source.version > localVersion` 且 `value` 非空时才下载。

---

## 4. gRPC API（ManagementServer 模式）

Proto 文件根目录：`ClassIsland.Shared/Protobuf/`

服务：

- `ClientRegister`
- `Handshake`
- `ClientCommandDeliver`（双向流）
- `Audit`
- `ConfigUpload`

## 4.1 通用 Metadata

客户端会在 gRPC 请求中带 metadata：

- `cuid`: 客户端 GUID
- `protocol_name`: `Cyrene_MSP`
- `protocol_version`: `2.0.0.0`
- `session`: 会话 ID（握手后；会话外请求为空）

实现见：`GetMetadata()` in `ManagementServerConnection.cs`

## 4.2 ClientRegister

### Register

- **RPC**: `ClientRegister.Register(ClientRegisterCsReq) -> ClientRegisterScRsp`
- 客户端请求：
  - `ClientUid` (string GUID)
  - `ClientId` (班级标识)
  - `ClientMac` (网卡 MAC)
- 服务端响应：
  - `Retcode`
  - `Message`
  - `ServerPublicKey` (ASCII armored PGP 公钥)

客户端接受 `Retcode = Success(200)` 或 `Registered(10001)`，否则视为失败。

### UnRegister

Proto 有定义，但当前主程序路径中未见实际调用。

## 4.3 Handshake

### BeginHandshake

- **RPC**: `Handshake.BeginHandshake(HandshakeScBeginHandShakeReq) -> HandshakeScBeginHandShakeRsp`
- 客户端请求：
  - `ClientUid`
  - `ClientMac`
  - `ChallengeTokenEncrypted`（随机串经服务端公钥加密）
  - `RequestedServerKeyId`
- 服务端响应：
  - `Retcode`
  - `Message`
  - `ChallengeTokenDecrypted`（应能还原随机串）
  - `ServerPublicKey`

### CompleteHandshake

- **RPC**: `Handshake.CompleteHandshake(HandshakeScCompleteHandshakeReq) -> HandshakeScCompleteHandshakeRsp`
- 客户端请求：`Accepted`（是否信任）
- 服务端响应：
  - `Retcode`
  - `Message`
  - `SessionId`

成功后客户端保存 `SessionId`，后续带入 metadata 的 `session`。

## 4.4 ClientCommandDeliver（命令流）

- **RPC**: `ClientCommandDeliver.ListenCommand(stream ClientCommandDeliverScReq) returns (stream ClientCommandDeliverScRsp)`

心跳：

- 客户端每 10 秒发 `Ping`。
- 服务端应回 `Pong`（或至少不报错并维持流）。

服务端下发命令：`ClientCommandDeliverScRsp`

- `RetCode` 需为 `Success`
- `Type` 为 `CommandTypes`
- `Payload` 为对应 proto 二进制

当前主程序实际消费命令：

1. `RestartApp`（无 payload 约束）
2. `DataUpdated`（无 payload 约束）
3. `GetClientConfig`（payload = `Command.GetClientConfig`）
4. `SendNotification`（payload = `Command.SendNotification`）
   - 代码目前在 `#if false` 块中（可能未启用）

`GetClientConfig` 请求结构：

- `RequestGuid` (string)
- `ConfigType` (enum)

收到后客户端调用 `ConfigUpload.UploadConfig` 回传。

## 4.5 ConfigUpload

- **RPC**: `ConfigUpload.UploadConfig(ConfigUploadScReq) -> ConfigUploadScRsp`

客户端上传：

- `RequestGuidId`：回显 `GetClientConfig.RequestGuid`
- `Payload`：JSON 字符串

`ConfigType -> Payload` 对照：

- `AppSettings` -> `Settings` JSON
- `Profile` -> `Profile` JSON
- `CurrentComponent` -> 当前组件列表 JSON
- `CurrentAutomation` -> 工作流列表 JSON
- `Logs` -> 日志列表 JSON
- `PluginList` -> 已加载插件 ID 列表 JSON

## 4.6 Audit

- **RPC**: `Audit.LogEvent(AuditScReq) -> AuditScRsp`

客户端上传：

- `Event`：`AuditEvents`
- `Payload`：对应事件 proto 二进制
- `TimestampUtc`：Unix 秒级时间戳

常见事件：

- `AuthorizeSuccess` / `AuthorizeFailed` (`AuthorizeEvent`)
- `AppSettingsUpdated` (`AppSettingsUpdated`)
- `ClassChangeCompleted` (`ClassChangeCompleted`)
- `ClassPlanUpdated` / `TimeLayoutUpdated` / `SubjectUpdated` (`ProfileItemUpdated`)
- `AppCrashed` (`AppCrashed`)
- `AppStarted` / `AppExited`（`google.protobuf.Empty`）
- `PluginInstalled` / `PluginUninstalled`

---

## 5. 枚举（关键）

## 5.1 `Retcode`

- `Success = 200`
- `ServerInternalError = 500`
- `InvalidRequest = 404`
- `HandshakeClientRejected = 1001`
- `Registered = 10001`
- `ClientNotFound = 10002`

## 5.2 `CommandTypes`

- `Ping = 10`
- `Pong = 11`
- `RestartApp = 101`
- `SendNotification = 102`
- `DataUpdated = 103`
- `GetClientConfig = 104`

## 5.3 `ConfigTypes`

- `AppSettings = 1`
- `Profile = 2`
- `CurrentComponent = 3`
- `CurrentAutomation = 4`
- `Logs = 5`
- `PluginList = 6`

---

## 6. 最小可用服务端实现建议

若要先跑通主程序，最小集合：

1. HTTP `GET /api/v1/client/{cuid}/manifest`。
2. 能返回上述资源 JSON（至少 policy/credential/profile/settings 对应链接可访问）。
3. gRPC `ClientRegister.Register`。
4. gRPC `Handshake.BeginHandshake/CompleteHandshake`。
5. gRPC `ClientCommandDeliver.ListenCommand`（至少支持心跳，不下发命令也可）。
6. 可选：`Audit.LogEvent`、`ConfigUpload.UploadConfig`（建议实现并记录）。

---

## 7. 代码依据（主要）

- `ClassIsland/Services/Management/ManagementServerConnection.cs`
- `ClassIsland/Services/Management/ServerlessConnection.cs`
- `ClassIsland/Services/Management/ManagementService.cs`
- `ClassIsland/Services/ProfileService.cs`
- `ClassIsland/Services/SettingsService.cs`
- `ClassIsland.Shared/Models/Management/*.cs`
- `ClassIsland.Shared/Protobuf/**/*.proto`
