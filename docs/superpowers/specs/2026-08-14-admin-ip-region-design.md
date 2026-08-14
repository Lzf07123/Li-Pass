# 管理后台 IP 归属地展示、统计与库更新设计

- 日期：2026-08-14
- 状态：已实施完成（2026-08-14）
- 范围：管理后台会话监控与审计日志展示 IP 归属地；数据统计新增登录来源地域分布；站点设置新增 IP 库（ip2region）手动/定期自动更新

## 1. 目标

1. 在「会话监控」「审计日志」中，把裸 IP 提升为「IP + 归属地」（中国显示省/市，海外显示国家）。
2. 「数据统计」新增登录来源地域分布（Top 10 + 其它），用横向条可视化。
3. 「站点设置」新增「IP 归属地库」卡片：展示当前版本与数据日期、IPv4/IPv6 加载状态，支持「立即检查更新」手动更新，以及可开关的定期自动更新。

全部基于离线库 `ip2region`，查询不依赖外网；只有「更新」动作才会访问网络。

## 2. 数据源选型

采用 [ip2region](https://github.com/lionsoul2014/ip2region) v3.17.0（Apache-2.0）：

- 两份 xdb：`ip2region_v4.xdb`（约 11MB）、`ip2region_v6.xdb`（约 37MB），合并支持 IPv4/IPv6，精确到城市。
- 官方 Python 绑定（`binding/python/ip2region/{__init__,searcher,util}.py`）锁定 v3.17.0 源码入仓库 `backend/ip2region/`，不新增 pip 依赖。
- `content buffer` 模式单次查询实测约 10µs；两个库常驻内存约 48MB/进程（单 worker 部署，容器内存上限 768MB 有裕量）。
- 字段格式：`国家|省份|城市|ISP|iso-alpha2`，中国的国家/省/市为中文，海外为英文；空值用 `0` 或空串。

对比方案：MaxMind GeoLite2 需要账号与密钥、禁止再分发、中国省市级粒度弱；在线 API（如 ip-api.com）有配额与商用限制，且会把用户 IP 发给第三方。均不采用。

## 3. 后端设计

### 3.1 归属地解析服务 `services/geoip.py`

- 懒加载单例 `GeoIpResolver`：首次解析时用 `new_with_buffer` 把两份 xdb 读入内存；每次解析前 `os.stat` 对比 (mtime, size)，文件被替换后自动重载（支持多 worker 共享文件系统与热更新）。
- 分类优先于查询：`ipaddress` 判定 `private/loopback/link_local/unspecified` → `内网地址`；`multicast/reserved` → `保留地址`；IPv4-mapped IPv6 归一化为 IPv4 后处理。
- 展示规则：国家为「中国」时拼接「省份 城市」（空段跳过，兜底「中国」）；海外显示国家；无法解析显示「未知」；xdb 缺失返回 `None`（前端显示 `—`）。不展示 ISP。
- 对无效 IP、xdb 缺失均不抛异常，静默降级为 `None`。

### 3.2 接口扩展

| 方法 | 路径 | 变更 |
| --- | --- | --- |
| `GET` | `/api/v1/admin/sessions` | 每个会话项新增 `ip_location: string\|null` |
| `GET` | `/api/v1/admin/audit-logs` | 每条记录新增 `ip_location: string\|null` |
| `GET` | `/api/v1/admin/stats` | 响应新增 `regions: [{region, count}]` |
| `GET` | `/api/v1/admin/settings` | 新增 `ip2region` 状态对象 |
| `PUT` | `/api/v1/admin/settings` | 可选新增 `ip2region_auto_update_enabled`、`ip2region_update_interval_hours` |
| `POST` | `/api/v1/admin/settings/ip2region/update` | 立即检查并更新 IP 库 |

- 权限：全部沿用路由级 `get_current_admin`。
- `regions` 口径：统计窗口（7/30/90 天）内成功登录（`action IN ('login','2fa_login')`）的 IP 按 `GROUP BY ip` 去重聚合后逐一解析，按归属地计数，取 Top 10 降序，其余合并为「其它」；IP 库未安装时返回空数组（前端显示「暂无数据」）。归属地解析失败计入「未知」。
- `ip2region` 状态对象：`{version, data_updated_at, v4_ready, v6_ready, auto_update_enabled, update_interval_hours}`。

### 3.3 更新服务 `services/ip2region_update.py`

- 版本发现：`GET ip2region_releases_api_url`（默认 GitHub `releases/latest`，取 `tag_name`）；下载：`{ip2region_download_base_url}/{tag}/data/ip2region_v{4,6}.xdb`（默认 raw.githubusercontent.com）。两个地址均可配置镜像（如 Gitee）。
- 更新流程：下载到 `data/ip2region/.tmp-update/` → SHA256 信任清单校验（仅清单内版本可安装）→ `util.verify_from_file` 校验结构 + 校验文件头 `ipVersion`（v4=4、v6=6）→ 旧库先移 `.bak` 再原子替换、失败回滚 → 写 `meta.json`（版本、数据时间戳、sha256、检查时间）→ 触发解析器重载。任何一步失败都保留旧库。
- 结果：`{version, data_updated_at, changed}`；已是最新时 `changed=false` 且不下载。
- 并发：数据目录上的跨进程文件锁（fcntl）互斥手动/自动更新；替换用 `os.replace`，多 worker 靠解析器的 stat 检测自动重载。
- 手动更新限流：按管理员维度，默认 6 次/小时；超限 429。更新成功记审计（`admin_update_ip2region`）。
- 自动更新：`main.py` lifespan 增加后台任务，每小时醒来一次；读取站点设置 `ip2region_auto_update_enabled`（默认 false）与 `ip2region_update_interval_hours`（默认 24），距上次检查超过间隔才执行；失败仅记日志。

### 3.4 配置（`core/config.py`）

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `IP2REGION_DATA_DIR` | `data/ip2region`（生产必须绝对路径） | xdb 与 meta.json 目录 |
| `IP2REGION_RELEASES_API_URL` | GitHub releases/latest | 版本发现 API |
| `IP2REGION_DOWNLOAD_BASE_URL` | GitHub raw 根地址 | xdb 下载基地址 |
| `IP2REGION_HTTP_TIMEOUT_SECONDS` | 30 | 下载/检查超时 |
| `IP2REGION_AUTO_UPDATE_ENABLED` | false | 自动更新默认开关（可被站点设置覆盖） |
| `IP2REGION_UPDATE_INTERVAL_HOURS` | 24 | 自动检查间隔（1–8760） |
| `IP2REGION_UPDATE_RATE_LIMIT` / `..._WINDOW_SECONDS` | 6 / 3600 | 手动更新限流 |

### 3.5 构建与本地开发

- xdb 为 48MB 二进制，不入 git；`.gitignore` 增加 `backend/data/`。
- `backend/scripts/download_ip2region.py`（纯标准库）：按 tag 从下载基地址拉取两份 xdb，v3.17.0 做 SHA256 强校验（`v4=6307a969…`、`v6=5b93da35…`），写入 meta.json；Docker 构建与本地开发共用同一脚本。
- `backend/Dockerfile`：`RUN python scripts/download_ip2region.py && chown -R 10001:10001 /app/data`，把初始数据烧进镜像；运行时更新写回镜像层，容器重建后由自动/手动更新或重建时下载恢复。

## 4. 前端设计

- 会话监控：IP 单元格在 IP 下方用 `text-xs text-muted` 显示归属地。
- 审计日志：IP 列同样追加归属地。
- 数据统计：新增「登录来源地域分布（近 N 天）」卡片，Top 10 横向条（复用认证方式分布条的样式：标签 + 归一化色条 + 数量），`其它` 兜底；空数组时显示「暂无数据」。
- 站点设置：新增「IP 归属地库」卡片——版本与数据日期、IPv4/IPv6 加载状态、「自动更新」开关、「检查间隔」下拉（12/24/72/168 小时）、「立即检查更新」按钮（AsyncButton，成功提示「已更新到 vX」或「已是最新版本」）。
- 视觉沿用现有令牌（`bg-primary`、`text-muted`、`card` 等），深色模式自适应，无新增依赖与动画。

## 5. 测试

- 后端：`format_region`/IP 分类纯函数；`GeoIpResolver` 用假解析器注入的降级路径；会话/审计响应含 `ip_location`；`regions` Top 10 + 「其它」聚合与未安装时返回空；设置 GET/PUT 扩展字段；手动更新端点（monkeypatch 抓取/下载的编排、401/403/429、审计）；`meta.json` 读写；`get_site_setting_int`。
- 前端：会话/审计/统计面板渲染归属地与地域条；设置面板渲染状态、切换自动更新/间隔触发 PUT、点击更新触发 POST 与 Toast、失败提示。

## 6. 安全与运维

- 解析完全离线，零外发；仅管理员触发的更新动作访问 GitHub（可配镜像）。
- 下载内容在替换前做 SHA256 信任清单校验（运行期与构建期同一清单）+ 结构校验 + 文件头 IP 版本校验；更新动作记审计并限流。
- 无数据库迁移；`regions` 聚合先 `GROUP BY ip` 再解析，最多解析窗口内去重后的 IP 数。
- 内存口径：xdb 常驻约 48MB/进程；若未来提高 `UVICORN_WORKERS`，需同步评估容器内存上限。

## 7. 明确假设

- 归属地展示只显示「中国=省份+城市、海外=国家」，不显示 ISP；如需 ISP 可后续加。
- 仅会话监控、审计日志、数据统计三个视图展示归属地；用户管理页暂不加。
- 自动更新默认关闭；更新源默认 GitHub，被墙环境通过环境变量切换 Gitee 镜像。
