# 订阅机制说明

本文档说明验证码转发的订阅推送机制。

---

## 概述

系统支持两层订阅者，收到短信时合并去重后推送：

| 层级 | 配置方式 | 特点 |
|------|---------|------|
| 静态订阅 | `.env` 中的 `VCA_DEFAULT_SUBSCRIBERS` | 始终收到所有手机的消息，重启不丢失 |
| 动态订阅 | 群聊对话指令 | 支持按手机订阅，持久化到 `data/subscribers.json` |

---

## 静态订阅（默认推送）

在 `.env` 中配置：

```bash
VCA_DEFAULT_SUBSCRIBERS=["ou_xxxxxxxxxxxx", "ou_another_user"]
```

- 这些用户**始终**收到所有手机的转发消息
- 适合管理员或固定需要接收验证码的人
- 修改后需重启服务生效

### 如何获取 open_id

```bash
lark-cli auth login --scope "contact:user.base:readonly"
# 按提示授权后终端会输出 open_id (ou_xxx)
```

---

## 动态订阅（群聊指令）

### 前提条件

1. 机器人已加入飞书群
2. `.env` 中配置了群的 chat_id：
   ```bash
   VCA_GROUP_CHAT_IDS=["oc_xxxxxxxxxxxxxxxx"]
   ```
3. 可选：配置授权用户（留空表示所有人可操作）：
   ```bash
   VCA_AUTHORIZED_USERS=["ou_user1", "ou_user2"]
   ```

### 获取群 chat_id

```bash
# 列出机器人所在的群
lark-cli im +chats-list --as bot
```

从返回结果中找到目标群的 `chat_id`（以 `oc_` 开头）。

### 支持的指令

在群聊中 @机器人 或直接发送以下消息：

| 指令 | 效果 |
|------|------|
| `订阅` | 订阅所有手机的验证码 |
| `订阅 138****1234` | 只订阅指定手机的验证码 |
| `取消订阅` | 取消全部订阅 |
| `验证码` / `最新验证码` / `发一下` | 查询最近的验证码 |
| `138****1234 的验证码` | 查询指定手机的验证码 |

> 指令匹配使用自然语言模糊匹配，不需要精确格式。

### 权限控制

- `VCA_AUTHORIZED_USERS` 为空数组 `[]` 时：群内所有人都可以操作
- 配置了用户列表时：只有列表中的用户可以订阅/查询

---

## 推送逻辑

收到短信时的推送流程：

```
短信到达
  ↓
解析验证码（可选）
  ↓
查询动态订阅者（按手机号匹配）
  ↓
合并静态订阅者（去重）
  ↓
并发推送给所有目标用户
```

代码逻辑（`webhook.py`）：

```python
subscribers = subscriber_manager.get_for_device(phone)        # 动态订阅者
all_targets = list(set(subscribers + settings.default_subscribers))  # 合并去重
```

### 订阅粒度

- 静态订阅者：收到**所有**手机的消息
- 动态订阅者：可以选择订阅 `all`（所有手机）或指定手机号

---

## 数据持久化

动态订阅数据保存在 `data/subscribers.json`：

```json
{
  "subscribers": {
    "ou_user_open_id": {
      "devices": ["all"]
    },
    "ou_another_user": {
      "devices": ["your-phone-number"]
    }
  }
}
```

- 服务重启后自动加载，不会丢失
- 文件不存在时自动创建

---

## 当前限制

1. **仅支持群聊订阅**：动态订阅只能通过群聊指令操作，暂不支持私聊机器人订阅
2. **无订阅确认推送**：订阅成功后只在群里回复，不会给用户私聊发确认
3. **无定时静默**：不支持设置"免打扰"时段
4. **群聊事件监听依赖 lark-cli**：需要 `lark-cli event +subscribe` 长连接运行

---

## 典型配置示例

### 场景 1：个人使用，不需要群聊

```bash
VCA_DEFAULT_SUBSCRIBERS=["ou_my_open_id"]
VCA_GROUP_CHAT_IDS=[]
```

所有验证码直接私聊推送给自己，无需群聊功能。

### 场景 2：团队使用，群聊共享

```bash
VCA_DEFAULT_SUBSCRIBERS=["ou_admin"]
VCA_GROUP_CHAT_IDS=["oc_team_group"]
VCA_AUTHORIZED_USERS=[]
```

管理员始终收到推送；团队成员在群里按需订阅/查询。

### 场景 3：严格权限控制

```bash
VCA_DEFAULT_SUBSCRIBERS=["ou_admin"]
VCA_GROUP_CHAT_IDS=["oc_team_group"]
VCA_AUTHORIZED_USERS=["ou_admin", "ou_trusted_user"]
```

只有授权用户可以在群里操作订阅和查询。
