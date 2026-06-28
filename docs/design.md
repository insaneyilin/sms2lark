# 验证码自动转发飞书机器人 — 设计与开发文档

## 1. 项目背景

团队有多台共享手机号，日常需要接收各类平台的短信验证码。现状是每次需要验证码时，必须找到物理手机手动查看，效率低且不适合远程协作。

**目标**：构建一个自动化系统，将共享手机收到的验证码实时转发到飞书机器人，支持私聊推送和群聊查询。

**核心需求**：
- 实时性：短信到达后 3 秒内推送到飞书
- 稳定性：7×24 后台运行不掉线
- 多设备：支持多台共享手机同时接入
- 可订阅：用户可选择接收全部或指定手机的验证码
- 安全性：验证码不持久存储，访问需授权

---

## 2. 系统架构

```
┌─────────────────────┐
│ Phone A (Android)   │──┐
│ SmsForwarder App    │  │
└─────────────────────┘  │
                         │  HTTP POST /webhook/sms
┌─────────────────────┐  │  (携带 device_id + token)
│ Phone B (iPhone)    │──┤
│ iOS Shortcuts       │  │
└─────────────────────┘  │
                         │
┌─────────────────────┐  │        ┌──────────────────────────────┐
│ Phone C (...)       │──┘        │     FastAPI Server            │
└─────────────────────┘  -------->│     (uvicorn, port 8900)     │
                                  │                              │
                                  │  ┌────────┐   ┌──────────┐  │
                                  │  │Webhook │──>│ Parser   │  │
                                  │  │Receiver│   │(正则提取) │  │
                                  │  └────────┘   └────┬─────┘  │
                                  │                    │         │
                                  │              ┌─────▼──────┐  │
                                  │              │ CodeStore  │  │
                                  │              │(内存+TTL)  │  │
                                  │              └─────┬──────┘  │
                                  │                    │         │
                                  │  ┌─────────────────▼──────┐  │
                                  │  │    Lark Dispatcher     │  │
                                  │  │  - 私聊推送订阅者      │  │
                                  │  │  - 群聊回复查询        │  │
                                  │  └────────────────────────┘  │
                                  │                              │
                                  │  ┌────────────────────────┐  │
                                  │  │   Event Listener       │  │
                                  │  │  (lark-cli 长连接)     │  │
                                  │  │   监听群消息指令       │  │
                                  │  └────────────────────────┘  │
                                  └──────────────────────────────┘
                                              │
                                              │ lark-cli im +messages-send
                                              ▼
                                     ┌────────────────┐
                                     │  飞书用户/群聊  │
                                     └────────────────┘
```

### 数据流

1. 手机收到短信 → SmsForwarder/iOS Shortcuts 将短信内容 POST 到 webhook
2. Server 验证 token → 正则提取验证码和平台名 → 存入内存（5分钟 TTL）
3. 查找该设备的所有订阅者 → 通过 lark-cli 并发推送私聊消息
4. 同时，Event Listener 监听群消息，授权用户发自然语言指令时回复验证码

---

## 3. 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| Web 框架 | FastAPI | 异步、性能好、自带请求校验 |
| 配置管理 | pydantic-settings | 类型安全、支持 .env |
| 飞书 API | lark-cli (subprocess) | 无需自行实现 OAuth，CLI 已处理认证 |
| 验证码存储 | 内存 dict + asyncio 定时清理 | 简单可靠，无外部依赖，安全（不落盘）|
| 订阅持久化 | JSON 文件 | 数据量小，无需数据库 |
| 部署 | Docker + docker-compose | restart: always 保证 7×24 |
| 手机侧 | SmsForwarder (Android) / iOS Shortcuts | 成熟方案，支持 Webhook |

**零新依赖原则**：所有 Python 包均为开发环境已安装的，无需额外 `pip install`。

---

## 4. 模块设计

### 4.1 配置模块 (`app/config.py`)

基于 `pydantic-settings`，从环境变量或 `.env` 文件加载配置。所有配置项以 `VCA_` 为前缀。

