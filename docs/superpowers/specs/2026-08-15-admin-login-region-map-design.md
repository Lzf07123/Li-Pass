# 管理后台登录来源地域分布地图设计

## 背景

数据统计页的「登录来源地域分布」目前是 Top 10 条形列表。改为中国地图省级着色（choropleth），更直观地呈现登录来源的空间分布。

## 目标

用中国地图展示窗口内登录次数按省级行政区的分布；海外/内网/未知等非省级数据以徽章汇总，明细以表格兜底（可访问性）。

## 方案

### 后端

- `geoip.locate_ip(ip) -> (GeoIpResult | None, label | None)`：公共 IP 且库就绪时返回 country/province，否则给出分类标签（内网/保留/未知）。
- `admin_stats` 新增聚合：
  - `regions_map`：中国省级全名 → 登录次数（全量，含「内蒙古自治区/香港特别行政区」等别名规范化，限定 34 个省级行政区集合，未识别省份归「未知」）。
  - `regions_other`：`{overseas, internal, unknown}`——海外国家聚合为 overseas，内网+保留为 internal，未知为 unknown。
  - IP 库未安装时两者返回空/零。
- 保留现有 `regions`（Top 10 展示串）不破坏既有测试。

### 前端

- 静态资产 `src/assets/maps/china.json`（省级 GeoJSON，入库离线、随构建打包，来源阿里 DataV GeoAtlas）。
- 新组件 `ChinaMap.tsx`（自研 SVG，无新依赖，与 LineChart 风格一致）：
  - 等距投影适配 viewBox；5 档单色渐变（`--portal-primary`，暗色自适应）+ 色阶图例；零值省份中性色。
  - 悬停高亮省份并显示「省名 · 次数 · 占比」；SVG `<title>` 原生提示兜底。
  - 地图下方「海外/内网/其它」徽章 + 可读明细表（按次数排序，含占比），兼顾移动端与可访问性。
- `AdminStatsPanel` 的地域分布块替换为地图 + 徽章 + 明细表。

## 测试

- 后端：monkeypatch geoip 解析器，断言省份计数与别名规范化、海外/内网/未知汇总、未安装时为空。
- 前端：ChinaMap 渲染省份与零值中性色、悬停提示、徽章与明细表；AdminStatsPanel 集成测试更新。

## 非目标

- 不做世界地图；不做缩放/平移；不引入 echarts/D3 等依赖。
