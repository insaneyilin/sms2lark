# 验证码识别规则

本文档说明短信验证码的识别和提取逻辑。

---

## 识别策略

系统采用三层判断，任一层匹配即转发：

| 层级 | 说明 | 结果 |
|------|------|------|
| 精确提取 | 通过正则提取到具体验证码（数字或字母数字混合） | 转发 + 高亮显示验证码 |
| 关键词匹配 | 内容包含验证码相关关键词 | 转发（无法高亮具体码） |
| 形态匹配 | 短消息中包含独立的字母数字混合串 | 转发（无法高亮具体码） |
| 都不匹配 | 普通短信（聊天、广告等） | **忽略，不转发** |

---

## 精确提取规则

### 中文关键词 + 纯数字（4-8位）

```
验证码[为是：:\s]*(\d{4,8})
校验码[为是：:\s]*(\d{4,8})
动态密码[为是：:\s]*(\d{4,8})
认证码[为是：:\s]*(\d{4,8})
取件码[为是：:\s]*(\d{4,8})
```

### 英文关键词 + 纯数字（4-8位）

```
code\s*(is|:)?\s*(\d{4,8})
verification code?\s*(is|:)?\s*(\d{4,8})
OTP\s*(is|:)?\s*(\d{4,8})
PIN\s*(is|:)?\s*(\d{4,8})
passcode\s*(is|:)?\s*(\d{4,8})
```

### 关键词 + 字母数字混合码（4-8位）

```
验证码[为是：:\s]*([A-Za-z0-9]{4,8})
code\s*(is|:)?\s*([A-Za-z0-9]{4,8})
OTP\s*(is|:)?\s*([A-Za-z0-9]{4,8})
passcode\s*(is|:)?\s*([A-Za-z0-9]{4,8})
```

### 中文语境推断

```
(验证|校验|确认|登录|注册|绑定|认证|激活|找回|重置).*?(\d{4,8})
(\d{4,8})\s*(为你的|是你的|为您的|是您的)
(\d{4,8})\s*[（(].*?(有效|分钟|min)
```

---

## 关键词宽松匹配（HINT）

即使没提取到具体验证码，只要内容包含以下关键词就视为验证码短信：

- 中文：`验证码`、`校验码`、`动态密码`、`认证码`、`取件码`
- 英文：`code`、`OTP`、`PIN`、`passcode`、`verification`、`authenticate`
- 时效相关：`有效期`、`有效时间`、`分钟内`、`min` + 数字
- 场景 + 数字：`登录`/`注册`/`绑定`/`找回`/`重置`/`激活`/`认证` + 4-8位数字

---

## 形态匹配

短消息（<200字符）中包含独立的字母数字混合串（如 `A3k9Xp`），判定为可能的验证码：

- 字母开头 + 数字组合（如 `A3F8K2`）
- 数字字母交替（如 `3aB9c2`）
- 短消息（<80字符）中有字母+数字的 4-8 位组合串

---

## 平台名提取

从短信内容中的【】或 [] 括号中提取平台名：

```
【淘宝】→ 淘宝
[Google] → Google
```

如果没有括号，使用发送方号码作为平台名。

---

## 测试样本

### 应该转发（精确提取到验证码）

```bash
# 基本格式
curl -X POST http://127.0.0.1:8900/webhook/sms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{"sender":"10086","content":"【淘宝】验证码123456，5分钟内有效。","timestamp":0,"phone":"your-phone-number"}'

# 带冒号
curl -X POST http://127.0.0.1:8900/webhook/sms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{"sender":"106900","content":"【微信】你的验证码是：654321，请在10分钟内使用","timestamp":0,"phone":"your-phone-number"}'

# 英文格式
curl -X POST http://127.0.0.1:8900/webhook/sms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{"sender":"Google","content":"Your verification code is 987654","timestamp":0,"phone":"your-phone-number"}'

# code is 格式
curl -X POST http://127.0.0.1:8900/webhook/sms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{"sender":"Telegram","content":"Login code: 55234. Do not share.","timestamp":0,"phone":"your-phone-number"}'

# OTP
curl -X POST http://127.0.0.1:8900/webhook/sms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{"sender":"AWS","content":"Your OTP is 482917","timestamp":0,"phone":"your-phone-number"}'

# 字母数字混合
curl -X POST http://127.0.0.1:8900/webhook/sms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{"sender":"Apple","content":"Your verification code is A3F8K2","timestamp":0,"phone":"your-phone-number"}'

# 注册场景
curl -X POST http://127.0.0.1:8900/webhook/sms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{"sender":"106551","content":"【抖音】注册验证码888432，10分钟有效，请勿告知他人","timestamp":0,"phone":"your-phone-number"}'

# 动态密码
curl -X POST http://127.0.0.1:8900/webhook/sms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{"sender":"95588","content":"【工商银行】您的动态密码为239841，请于5分钟内输入","timestamp":0,"phone":"your-phone-number"}'

# 找回密码
curl -X POST http://127.0.0.1:8900/webhook/sms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{"sender":"106900","content":"找回密码验证码：776523，如非本人操作请忽略","timestamp":0,"phone":"your-phone-number"}'

# PIN码
curl -X POST http://127.0.0.1:8900/webhook/sms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{"sender":"Stripe","content":"Your Stripe PIN is 4829. Expires in 10 min.","timestamp":0,"phone":"your-phone-number"}'
```

