# 站点设置 IP 库后台更新与实时进度设计

## 背景

站点设置「IP 归属地库」的「立即检查更新」目前是同步阻塞接口：管理员点击后要等约 48MB 数据下载完成才返回，无进度反馈，离开页面后也无法感知结果。

## 目标

改为后台任务 + 状态轮询：请求立即返回，下载在服务端后台继续；前端实时显示阶段与字节级进度；离开页面再回来仍能看到进行中/完成/失败状态。

## 方案

### 进度状态

- 新增 `app/services/ip2region_progress.py`：单槽位进度存储，memory/redis 双后端（沿用项目 store 惯例；生产 `RATE_LIMITER=redis` 时用 Redis，否则进程内字典——内存模式文档规定单 worker）。状态键带 1 小时 TTL。
- 状态结构：`{state: idle|running|success|error, stage: idle|checking|downloading_v4|downloading_v6|installing, downloaded_bytes, total_bytes, percent, version, changed, message, started_at, finished_at}`。

### 任务执行

- `POST /api/v1/admin/settings/ip2region/update` 改为 async 端点：限流校验后，若已有任务在跑返回 409（附固定文案，前端随即轮询状态）；否则 `asyncio.create_task(asyncio.to_thread(...))` 启动后台任务并返回 202 + 状态快照。
- 后台任务使用**独立 DB 会话**（通过 `request.app.dependency_overrides.get(get_db, get_db)` 取得工厂，测试可注入内存 SQLite），不复用请求会话。
- `update_ip2region` 增加可选 `on_progress(stage, downloaded, total)` 回调；`_download_to` 按 64KB 块流式读取并回调（Content-Length 提供 total）。阶段：checking → downloading_v4 → downloading_v6 → installing → success/error。
- 冲突/互斥沿用既有跨进程文件锁；自动更新（每小时调度）不并入进度面板。

### 接口

- `POST /settings/ip2region/update` → 202 `{started: true, status}`；进行中 409。
- `GET /settings/ip2region/update/status` → 状态快照（idle 时为初始态）。
- 两者均受管理员鉴权与既有限流保护。

### 前端

- `AdminSettingsPanel`：点击后按钮置为「后台下载中…」并禁用，显示进度条与阶段文案，每秒轮询状态；打开面板时先查一次状态，若进行中自动恢复轮询；成功刷新库状态并 Toast，失败展示 message。

## 测试

- 后端：memory 存储读写与过期；POST 返回 202 且后台最终 success；进度回调推进时状态反映百分比；运行中重复提交 409；鉴权 401/403。
- 前端：点击后轮询并显示进度；完成后刷新与成功提示；失败提示。

## 非目标

- 不支持取消/断点续传；自动更新不进入进度面板。
