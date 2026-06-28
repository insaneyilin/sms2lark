# iPhone 短信转发部署方案

本文档记录 iPhone 侧短信转发的可选方案。与 Android（SmsForwarder 全自动后台转发）不同，iOS 系统限制较多，需要根据实际条件选择方案。

---

## 方案对比

| 方案 | 全自动 | 需要额外设备 | 难度 | 推荐度 |
|------|--------|-------------|------|--------|
| Mac 短信转发 + 监听脚本 | ✅ | 需 Mac 常开 | 中 | ⭐⭐⭐ 推荐 |
| iOS 快捷指令自动化 | ❌ 需手动确认 | 无 | 低 | ⭐⭐ 临时用 |
| 越狱 + 插件 | ✅ | 无 | 高 | ⭐ 不推荐 |

---

## 方案 1：Mac 短信转发 + 监听脚本（推荐）

### 原理

iPhone 的"短信转发"功能可以将 SMS 同步到同 Apple ID 的 Mac 上。Mac 端脚本监听 Messages 数据库变化，检测到新短信后 POST 到 webhook。

### 前提条件

- iPhone 和 Mac 登录同一个 Apple ID
- Mac 需常开（可以合盖不休眠）
- Mac 和服务端网络互通

### 步骤

#### 1. 开启短信转发

iPhone 上操作：
1. 设置 → 信息 → 短信转发
2. 找到你的 Mac，开启开关
3. Mac 上"信息" App 确认

验证：让别人给 iPhone 发一条短信，Mac "信息" App 应同步收到。

#### 2. Mac 端监听脚本

核心思路：定时查询 Mac 上的 Messages SQLite 数据库（`~/Library/Messages/chat.db`），检测新消息后调用 webhook。

```python
#!/usr/bin/env python3
"""
mac_sms_monitor.py - 监听 Mac Messages 数据库，转发短信到 webhook
"""

import json
import sqlite3
import time
import urllib.request

# ========== 配置 ==========
WEBHOOK_URL = "https://xxxxx.ngrok-free.dev/webhook/sms"
WEBHOOK_TOKEN = "your-secret-token"
PHONE_NUMBER = "your-phone-number"  # 这台 iPhone 的号码
POLL_INTERVAL = 3  # 轮询间隔（秒）
DB_PATH = "/Users/你的用户名/Library/Messages/chat.db"
# ==========================

last_rowid = None


def get_latest_sms(db_path, since_rowid=None):
    """查询 Messages 数据库中的新 SMS 消息"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = """
        SELECT m.ROWID, m.text, h.id, m.date
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        WHERE m.is_from_me = 0
          AND m.service = 'SMS'
    """
    if since_rowid:
        query += f" AND m.ROWID > {since_rowid}"
    query += " ORDER BY m.ROWID ASC"

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return rows


def forward_to_webhook(sender, content):
    """POST 到 webhook"""
    payload = json.dumps({
        "sender": sender or "",
        "content": content or "",
        "timestamp": int(time.time()),
        "phone": PHONE_NUMBER,
    }).encode()

    req = urllib.request.Request(
        WEBHOOK_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {WEBHOOK_TOKEN}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"  -> 转发成功: {resp.status}")
    except Exception as e:
        print(f"  -> 转发失败: {e}")


def main():
    global last_rowid

    # 初始化：记录当前最大 ROWID，避免转发历史消息
    rows = get_latest_sms(DB_PATH)
    if rows:
        last_rowid = rows[-1][0]
    print(f"初始化完成，起始 ROWID: {last_rowid}")
    print(f"监听中... (每 {POLL_INTERVAL}s 检查一次)")

    while True:
        time.sleep(POLL_INTERVAL)
        try:
            rows = get_latest_sms(DB_PATH, last_rowid)
            for rowid, text, sender, date in rows:
                print(f"新短信: [{sender}] {text[:50]}")
                forward_to_webhook(sender, text)
                last_rowid = rowid
        except Exception as e:
            print(f"查询出错: {e}")


if __name__ == "__main__":
    main()
```

#### 3. 授予磁盘访问权限

macOS 默认不允许读取 `chat.db`，需要：

1. 系统设置 → 隐私与安全性 → 完全磁盘访问权限
2. 添加 **终端**（Terminal.app）或你使用的终端应用（iTerm2 等）

#### 4. 运行监听脚本

```bash
# 前台测试
python3 mac_sms_monitor.py

# 后台常驻
nohup python3 mac_sms_monitor.py > mac_sms_monitor.log 2>&1 &
```

#### 5. 验证

给 iPhone 发一条短信，检查：
1. Mac "信息" App 收到
2. 脚本输出 "新短信: ..."
3. 飞书收到推送

### 注意事项

- Mac 不能休眠（系统设置 → 节能 → 防止自动进入睡眠）
- `chat.db` 是只读查询，不会影响 Messages 正常使用
- Messages 数据库的 `date` 字段是 Core Data 时间戳（2001-01-01 起的秒数），非 Unix 时间戳
- 如果同时有 iMessage 消息，脚本通过 `service = 'SMS'` 过滤只转发短信

---

## 方案 2：iOS 快捷指令自动化

### 原理

利用 iOS 内置的"快捷指令"App 创建自动化规则：收到短信时触发 HTTP 请求。

### 限制（重要）

- **不能完全自动**：iOS 要求用户点击通知确认运行（安全策略，无法绕过）
- **无法获取短信内容变量**：快捷指令的"信息"触发器不提供消息正文作为变量
- **仅适合临时/手动场景**

### 步骤

1. 打开 **快捷指令** App → 自动化 → 右上角 `+`
2. 选 **信息** → "发送者"选"任何人" → "当我收到信息时"
3. 添加操作 → 搜索 **获取 URL 内容**：
   - URL: `https://你的地址/webhook/sms`
   - 方法: POST
   - 请求头: `Authorization` = `Bearer your-secret-token`
   - 请求体: JSON
     ```json
     {
       "sender": "unknown",
       "content": "请查看手机",
       "timestamp": 0,
       "phone": "your-phone-number"
     }
     ```
4. 关闭"运行前询问"（iOS 仍会弹通知，需点击确认）

> 由于无法自动获取短信内容，这个方案只能起到"提醒"作用（通知你有新短信），无法转发原文。

---

## 方案 3：越狱方案（不推荐）

越狱后可安装 Activator 等插件实现短信自动触发 shell 命令，但：
- 越狱会丧失系统安全性
- iOS 更新后需要重新越狱
- 对共享手机不合适

不做详细展开。

---

## 总结

对于 iPhone 的共享手机场景：

- **有 Mac 常开**：用方案 1，可以做到和 Android 一样的全自动转发
- **没有 Mac**：方案 2 只能做提醒，无法自动转发原文；需考虑其他方式（如换 Android 手机）

服务端侧无需任何修改——iPhone 和 Android 最终都是 POST 到同一个 `/webhook/sms` 接口，只是手机端的触发方式不同。
