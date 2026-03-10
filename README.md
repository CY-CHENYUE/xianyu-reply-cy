# 🐟 xianyu-reply-cy — 闲鱼自动回复助手

适用于 Claude Code / OpenClaw 的闲鱼自动回复技能，通过 Playwright 驱动**真实 Chrome 浏览器**，自动监控闲鱼网页版消息并回复买家咨询。

## 功能特性

- **自动检测登录状态** — 支持扫码登录，持久化 Session
- **聊天列表监控** — 获取对话列表，识别未读消息
- **智能回复** — 读取对话内容，结合商品知识库生成回复
- **有趣卖家人设** — 像朋友聊天一样，偶尔抖机灵但不油腻
- **自动转人工** — 退货/退款/砍价超 10%/复杂问题自动标记转人工
- **反检测策略** — playwright-stealth 注入 + 随机化操作时序

## 安装

### 1. 安装依赖

```bash
cd xianyu-reply-cy
pip install playwright>=1.40 playwright-stealth>=1.0
python3 -m playwright install chromium
```

### 2. 配置商品知识库

编辑 `products.md`，填写你的商品信息（名称、价格、发货时间等），AI 会基于此生成回复。

## 命令速查

所有命令通过 `python3 scripts/xianyu.py` 调用，输出 JSON。

```bash
# 检查登录状态（会打开浏览器导航到闲鱼 IM）
python3 scripts/xianyu.py login

# 等待用户扫码登录（最多等 120 秒）
python3 scripts/xianyu.py wait-login [--timeout 120]

# 列出聊天对话（含未读标记）
python3 scripts/xianyu.py list-chats

# 读取某个对话的消息
python3 scripts/xianyu.py read-chat --index 0

# 在当前打开的对话中发送消息
python3 scripts/xianyu.py send --text "回复内容"

# 获取页面文字快照（调试用）
python3 scripts/xianyu.py snapshot

# 截图
python3 scripts/xianyu.py screenshot [--output path.png]
```

加 `--headless` 无头运行，`--debug` 查看详细错误。

## 项目结构

```
xianyu-reply-cy/
├── SKILL.md                    # Claude Code 技能定义
├── README.md
├── products.md                 # 商品知识库
└── scripts/
    ├── xianyu.py               # CLI 入口
    ├── actions/
    │   └── chat.py             # 聊天操作（列表/读取/发送）
    └── core/
        └── browser.py          # 浏览器实例管理
```

## 注意事项

- **不要**点击"确认收货"、"退款"、"举报"等敏感按钮
- **不要**修改商品价格、描述
- **只操作**聊天输入框和发送按钮
- 页面异常或找不到元素 → 停止并告知用户
- 请合理控制操作频率，避免触发平台风控

## 依赖

- **Python 3.10+**
- **Playwright** — 浏览器自动化
- **playwright-stealth** — 反检测

## 许可证

MIT License

---

<div align="center">
  <h3>联系作者</h3>
  <p>扫码加微信，交流反馈</p>
  <img src="assets/wechat-qr.jpg" alt="WeChat QR Code" width="200">
</div>
