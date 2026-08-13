# 站内信与自定义邮件通知设计

- 日期：2026-08-14
- 状态：已实施完成（2026-08-14）
- 范围：管理端统一通知中心（站内信 + 自定义邮件）+ 用户收件箱与邮件偏好

## 1. 目标

管理员在管理后台撰写一条通知，一次发布可同时送达「站内信」与「邮件」两个渠道，收件人可选全部用户或在已注册用户列表勾选；用户在用户中心收件箱查看站内信，并可在基本资料中关闭邮件通知（站内信始终保留）。

## 2. 已确认的决策

1. 收件人：全部活跃用户，或在已注册用户列表勾选（提交 `user_ids`）。
2. 邮件正文：纯文本，支持 `{nickname}`、`{email}` 占位符按收件人替换。
3. 邮件偏好：用户资料中新增「接收邮件通知」开关，默认开启；关闭后只发站内信、不再收邮件。

## 3. 数据模型

### `notifications`（一次发送的元数据，供管理端历史列表）

| 列 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID PK | |
| `title` | String(120) | 标题模板 |
| `body` | Text | 正文模板 |
| `in_site` | Boolean | 是否发站内信 |
| `email` | Boolean | 是否发邮件 |
| `sender_id` | UUID FK users（SET NULL） | 发送管理员 |
| `recipient_count` | Integer | 收件人总数 |
| `email_sent` | Integer | 邮件发送成功数 |
| `email_failed` | Integer | 邮件发送失败数 |
| `created_at` | timestamptz | |

### `notification_recipients`（每收件人一条，承载已读状态）

| 列 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID PK | 也作为用户侧“消息 ID” |
| `notification_id` | UUID FK notifications（CASCADE） | |
| `user_id` | UUID FK users（CASCADE） | |
| `read_at` | timestamptz nullable | 已读时间 |
| `created_at` | timestamptz | 用于收件箱排序 |

约束：`(notification_id, user_id)` 唯一；索引 `(user_id, created_at)`。

### `users.email_notifications`

Boolean，默认 `True`。关闭后仅跳过邮件渠道，不影响站内信。

## 4. 接口设计

### 管理端（仅管理员）

| 方法 | 路径 | 语义 |
| --- | --- | --- |
| `POST` | `/api/v1/admin/notifications` | 发送通知。请求体见下；返回 `{id, recipient_count, email_sent, email_failed}` |
| `GET` | `/api/v1/admin/notifications?offset&limit` | 发送历史（倒序分页），含渠道、数量、发送人 |

发送请求体：

```json
{
  "title": "维护通知",
  "body": "您好，{nickname}：平台将于……",
  "in_site": true,
  "email": true,
  "user_ids": ["uuid-1", "uuid-2"]
}
```

- `title` 1–120、`body` 1–5000；`in_site`/`email` 至少一个为真。
- `user_ids` 省略 → 全部活跃用户；提供时（1–500）按 ID 解析为活跃用户，不存在的或已停用的用户被跳过并计入响应 `skipped`；全部无效时返回 400。
- 全部用户超过单次上限时返回 400，提示改用指定用户分批发送。
- 复用管理员频率限制（默认 20 次/小时，按来源 IP 计数），超限返回 429 并记审计。

### 用户端（仅本人）

| 方法 | 路径 | 语义 |
| --- | --- | --- |
| `GET` | `/api/v1/me/messages?offset&limit` | 收件箱列表，返回 `{items, total, unread}` |
| `GET` | `/api/v1/me/messages/unread-count` | 返回 `{unread}`，供头部铃铛 |
| `POST` | `/api/v1/me/messages/{id}/read` | 标记已读（幂等），204 |
| `POST` | `/api/v1/me/messages/read-all` | 全部已读，返回 `{updated}` |
| `DELETE` | `/api/v1/me/messages/{id}` | 删除本人消息，204 |

消息条目：`{id, title, body, sent_at, read}`。所有操作校验归属，非本人消息返回 404。

### 用户资料

`PUT /api/v1/me` 与 `UserOut` 新增 `email_notifications: bool | null`；为 `null` 时不修改。

## 5. 发送流程

1. 校验渠道、正文与收件人范围，过频率限制。
2. 写入 `notifications` 与全部 `notification_recipients` 行（站内信就此送达）。
3. 若勾选邮件：跳过 `email_notifications=False` 的用户，对其余收件人渲染 `{nickname}`/`{email}` 占位符后，复用 SMTP 单连接批量发送（沿用现有邀请批量发送的连建、失败重建与重试策略）。
4. 汇总成功/失败数回写 `notifications`，失败邮箱写入日志与审计详情（最多前 20 个）。

## 6. 前端

- 管理端：`/admin/notifications` 新增「通知管理」标签页，上半部撰写表单（收件人单选 + 已注册用户勾选列表（支持搜索与已选计数）、渠道复选、标题、正文、占位符说明），下半部发送历史表格。
- 用户端：新增 `/messages` 收件箱页（未读高亮、全部已读、删除、空状态）；`AppHeader` 增加铃铛入口显示未读数（超过 99 显示 99+），请求失败时隐藏。
- 用户中心基本资料卡片增加「接收邮件通知」复选框，随资料一起保存。

## 7. 审计与安全

- 审计动作 `admin_send_notification`，新增分类 `admin_notification`（前端筛选标签「通知管理」），detail 记录标题、渠道、数量与失败邮箱。
- 仅管理员可发送；用户接口只允许操作本人消息。
- 收件人上限与频率限制的默认值可在环境变量覆盖：`NOTIFICATION_MAX_RECIPIENTS`（500）、`ADMIN_NOTIFICATION_RATE_LIMIT`（20）、`ADMIN_NOTIFICATION_RATE_WINDOW_SECONDS`（3600）。

## 8. 保留与清理

维护任务新增：删除 `read_at` 早于 `NOTIFICATION_RETENTION_DAYS`（默认 180 天）的已读收件行；未读消息与发送历史不清理。

## 9. 测试

- 后端：发送（全量/指定 user_ids/占位符/双渠道/关闭邮件偏好）、缺失或停用用户跳过计数、参数与上限校验、频率限制、非管理员 403、历史列表、收件箱与已读/删除的归属校验、审计分类、邮件服务单封与批量、保留清理。
- 前端：管理端撰写表单校验与提交体、历史渲染；收件箱未读/已读/删除/全部已读；铃铛徽章与失败隐藏；资料页邮件开关。

## 10. 非目标（后续）

HTML 富文本/附件、发送后台任务队列、按角色筛选收件人、消息模板库、定时发送。
