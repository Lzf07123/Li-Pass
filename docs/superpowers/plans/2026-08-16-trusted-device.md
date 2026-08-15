# 实施计划：可信设备 7 天免登录二次验证（仅登录时）

日期：2026-08-16
设计：`../specs/2026-08-16-trusted-device-design.md`

## Goal

登录完成 2FA 时可显式授权「信任此设备」，7 天内同设备密码登录跳过登录 2FA；豁免仅限登录环节，敏感操作复核不受影响；支持用户侧查看与撤销，并在改密码/退出所有设备时全量撤销。

## Architecture / Tech Stack / Global Constraints

- FastAPI + SQLAlchemy 2.0 + Alembic + Redis（限流）/ 内存（测试）；前端 React + TypeScript。
- 硬性规则：不改动 step-up 体系；秘密不入库（token 只存 SHA-256）；数据库变更必须 Alembic 迁移且 PostgreSQL 往返验证；命名技术标识统一 `lipass`。
- TDD：每个 Task 先红后绿再独立提交。

## Task 1：模型与迁移

**Create/Modify/Test**

- Create `backend/app/models/trusted_device.py`：`TrustedDevice` 模型。
- Modify `backend/app/models/__init__.py`：导出。
- Create `backend/alembic/versions/<rev>_add_trusted_devices.py`（down_revision=`a2b3c4d5e6f7`；FK 命名、DateTime(timezone=True)）。
- Create `backend/tests/test_trusted_device_model.py`：创建/过期/撤销字段与唯一约束。

- [ ] 写模型与迁移，SQLite 测试夹具跑通
- [ ] `alembic upgrade head && downgrade -1` 本地往返
- [ ] 提交 `feat: 新增可信设备模型与迁移`

## Task 2：可信设备服务

**Create/Modify/Test**

- Create `backend/app/services/trusted_devices.py`：`TRUSTED_DEVICE_COOKIE`、`grant()`、`find_valid()`、`revoke_one()`、`revoke_all()`、`set_cookie()/clear_cookie()`、序列化。
- Modify `backend/app/core/config.py`：`trusted_device_ttl_days: int = 7` 与校验。
- Create `backend/tests/test_trusted_device_service.py`：授予/校验/过期/撤销/刷新 last_used_at。

- [ ] 服务 TDD 红→绿
- [ ] 提交 `feat: 可信设备授予/校验/撤销服务`

## Task 3：登录豁免与授予

**Create/Modify/Test**

- Modify `backend/app/schemas/auth.py`：`TwoFaVerifyRequest` 增 `trust_device`。
- Modify `backend/app/api/routes/auth.py`：login 在创建 2FA 挑战前校验可信 Cookie（命中 → 建会话 + `2fa_trusted_skip` 审计 + 返回用户）；2fa/verify 成功后按 `trust_device` 授予并种 Cookie + `trusted_device_granted` 审计。
- Modify `backend/tests/test_twofa_login.py` / 新测试：勾选信任后二次登录跳过 2FA；密码错误仍拒绝；不勾选仍要求 2FA。

- [ ] 后端测试红→绿
- [ ] 提交 `feat: 登录时可信设备豁免 2FA 与授予`

## Task 4：查看/撤销与联动撤销

**Create/Modify/Test**

- Modify `backend/app/api/routes/users.py`：`GET/DELETE /api/v1/me/trusted-devices[/{id}]`；改密码撤销全部；revoke-all 撤销全部。
- Modify `backend/app/api/routes/auth.py`（如需）：logout 不撤销（可信设备跨会话保留，设计如此）。
- Modify `backend/tests/test_user_center.py` / 新测试：列表、撤销单台、撤销当前清 Cookie、改密码/revoke-all 全量撤销。

- [ ] 测试红→绿
- [ ] 提交 `feat: 可信设备列表/撤销与改密码、退出所有设备联动`

## Task 5：前端

**Create/Modify/Test**

- Modify `frontend/src/api/client.ts`：`TwoFaVerifyRequest` 扩展、`trustedDevicesApi`。
- Modify `frontend/src/pages/LoginPage.tsx`：2FA 复选框「信任此设备：7 天内登录免二次验证」。
- Modify `frontend/src/pages/DashboardPage.tsx`：可信设备卡片（列表/撤销/当前标记）。
- Modify `frontend/src/__tests__/LoginPage.test.tsx`、`DashboardPage.test.tsx`。

- [ ] 前端测试红→绿
- [ ] 提交 `feat: 前端信任设备选项与可信设备管理`

## Task 6：文档与变更记录

**Create/Modify/Test**

- Modify `.env.example`、`backend/.env.example`、`docs/deployment.md`：`TRUSTED_DEVICE_TTL_DAYS`。
- Modify `CHANGELOG.md`：功能 + 行为变更。

- [ ] 提交 `docs: 同步可信设备配置文档与变更记录`

## 全量验证（收尾前）

```bash
cd backend && .venv/bin/python -m pytest -q
cd frontend && npx tsc -b && npm run lint && npm test && npm run build
```
