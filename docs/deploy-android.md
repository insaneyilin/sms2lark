# Android 短信转发部署指南

本文档记录从零部署"Android 手机 → 飞书机器人"完整链路的步骤。

---

## 前置条件

- 一台 Android 手机（共享手机号所在设备）
- 一台 macOS/Linux 服务器（运行转发服务）
- 飞书开发者账号 + 已创建应用
- ngrok 账号（免费版即可）或 cloudflared

---

## 1. 服务端部署

### 1.1 克隆项目并配置环境

```bash
cd /path/to/lark_agent

# 复制环境变量模板
cp .env.example .env
```

### 1.2 编辑 .env

```bash
# Webhook 认证 token（自定义，和手机端保持一致）
VCA_WEBHOOK_TOKEN=your-secret-token

# 注册的共享手机号（JSON 数组，只有这些号码可以转发）
VCA_REGISTERED_PHONES=["13800001111"]

# lark-cli 路径
VCA_LARK_CLI_PATH=/opt/homebrew/bin/lark-cli

# 默认推送用户（飞书 open_id，JSON 数组）
VCA_DEFAULT_SUBSCRIBERS=["ou_xxxxxxxxxxxx"]

# 群聊（暂不配可留空数组）
VCA_GROUP_CHAT_IDS=[]
VCA_AUTHORIZED_USERS=[]

# 验证码过期时间（秒）
VCA_CODE_TTL_SECONDS=300

# 服务端口
VCA_HOST=0.0.0.0
VCA_PORT=8900
```

### 1.3 配置飞书应用（首次）

```bash
# 初始化 lark-cli 应用（会弹出浏览器链接，按引导完成）
lark-cli config init --new
```

需要在飞书开发者后台（https://open.feishu.cn）为该应用开通权限：
- `im:message`
- `im:message:send_as_bot`

开通后创建版本并发布。

### 1.4 获取你的 open_id

```bash
# 授权用户身份
lark-cli auth login --scope "contact:user.base:readonly"
# 按提示打开链接完成授权，终端会输出你的 open_id (ou_xxx)
```

将 open_id 填入 `.env` 的 `VCA_DEFAULT_SUBSCRIBERS`。

### 1.5 验证机器人能发消息

```bash
lark-cli im +messages-send \
  --user-id ou_your_open_id \
  --text "机器人测试消息" \
  --as bot
```

飞书收到消息即代表配置成功。

### 1.6 启动服务

```bash
# 方式 1：前台运行（测试用）
uvicorn app.main:app --host 0.0.0.0 --port 8900

# 方式 2：后台运行
nohup uvicorn app.main:app --host 0.0.0.0 --port 8900 > server.log 2>&1 &

# 方式 3：Docker（生产推荐）
docker-compose up -d
```

验证服务启动：
```bash
curl http://127.0.0.1:8900/health
# 应返回 {"status": "ok", ...}
```

### 1.7 暴露公网 URL

手机需要能访问到服务端，使用 ngrok 做内网穿透：

```bash
# 必须用 nohup 后台启动，否则终端关闭或管道断开会导致 ngrok 退出
nohup ngrok http 8900 > /dev/null 2>&1 &

# 等几秒后查询公网 URL
curl -s http://127.0.0.1:4040/api/tunnels | python -c "import sys,json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])"
```

终端会显示公网 URL，类似：
```
https://xxxxx.ngrok-free.dev
```

记下这个 URL，后面手机配置要用。

> **⚠️ ngrok 免费版的问题**：
> - URL 不固定：每次重启 ngrok 会分配新 URL，需要同步更新手机 SmsForwarder 配置
> - 连接不稳定：免费版隧道可能偶尔断开，导致 503 ERR_NGROK_3004 错误
> - 不适合 7×24 生产使用
>
> **生产推荐方案**（任选其一）：
> - **cloudflared（推荐，免费 + 稳定）**：Cloudflare Tunnel 支持固定域名，断线自动重连
>   ```bash
>   brew install cloudflared
>   cloudflared tunnel --url http://localhost:8900
>   ```
> - **ngrok 付费版**：固定域名 `ngrok http 8900 --domain=your-name.ngrok.app`
> - **VPS 部署**：直接部署到有公网 IP 的服务器，无需内网穿透

---

## 2. Android 手机配置

### 2.1 安装 SmsForwarder

- 项目地址：https://github.com/pppscn/SmsForwarder
- 下载 APK：在 GitHub Releases 页面下载最新版安装
- 安装后授予权限：短信读取、后台运行、自启动

### 2.2 添加发送通道

打开 SmsForwarder → 发送通道 → 点右下角 `+` → 选 **Webhook**

按以下填写：

| 字段 | 值 |
|------|-----|
| 通道名称/状态 | `飞书验证码转发`（开关保持开启）|
| 请求方式 | `POST` |
| Webhook Server | `https://xxxxx.ngrok-free.dev/webhook/sms`（替换为你的 ngrok URL）|
| 消息模板 | 见下方 |
| Secret | 留空 |
| 成功应答关键字 | 留空 |
| 代理设置 | 无代理 |

**消息模板**填入（将 `your-phone-number` 替换为这台手机自身的号码）：
```json
{"sender":"[from]","content":"[org_content]","timestamp":[timestamp],"phone":"your-phone-number"}
```

