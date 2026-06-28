# SMS Code Forwarder for Feishu/Lark

将共享手机收到的短信验证码实时转发到飞书机器人，支持私聊推送和群聊查询。

## 功能

- **实时转发**：手机收到验证码短信后 3 秒内推送到飞书
- **多设备支持**：可接入多台 Android/iPhone 共享手机
- **智能识别**：三层验证码匹配（精确提取 → 关键词 → 形态判断），自动过滤普通短信
- **订阅管理**：支持私聊/群聊订阅，可按手机号选择性接收
- **群聊查询**：在群里 @机器人 查询最近验证码
- **安全防护**：手机号注册验证、Token 认证、号码脱敏显示、验证码 TTL 自动过期

## 架构

```
Android/iPhone          Server                    Feishu
┌──────────────┐      ┌──────────────────┐      ┌──────┐
│ SmsForwarder │ POST │ FastAPI (8900)   │ push │      │
│ / Shortcuts  │ ───> │ 解析+存储+推送    │ ───> │ 用户 │
└──────────────┘      └──────────────────┘      └──────┘
       via cloudflared/ngrok       via lark-cli
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 lark-cli

```bash
# 安装
npm install -g @larksuite/cli

# 初始化飞书应用
lark-cli config init --new
```

在飞书开发者后台为应用开通权限：`im:message`、`im:message:send_as_bot`

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的配置
```

### 4. 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8900
```

### 5. 暴露公网（让手机能访问）

```bash
# 推荐 cloudflared（免费、稳定）
cloudflared tunnel --url http://localhost:8900

# 或 ngrok
ngrok http 8900
```

### 6. 配置手机

- **Android**：安装 [SmsForwarder](https://github.com/pppscn/SmsForwarder)，配置 Webhook 转发规则
- **iPhone**：通过 Mac 短信转发 + 监听脚本（详见文档）

详细步骤见 [Android 部署指南](docs/deploy-android.md) 和 [iPhone 部署方案](docs/deploy-iphone.md)。

## 机器人指令

### 私聊机器人

| 指令 | 效果 |
|------|------|
| `验证码` | 查询最近 5 条验证码 |
| `订阅` | 订阅所有手机推送 |
| `订阅 138****1234` | 只订阅指定手机 |
| `取消订阅` | 取消订阅 |
| `帮助` | 显示指令列表 |

### 群聊（需 @机器人）

| 指令 | 效果 |
|------|------|
| `@bot` | 查询最近 5 条验证码 |
| `@bot 订阅` | 订阅推送 |
| `@bot 取消订阅` | 取消订阅 |

## 项目结构

```
├── app/
│   ├── main.py              # FastAPI 入口 + lifespan
│   ├── config.py            # 配置管理（pydantic-settings）
│   ├── webhook.py           # POST /webhook/sms 端点
│   ├── parser.py            # 验证码识别与提取
│   ├── store.py             # 内存 TTL 存储
│   ├── lark_sender.py       # 飞书消息发送（lark-cli）
│   ├── event_listener.py    # 飞书事件监听（群聊/私聊）
│   ├── command_handler.py   # 指令处理（订阅/查询/帮助）
│   ├── subscribers.py       # 订阅者管理
│   └── models.py            # 数据模型
├── docs/
│   ├── design.md            # 系统设计文档
│   ├── deploy-android.md    # Android 部署指南
│   ├── deploy-iphone.md     # iPhone 部署方案
│   ├── subscription.md      # 订阅机制说明
│   ├── parser-rules.md      # 验证码识别规则 + 测试样本
│   └── get-ids.md           # 获取飞书 ID 指南
├── data/                    # 运行时数据（git ignored）
├── .env.example             # 环境变量模板
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 文档

| 文档 | 内容 |
|------|------|
| [系统设计](docs/design.md) | 架构、模块说明、安全设计 |
| [Android 部署](docs/deploy-android.md) | SmsForwarder 配置步骤 |
| [iPhone 部署](docs/deploy-iphone.md) | Mac 中转方案、iOS 快捷指令 |
| [订阅机制](docs/subscription.md) | 静态/动态订阅、权限控制 |
| [识别规则](docs/parser-rules.md) | 正则规则详解 + 测试样本 |
| [获取 ID](docs/get-ids.md) | 如何获取 open_id、chat_id |

## Docker 部署

```bash
docker-compose up -d
```

## License

MIT
