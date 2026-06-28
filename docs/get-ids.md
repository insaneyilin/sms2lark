# 获取飞书 ID 指南

配置订阅和群聊功能时需要用到 `open_id`（用户标识）和 `chat_id`（群标识）。本文档记录获取方式。

---

## 获取群聊 chat_id

前提：机器人已被拉入目标群。

```bash
lark-cli im +chats-list --as bot
```

返回结果中每个群包含 `chat_id`（以 `oc_` 开头），找到目标群复制即可。

将 chat_id 填入 `.env`：
```bash
VCA_GROUP_CHAT_IDS=["oc_xxxxxxxxxxxxxxxx"]
```

---

## 获取用户 open_id

### 方式 1：通过手机号查询

```bash
lark-cli contact +users-batch-get-id --mobiles '["13800001111"]' --as bot
```

> 需要应用有 `contact:user.id:readonly` 权限。在飞书开发者后台 → 权限管理中开通。

### 方式 2：通过邮箱查询

```bash
lark-cli contact +users-batch-get-id --emails '["someone@company.com"]' --as bot
```

### 方式 3：通过群成员列表

已知群的 chat_id 时，可以直接列出所有成员的 open_id：

```bash
lark-cli im +chat-members-get --chat-id oc_xxxxx --as bot
```

返回每个成员的 `member_id` 即为 open_id（以 `ou_` 开头）。

### 方式 4：让用户自己获取

让对方在自己电脑上执行（需安装 lark-cli）：

```bash
lark-cli auth login --scope "contact:user.base:readonly"
```

按提示打开链接授权后，终端会输出其 open_id。

---

## 推荐流程

最简单的操作路径：

1. 把机器人拉入飞书群
2. `lark-cli im +chats-list --as bot` → 拿到 chat_id
3. `lark-cli im +chat-members-get --chat-id oc_xxx --as bot` → 拿到群内所有人的 open_id
4. 按需填入 `.env` 的对应配置项

---

## 权限要求

| 操作 | 所需权限 | 身份 |
|------|---------|------|
| 列出机器人所在群 | `im:chat:readonly` | bot |
| 获取群成员列表 | `im:chat:readonly` | bot |
| 通过手机号/邮箱查用户 | `contact:user.id:readonly` | bot |

权限在飞书开发者后台（https://open.feishu.cn）→ 应用 → 权限管理 中开通，开通后需发布新版本生效。