> `phone` 字段是这台共享手机自己的号码，服务端用它做设备身份验证。
> 只有在 `.env` 的 `VCA_REGISTERED_PHONES` 中注册过的号码才能转发。

**Headers** 点 `+` 添加一行：
- 键：`Authorization`
- 值：`Bearer your-secret-token`（和 .env 中的 VCA_WEBHOOK_TOKEN 一致）

填好后点右下角 **「测试」** — 应返回成功。

### 2.3 添加转发规则

转发规则 → 点 `+` 添加：

| 字段 | 值 |
|------|-----|
| 匹配字段 | 全部 |
| 发送通道 | 选"飞书验证码转发" |
| 卡片类型 | 短信 |

保存即可。

### 2.4 保活设置（重要）

SmsForwarder 需要后台常驻，否则系统会杀进程：

1. **电池优化**：设置 → 电池 → 找到 SmsForwarder → 选"无限制"/"不优化"
2. **自启动**：设置 → 应用 → 自启动管理 → 允许 SmsForwarder
3. **锁定后台**：最近任务列表 → SmsForwarder 卡片 → 点锁图标
4. **SmsForwarder 内部**：设置 → 开启"前台服务"（会显示常驻通知）

> 不同手机品牌设置路径不同（小米/华为/OPPO 各有区别），核心是让 App 不被系统杀死。

---

## 3. 端到端验证

配好后，用另一台手机给共享手机发一条短信（或触发一个验证码），检查：

1. SmsForwarder 日志中显示"发送成功"
2. 飞书在 3 秒内收到机器人推送的消息
3. 消息包含完整原文 + 提取的验证码（如果有）

也可以在服务端直接 curl 模拟测试：
```bash
curl -X POST https://xxxxx.ngrok-free.dev/webhook/sms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{"sender":"10086","content":"【测试】验证码 123456","timestamp":0,"phone":"13800001111"}'
```

---

## 4. 多台手机扩展

如需接入第二台手机，只需：

1. `.env` 的 `VCA_REGISTERED_PHONES` 添加新号码：
   ```
   VCA_REGISTERED_PHONES=["another-phone-number", "your-phone-number", "18800001111"]
   ```

2. 新手机的 SmsForwarder 消息模板中 `phone` 填该手机号码：
   ```json
   {"sender":"[from]","content":"[org_content]","timestamp":[timestamp],"phone":"18800001111"}
   ```

3. 重启服务端即可。

---

## 5. 常见问题

### Q: SmsForwarder 测试返回 HTTP 400
**A**: timestamp 格式问题。确认服务端已更新（支持毫秒级 13 位时间戳）。

### Q: SmsForwarder 测试返回 HTTP 401
**A**: Authorization header 的 token 和服务端 .env 中的 `VCA_WEBHOOK_TOKEN` 不一致。检查拼写和空格。

### Q: 飞书没收到消息
**A**: 
1. 检查服务端日志有没有收到请求
2. 运行 `lark-cli im +messages-send --user-id ou_xxx --text "test" --as bot` 测试机器人是否能发送
3. 确认飞书应用已发布且权限已开通

### Q: ngrok URL 变了怎么办
**A**: 每次 ngrok 重启 URL 会变，需要去 SmsForwarder 更新 Webhook Server 地址。解决方案：
- 使用 ngrok 付费版固定域名
- 使用 cloudflared tunnel（免费固定域名）
- 部署到有公网 IP 的服务器

### Q: 小米手机收到短信但 SmsForwarder 转发日志为空
**A**: 小米/红米 (MIUI/HyperOS) 有"验证码安全保护"，会拦截短信广播不让第三方 App 接收。必须关闭：
1. 打开系统自带的 **「信息」** App（短信应用）
2. 点右上角设置（三个点或齿轮）
3. 找到 **「短信智能识别」**
4. 关闭 **「折叠验证码信息」** 和 **「锁屏时屏蔽验证码」**

关闭后 SmsForwarder 才能通过广播接收到短信。

### Q: 手机重启后转发不工作
**A**: 确认 SmsForwarder 已设置自启动 + 前台服务。参考 2.4 保活设置。

### Q: 消息模板变量有哪些
**A**: SmsForwarder 支持的变量：
- `[from]` — 发送方号码
- `[org_content]` — 原始短信内容
- `[content]` — 处理后的内容（可能被截断）
- `[timestamp]` — 时间戳（毫秒）
- `[device_name]` — 设备名称

---

## 6. 架构总结

```
Android 手机                    服务端 (macOS/Linux)              飞书
┌──────────────┐              ┌────────────────────┐          ┌──────┐
│ 收到短信     │   HTTP POST  │  FastAPI (8900)    │  lark-cli│      │
│ SmsForwarder │ ──────────>  │  解析 + 存储 + 推送 │ ────────>│ 用户 │
│ (Webhook)    │   via ngrok  │                    │          │      │
└──────────────┘              └────────────────────┘          └──────┘
```

完整数据流：
1. 手机收到短信
2. SmsForwarder 触发转发规则
3. POST JSON 到 ngrok 公网 URL
4. ngrok 转发到本地 8900 端口
5. FastAPI 验证 token → 解析验证码 → 存入内存
6. 调用 lark-cli 发送飞书消息给所有订阅者
7. 用户飞书收到推送（含原文 + 验证码高亮）