### 应该转发（关键词匹配，但无法精确提取）

```bash
# 验证码格式不规则
curl -X POST http://127.0.0.1:8900/webhook/sms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{"sender":"106900","content":"【美团】您正在登录，验证码已发送至邮箱，请查收","timestamp":0,"phone":"your-phone-number"}'

# 含有效期但码不规范
curl -X POST http://127.0.0.1:8900/webhook/sms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{"sender":"Apple","content":"Use this code for authentication: 99-12-34. Valid for 5 min.","timestamp":0,"phone":"your-phone-number"}'
```

### 不应该转发（普通短信/广告）

```bash
# 纯文字
curl -X POST http://127.0.0.1:8900/webhook/sms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{"sender":"13800001111","content":"明天下午开会","timestamp":0,"phone":"your-phone-number"}'

# 广告
curl -X POST http://127.0.0.1:8900/webhook/sms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{"sender":"106900","content":"【京东】618大促来袭！全场满200减30，点击 jd.com 参与","timestamp":0,"phone":"your-phone-number"}'

# 纯英文聊天
curl -X POST http://127.0.0.1:8900/webhook/sms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{"sender":"13900001111","content":"Hello, are you coming tonight?","timestamp":0,"phone":"your-phone-number"}'

# 快递通知（无验证码）
curl -X POST http://127.0.0.1:8900/webhook/sms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{"sender":"106900","content":"【顺丰】您的快递已到达北京中转站，预计明天送达","timestamp":0,"phone":"your-phone-number"}'
```

---

## 批量测试脚本

将以上测试整合为一个脚本，快速验证：

```bash
#!/bin/bash
# test_parser.sh - 测试验证码识别规则

BASE_URL="http://127.0.0.1:8900/webhook/sms"
TOKEN="your-secret-token"
PHONE="your-phone-number"

send() {
    local desc="$1"
    local sender="$2"
    local content="$3"
    local expect="$4"

    result=$(curl -s -X POST "$BASE_URL" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"sender\":\"$sender\",\"content\":\"$content\",\"timestamp\":0,\"phone\":\"$PHONE\"}")

    code_found=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('code_found',''))" 2>/dev/null)

    if [ "$expect" = "yes" ] && [ "$code_found" != "False" ]; then
        echo "✅ PASS: $desc"
    elif [ "$expect" = "no" ] && [ "$code_found" = "False" ]; then
        echo "✅ PASS: $desc (correctly ignored)"
    elif [ "$expect" = "no" ] && echo "$result" | grep -q "code_found"; then
        echo "❌ FAIL: $desc (should be ignored but was forwarded)"
    else
        echo "⚠️  CHECK: $desc -> $result"
    fi
}

echo "=== 应该转发 ==="
send "中文验证码" "10086" "【淘宝】验证码123456，5分钟内有效" "yes"
send "英文 code" "Google" "Your verification code is 987654" "yes"
send "OTP" "AWS" "Your OTP is 482917" "yes"
send "字母数字混合" "Apple" "Your code is A3F8K2" "yes"
send "注册场景" "106551" "【抖音】注册验证码888432" "yes"
send "动态密码" "95588" "【工商银行】您的动态密码为239841" "yes"
send "PIN" "Stripe" "Your PIN is 4829" "yes"
send "Login code" "Telegram" "Login code: 55234" "yes"

echo ""
echo "=== 不应该转发 ==="
send "纯文字" "138xxx" "明天下午开会" "no"
send "广告" "106900" "【京东】618大促满200减30" "no"
send "英文聊天" "139xxx" "Hello, are you coming tonight?" "no"
send "快递通知" "106900" "【顺丰】您的快递已到达北京中转站" "no"
```

---

## 代码位置

识别逻辑在 `app/parser.py`：

- `extract_code()` — 精确提取验证码
- `looks_like_code_sms()` — 宽松关键词/形态判断
- `parse_sms()` — 入口函数，先尝试精确提取，再走宽松匹配

如需增加新的验证码格式支持，在 `CODE_PATTERNS`（精确提取）或 `HINT_PATTERNS`（宽松匹配）中添加正则即可。