关键配置：
- `VCA_WEBHOOK_TOKEN`：Webhook 认证令牌
- `VCA_DEVICES`：设备 ID 到显示名的 JSON 映射
- `VCA_DEFAULT_SUBSCRIBERS`：默认推送用户列表
- `VCA_GROUP_CHAT_IDS`：机器人监听的群 chat_id
- `VCA_AUTHORIZED_USERS`：有权在群里查验证码的用户

### 4.2 验证码解析 (`app/parser.py`)

多模式正则引擎，覆盖中英文验证码格式：

```python
CODE_PATTERNS = [
    r"验证码[为是：:\s]*(\d{4,8})",
    r"校验码[为是：:\s]*(\d{4,8})",
    r"动态密码[为是：:\s]*(\d{4,8})",
    r"(?:code|Code|CODE)\s*(?:is|:)?\s*(\d{4,8})",
    r"(?:verification|Verification)\s*(?:code|Code)?\s*(?:is|:)?\s*(\d{4,8})",
    r"(?:验证|校验|确认|登录|注册|绑定).*?(\d{4,8})",
]
```

平台名从短信中的【】括号提取（中国短信标准格式）。

### 4.3 内存存储 (`app/store.py`)

- 数据结构：`dict[device_id, list[CodeRecord]]`
- TTL：默认 5 分钟，后台每 30 秒清理一次
- 容量限制：每设备最多保留 20 条记录
- 查询接口：按设备/按平台/最新 N 条

### 4.4 飞书发送 (`app/lark_sender.py`)

通过 `asyncio.create_subprocess_exec` 调用 lark-cli：

```bash
lark-cli im +messages-send --user-id ou_xxx --markdown "..." --as bot
lark-cli im +messages-send --chat-id oc_xxx --markdown "..." --as bot
```

推送消息格式：
```
**验证码**
来源: 淘宝
手机: 138****1234
验证码: `882233`
发送方: 10086
```

### 4.5 群聊指令处理 (`app/command_handler.py`)

支持的自然语言指令：

| 用户说 | 机器人行为 |
|--------|-----------|
| "验证码" / "最新验证码" / "发一下码" | 回复最新 3 条验证码 |
| "phone-a 的验证码" / "138 的验证码" | 回复指定设备的验证码 |
| "订阅" / "订阅 phone-a" | 将用户加入订阅列表 |
| "取消订阅" | 移除订阅 |

### 4.6 事件监听 (`app/event_listener.py`)

- 运行 `lark-cli event +subscribe` 作为长连接子进程
- 逐行读取 NDJSON 输出
- 崩溃后 5 秒自动重连
- 仅在配置了 `GROUP_CHAT_IDS` 时启用

### 4.7 订阅管理 (`app/subscribers.py`)

- 数据格式：`{user_id: {devices: ["all"] | ["phone-a"]}}`
- JSON 文件持久化到 `data/subscribers.json`
- 支持按设备订阅：用户可只关注特定手机的验证码

---

## 5. 安全设计

| 威胁 | 防护措施 |
|------|----------|
| Webhook 伪造请求 | Bearer token 认证，必须携带正确 token 才接受 |
| 验证码泄露 | 纯内存存储 + 5 分钟 TTL 自动过期，不写日志/不落盘 |
| 日志中泄露 | 日志中验证码脱敏：`12**56` |
| 未授权群聊查询 | 配置 authorized_users 白名单 |
| 重放攻击 | 校验请求 timestamp 在 5 分钟内 |
| 凭据泄露 | `.env` 不入 git，Docker 中 volume 挂载 |

---

## 6. 多设备支持

每台手机通过 `device_id` 唯一标识（如 `phone-a`、`phone-b`），在 webhook 请求体中携带。

配置映射示例：
```json
{"phone-a": "138****1234", "phone-b": "139****5678"}
```

订阅粒度：
- `"all"` — 接收所有设备的验证码
- `"phone-a"` — 只接收指定设备的验证码

推送消息中包含设备标签，方便用户识别来源。

---

## 7. API 接口

### POST /webhook/sms

