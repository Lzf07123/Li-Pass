# 强制 2FA 实施计划

> 日期：2026-08-16 ｜ 对应设计：[2026-08-16-mandatory-2fa-design.md](../specs/2026-08-16-mandatory-2fa-design.md)

## Goal

验证邮箱后自动启用邮箱 2FA 作为默认方案；账号必须至少保留一种 2FA；管理员重置恢复默认；历史用户通过迁移与登录兜底强制纳入。

## Global Constraints

- 分支 `codex/mandatory-2fa`；每 Task 独立提交且提交点测试全绿；
- 安全不降级：未验证邮箱仍 1FA（无法收码），验证后强制；关闭最后一种 2FA 必须拒绝；
- 数据迁移写 Alembic，downgrade 为 no-op（历史意图不可恢复，文档注明）。

## Task 1 — 测试基础设施：登录辅助函数完成邮箱 2FA

- Modify `backend/tests/helpers.py`：`register_and_login` 在登录返回 `requires_2fa` 时自动 `2fa/send` + `2fa/verify`；新增 `login_with_email_2fa(client, captured_email, email, password, **kwargs)`

Consumes：现有 2FA 端点（已存在）
Produces：可复用的强制 2FA 登录辅助函数

Checklist：

- [ ] 改造 helper，全量回归仍绿（此时生产行为未变，兜底分支不触发）
- [ ] 提交 `test: 登录辅助函数支持完成邮箱 2FA 挑战`

## Task 2 — 自动启用邮箱 2FA + 数据迁移

- Modify `backend/app/api/routes/auth.py`：`verify_email` 成功置 `email_otp_enabled=True`（审计 detail 标记）；邀请注册创建时置 True；登录兜底（已验证且无任何 2FA → 自动开启 + 审计 `2fa_email_auto_enabled`）
- Modify `backend/app/api/routes/admin_users.py`：`create_user` 创建时 `email_otp_enabled=True`
- Create `backend/alembic/versions/a2b3c4d5e6f7_enable_email_2fa_for_verified_users.py`（链自 `f1a2b3c4d5e6`，upgrade 数据 UPDATE，downgrade no-op）
- Test：`test_auth_register.py` 验证后断言 `email_otp_enabled=True`；新增 `backend/tests/test_force_2fa.py`（验证后登录 requires_2fa、登录兜底自动开启、邀请/代建默认启用、未验证仍 1FA）
- Modify `backend/tests/test_auth_login.py`：`register_and_verify` 后登录改走 `login_with_email_2fa`
- Modify `backend/tests/test_user_center.py`：多会话用例的再次登录走 2FA
- Modify `backend/tests/test_account_invites.py`：管理员代建账号登录走 2FA

Checklist：

- [ ] 写/改测试确认红
- [ ] 实现四处自动启用 + 迁移
- [ ] 单测绿；全量回归绿
- [ ] 提交 `feat: 验证邮箱后默认启用邮箱 2FA 并迁移历史用户`

## Task 3 — 至少保留一种 2FA + 管理端重置恢复默认

- Modify `backend/app/api/routes/twofa.py`：`disable_email_otp` 在 TOTP 未开启时 400；`totp_disable` 在邮箱 2FA 未开启时 400（文案「至少保留一种二次验证方式，请先开启 TOTP 认证器」/通用）
- Modify `backend/app/api/routes/admin_users.py`：`reset_twofa` 置 `email_otp_enabled=True`、清 TOTP 与恢复码、吊销会话
- Test：重写 `backend/tests/test_twofa_settings.py` 的开关用例（先 TOTP 才能关邮箱、先邮箱才能关 TOTP、共存时均可关）；更新 `backend/tests/test_rate_limit_and_audit.py` 与 `backend/tests/test_admin_users_management.py` 的 reset-2fa 断言；`test_force_2fa.py` 补「关最后一种被拒」

Checklist：

- [ ] 改测试确认红
- [ ] 实现两处路由改动
- [ ] 单测绿；全量回归绿
- [ ] 提交 `feat: 强制至少保留一种 2FA，管理端重置恢复默认邮箱方案`

## Task 4 — 前端安全设置与验证页提示

- Modify `frontend/src/pages/DashboardPage.tsx`：邮箱 2FA 开启文案「已开启（默认方案）」；「关闭」按钮在另一种方案未开启时禁用并显示说明；TOTP 关闭按钮同理
- Modify `frontend/src/pages/VerifyEmailPage.tsx`：验证成功提示追加「已默认开启邮箱二次验证，登录时需要输入邮箱验证码」
- Test：更新 `DashboardTwofa.test.tsx`（禁用态断言）；`VerifyEmailPage` 现有测试视需要微调

Checklist：

- [ ] 写/改测试确认红
- [ ] 实现 UI
- [ ] `npx tsc -b && npm run lint && npm test` 绿
- [ ] 提交 `feat: 前端强制 2FA 状态展示与验证页提示`

## Task 5 — 文档、CHANGELOG 与全量验证

- Modify `CHANGELOG.md`：破坏性变更（登录强制 2FA）+ 功能 + 安全加固
- Modify `docs/deployment.md`：登录/2FA 行为说明与迁移提示
- Modify `README.md`：功能特性补充强制 2FA

Checklist：

- [ ] 后端全量 pytest 绿
- [ ] 真实 PostgreSQL：`alembic upgrade head → downgrade -1 → upgrade head` 往返，并抽查迁移后 `email_otp_enabled` 数据
- [ ] 前端 `tsc -b && lint && test && build` 绿
- [ ] 依赖审计无新增（pip-audit/npm audit）
- [ ] 提交 `docs: 同步强制 2FA 文档与变更记录`

## 收尾

- 合并 `codex/mandatory-2fa` 回 `main`（保留 merge 记录）
