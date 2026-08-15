# 账号安全与体验改进实施计划

> 日期：2026-08-16 ｜ 对应设计：[2026-08-16-account-ux-security-improvements-design.md](../specs/2026-08-16-account-ux-security-improvements-design.md)

## Goal

注销/删除账号强制当场密码复核；密码强度显示；注册完成自动跳登录；登录页记住账号/密码。

## Global Constraints

- 分支 `codex/account-ux-security`；每 Task 独立提交且提交点测试全绿；TDD。
- 安全不降级：注销类操作排除在 30 分钟窗口豁免外；记住密码默认关闭、仅成功登录后落盘。

## Task 1 — 后端注销类操作强制「密码 + 任意 2FA」

- Modify `backend/app/services/stepup.py`：新增 `authorize_critical_operation`（密码 + email_otp/totp 二码校验、按邮箱 2FA 失败限流、审计 `stepup_2fa_failed`）
- Modify `backend/app/schemas/auth.py`：`PasswordConfirm` 增加 `stepup_method`/`stepup_code`
- Modify `backend/app/api/routes/users.py`：新增 `POST /me/step-up/send`；`delete_own_account` 走 `authorize_critical_operation`
- Modify `backend/app/api/routes/admin_users.py`：`delete_user`、`batch_delete_users` 同理（schema 增加 stepup 字段）
- Modify `backend/tests/test_stepup_endpoints.py`、`test_admin_stepup_window.py`：删除类用例改为密码+邮箱 2FA
- Create `backend/tests/test_critical_stepup.py`：缺密码/缺 2FA/错码 400、密码+任意 2FA 成功、TOTP 方式成功、2FA 失败限流 429、窗口不豁免

Checklist：

- [ ] 写/改测试确认红
- [ ] 实现服务、send 端点与三处端点校验
- [ ] 单测绿；后端全量绿
- [ ] 提交 `feat: 注销与删除账号强制密码加任意 2FA 复核`

## Task 2 — 前端注销/删除弹窗双因素复核

- Modify `frontend/src/api/client.ts`：`meApi.stepUpSend()`
- Create `frontend/src/components/StepUp2faForm.tsx`：密码 + 方式单选 + 验证码 + 获取邮箱验证码（60s 冷却）
- Modify `DashboardPage`（注销）、`AdminUsersPanel`（删除/批量删除）接入复合表单
- Modify 相关前端测试

Checklist：

- [ ] 改测试确认红
- [ ] 实现组件并接入三处
- [ ] `tsc/lint/test` 绿
- [ ] 提交 `feat: 前端注销与删除账号双因素复核表单`

## Task 3 — 密码强度显示

- Create `frontend/src/hooks/usePasswordStrength.ts`、`frontend/src/components/PasswordStrength.tsx`
- Modify `RegisterPage` / `InviteRegisterPage` / `ResetPasswordPage` / `DashboardPage`（新密码）/ `AdminUsersPanel`（初始密码）接入
- Create `frontend/src/__tests__/PasswordStrength.test.tsx`（评分/标签/空值不显示）

Checklist：

- [ ] 写测试确认红
- [ ] 实现 hook/组件并接入五处
- [ ] `tsc/lint/test` 绿
- [ ] 提交 `feat: 密码输入新增强度显示`

## Task 4 — 注册完成自动跳转登录

- Modify `RegisterPage`：成功后 `navigate('/login?email=...')` + toast
- Modify `LoginPage`：读取 `?email=` 预填邮箱
- Modify `RegisterPage.test.tsx`、`LoginPage.test.tsx` 补断言

Checklist：

- [ ] 改测试确认红
- [ ] 实现跳转与预填
- [ ] `tsc/lint/test` 绿
- [ ] 提交 `feat: 注册完成自动跳转登录页并预填邮箱`

## Task 5 — 记住账号 / 记住密码

- Modify `LoginPage`：两个复选框、localStorage 读写、成功登录后落盘/取消勾选清除
- Create `frontend/src/lib/remember.ts`（键常量 + 读写 + 清除）
- Modify `LoginPage.test.tsx`：回填、成功落盘、失败不落盘、取消清除

Checklist：

- [ ] 写测试确认红
- [ ] 实现功能
- [ ] `tsc/lint/test` 绿
- [ ] 提交 `feat: 登录页支持记住账号与记住密码`

## Task 6 — 文档、CHANGELOG 与全量验证

- Modify `CHANGELOG.md`（功能/行为变更/安全加固）
- Modify `README.md`（注册跳转、密码强度、记住凭据、注销强制复核）

Checklist：

- [ ] 后端全量、前端 `tsc/lint/test/build` 全绿
- [ ] 依赖审计无新增
- [ ] 提交 `docs: 同步账号安全与体验改进文档`

## 收尾

- 合并 `codex/account-ux-security` 回 `main`（保留 merge 记录）