接收手机转发的短信。

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Body:**
```json
{
  "sender": "10086",
  "content": "【淘宝】验证码：123456，5分钟内有效。",
  "timestamp": 1719561600,
  "device_id": "phone-a"
}
```

**Response:**
```json
{"status": "ok", "code_found": true, "platform": "淘宝"}
```

### GET /health

系统健康检查。

**Response:**
```json
{
  "status": "ok",
  "uptime_seconds": 3600,
  "event_listener_alive": true,
  "codes_in_store": 3,
  "subscribers": 5,
  "devices": ["phone-a", "phone-b"]
}
```

---

## 8. 部署方式

### 本地开发

```bash
cp .env.example .env
# 编辑 .env 填入实际配置
uvicorn app.main:app --host 0.0.0.0 --port 8900
```

### 暴露 Webhook（让手机能访问）

```bash
# 方式 1: Cloudflare Tunnel（推荐，免费稳定）
cloudflared tunnel --url http://localhost:8900

# 方式 2: ngrok
ngrok http 8900
```

### Docker 生产部署

```bash
docker-compose up -d
```

`restart: always` + healthcheck 确保服务 7×24 自动恢复。

---

## 9. 手机侧配置

### Android — SmsForwarder

1. 从 GitHub 下载安装 [SmsForwarder](https://github.com/pppscn/SmsForwarder)
2. 添加发送通道：类型选 Webhook
3. 配置：
   - URL: `https://<your-tunnel>/webhook/sms`
   - 方法: POST
   - Headers: `Authorization: Bearer <your-token>`
   - Body 模板:
     ```json
     {"sender": "[from]", "content": "[content]", "timestamp": [timestamp], "device_id": "phone-a"}
     ```
4. 添加转发规则：匹配全部短信（或按需过滤）

### iPhone — iOS Shortcuts + Automation

1. 创建 Shortcut "转发短信"
2. 操作：获取剪贴板/短信内容 → POST 到 webhook URL
3. 创建 Automation：收到短信时 → 运行 Shortcut
4. 注意：iOS 限制较多，可能需要 Bark 等辅助 App

---

## 10. 开发过程

### 阶段 1: 基础框架搭建

1. 确定技术栈：FastAPI + lark-cli + 内存存储
2. 创建项目结构，编写 `config.py` + `models.py`
3. 实现验证码正则解析器，用 20+ 样本测试覆盖中英文格式

### 阶段 2: 核心流程 (Webhook → Push)

1. 实现 `webhook.py`：HTTP 端点 + token 认证
2. 实现 `store.py`：TTL 内存存储
3. 实现 `lark_sender.py`：lark-cli subprocess 封装
4. 串联 `main.py`：FastAPI lifespan 管理生命周期
5. 集成测试：curl 模拟短信 → 验证流程通畅

### 阶段 3: 群聊交互

1. 实现 `event_listener.py`：lark-cli 长连接 + 自动重连
2. 实现 `command_handler.py`：自然语言指令匹配
3. 实现 `subscribers.py`：订阅管理 + JSON 持久化

### 阶段 4: 容器化与部署

1. 编写 Dockerfile + docker-compose.yml
2. 配置 healthcheck 自动恢复
3. 文档记录部署和手机侧配置步骤

---

## 11. 项目文件清单

```
lark_agent/
├── app/
│   ├── __init__.py          # 包标识
│   ├── main.py              # 应用入口，lifespan 管理
│   ├── config.py            # 配置管理 (pydantic-settings)
│   ├── models.py            # 数据模型 (SmsPayload, CodeRecord)
│   ├── webhook.py           # Webhook 端点 + 认证
│   ├── parser.py            # 验证码正则提取
│   ├── store.py             # 内存 TTL 存储
│   ├── lark_sender.py       # 飞书消息发送
│   ├── event_listener.py    # 群消息事件监听
│   ├── command_handler.py   # 群聊指令处理
│   └── subscribers.py       # 订阅管理
├── data/
│   └── subscribers.json     # 订阅者持久化
├── docs/
│   └── design.md            # 本文档
├── .env.example             # 环境变量模板
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── task.txt                 # 原始需求
```
