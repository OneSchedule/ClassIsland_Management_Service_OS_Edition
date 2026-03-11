# API References Index

> 自动整理：基于 `api/references/` 当前内容（2026-03-12）

## 文档本体

- `api/management-server-api.md`
- `api/openapi-like-example.json`
- `api/grpc-contract-summary.md`

## 1. 客户端实现源码（ClassIsland）

- `api/references/ClassIsland/Services/Management/ManagementServerConnection.cs`
- `api/references/ClassIsland/Services/Management/ManagementService.cs`
- `api/references/ClassIsland/Services/Management/ServerlessConnection.cs`
- `api/references/ClassIsland/Services/ProfileService.cs`
- `api/references/ClassIsland/Services/SettingsService.cs`

## 2. 集控模型与接口（ClassIsland.Shared）

- `api/references/ClassIsland.Shared/Abstraction/Services/IManagementServerConnection.cs`
- `api/references/ClassIsland.Shared/Enums/ManagementServerKind.cs`
- `api/references/ClassIsland.Shared/Models/Management/ManagementClientPersistConfig.cs`
- `api/references/ClassIsland.Shared/Models/Management/ManagementCredentialConfig.cs`
- `api/references/ClassIsland.Shared/Models/Management/ManagementManifest.cs`
- `api/references/ClassIsland.Shared/Models/Management/ManagementPolicy.cs`
- `api/references/ClassIsland.Shared/Models/Management/ManagementSettings.cs`
- `api/references/ClassIsland.Shared/Models/Management/ManagementVersions.cs`
- `api/references/ClassIsland.Shared/Models/Management/ReVersionString.cs`

## 3. Protobuf 契约（Service）

- `api/references/ClassIsland.Shared/Protobuf/Service/Audit.proto`
- `api/references/ClassIsland.Shared/Protobuf/Service/ClientCommandDeliver.proto`
- `api/references/ClassIsland.Shared/Protobuf/Service/ClientRegister.proto`
- `api/references/ClassIsland.Shared/Protobuf/Service/ConfigUpload.proto`
- `api/references/ClassIsland.Shared/Protobuf/Service/Handshake.proto`

## 4. Protobuf 契约（Client / Server）

### Client

- `api/references/ClassIsland.Shared/Protobuf/Client/AuditScReq.proto`
- `api/references/ClassIsland.Shared/Protobuf/Client/ClientCommandDeliverScReq.proto`
- `api/references/ClassIsland.Shared/Protobuf/Client/ClientRegisterCsReq.proto`
- `api/references/ClassIsland.Shared/Protobuf/Client/ConfigUploadScReq.proto`
- `api/references/ClassIsland.Shared/Protobuf/Client/HandshakeScReq.proto`

### Server

- `api/references/ClassIsland.Shared/Protobuf/Server/AuditScRsp.proto`
- `api/references/ClassIsland.Shared/Protobuf/Server/ClientCommandDeliverScRsp.proto`
- `api/references/ClassIsland.Shared/Protobuf/Server/ClientRegisterScRsp.proto`
- `api/references/ClassIsland.Shared/Protobuf/Server/ConfigUploadScRsp.proto`
- `api/references/ClassIsland.Shared/Protobuf/Server/HandshakeScRsp.proto`

## 5. Protobuf 命令与枚举

### Command

- `api/references/ClassIsland.Shared/Protobuf/Command/GetClientConfig.proto`
- `api/references/ClassIsland.Shared/Protobuf/Command/SendNotification.proto`

### Enum

- `api/references/ClassIsland.Shared/Protobuf/Enum/AuditEvents.proto`
- `api/references/ClassIsland.Shared/Protobuf/Enum/CommandTypes.proto`
- `api/references/ClassIsland.Shared/Protobuf/Enum/ConfigTypes.proto`
- `api/references/ClassIsland.Shared/Protobuf/Enum/ListItemUpdateOperations.proto`
- `api/references/ClassIsland.Shared/Protobuf/Enum/Retcode.proto`

## 6. Protobuf 审计事件载荷

- `api/references/ClassIsland.Shared/Protobuf/AuditEvent/AppCrashed.proto`
- `api/references/ClassIsland.Shared/Protobuf/AuditEvent/AppSettingsUpdated.proto`
- `api/references/ClassIsland.Shared/Protobuf/AuditEvent/AuthorizeEvent.proto`
- `api/references/ClassIsland.Shared/Protobuf/AuditEvent/ClassChangeCompleted.proto`
- `api/references/ClassIsland.Shared/Protobuf/AuditEvent/PluginInstalled.proto`
- `api/references/ClassIsland.Shared/Protobuf/AuditEvent/PluginUninstalled.proto`
- `api/references/ClassIsland.Shared/Protobuf/AuditEvent/ProfileItemUpdated.proto`
