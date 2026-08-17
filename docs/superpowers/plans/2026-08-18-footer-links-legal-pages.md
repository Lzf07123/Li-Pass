# 实施计划：页脚丰富化与法律页面

Goal：页脚新增 GitHub/反馈/联系/法律链接（变量置空自动隐藏），并新增 `/privacy`、`/terms` 静态页面。

Architecture：React 前端改动，无后端变更。品牌配置在 `frontend/src/lib/brand.*`，页脚在 `frontend/src/components/SiteFooter.tsx`，路由在 `frontend/src/App.tsx`。

Tech Stack：React 19 + TypeScript + Vite + Tailwind CSS 4 + React Router 7 + Vitest。

Global Constraints：
- 变量填写才显示、置空隐藏。
- 外部链接 `target="_blank" rel="noreferrer"`；内部路径用 `Link`。
- 遵循 BRAND.md 页脚规范；不新增依赖。
- 每个 Task 独立提交，提交信息 `<type>: <中文简述>`。

## Task 1：品牌变量与示例配置

Files：
- Modify `frontend/src/lib/brand.example.ts`
- Modify `frontend/src/lib/brand.ts`（本地 gitignored 副本）
- Modify `frontend/.env.example`

Consumes：现有 `envString` 工具。
Produces：`GITHUB_URL`、`GITHUB_ISSUES_URL`、`CONTACT_EMAIL` 导出；`FOOTER_LINKS` 默认隐私政策/服务条款。

Checkbox：
- [ ] `brand.example.ts` 增加三个变量并注释空值隐藏行为
- [ ] `FOOTER_LINKS` 默认包含 `/privacy` 与 `/terms`
- [ ] `brand.ts` 同步修改
- [ ] `.env.example` 增加对应注释示例
- [ ] 提交 `feat: 品牌配置新增页脚仓库/联系与法律链接变量`

## Task 2：页脚组件与测试

Files：
- Modify `frontend/src/components/SiteFooter.tsx`
- Modify `frontend/src/__tests__/SiteFooter.test.tsx`
- Modify `frontend/src/__tests__/SiteFooterConfigured.test.tsx`

Consumes：`GITHUB_URL`、`GITHUB_ISSUES_URL`、`CONTACT_EMAIL`、`FOOTER_LINKS`、备案变量。
Produces：完整版/紧凑版页脚渲染；空值隐藏逻辑。

Checkbox：
- [ ] 完整页脚渲染链接导航行与版权/备案行
- [ ] 紧凑页脚保留版权 + 备案 + 附加链接 + GitHub 图标
- [ ] 任一变量为空时对应链接不渲染
- [ ] 测试覆盖 GitHub/反馈/联系/内部链接与空值隐藏
- [ ] `npm test -- SiteFooter` 通过
- [ ] 提交 `feat: 页脚新增 GitHub 仓库、反馈、联系与法律链接`

## Task 3：法律页面与路由

Files：
- Add `frontend/src/pages/LegalPage.tsx`
- Modify `frontend/src/App.tsx`
- Add `frontend/src/__tests__/LegalPage.test.tsx`

Consumes：`CONTACT_EMAIL`、`APP_NAME`、`APP_TAGLINE`；`AppHeader`、`SiteFooter`、`FloatingBackground`。
Produces：`/privacy`、`/terms` 路由与可渲染页面。

Checkbox：
- [ ] `LegalPage` 按 kind 渲染隐私/条款章节
- [ ] 路由注册 `/privacy`、`/terms`，加入公共页面集合
- [ ] 页面无需登录即可访问，正文含联系邮箱
- [ ] 测试覆盖两个页面标题与关键章节
- [ ] `npm test -- LegalPage` 通过
- [ ] 提交 `feat: 新增隐私政策与服务条款页面`

## Task 4：文档收尾与全量验证

Files：
- Modify `docs/deployment.md`（环境变量表）
- Modify `CHANGELOG.md`（未发布「功能」分区）

Checkbox：
- [ ] deployment.md 补充 `VITE_GITHUB_URL` / `VITE_GITHUB_ISSUES_URL` / `VITE_CONTACT_EMAIL` / `VITE_FOOTER_LINKS` 说明
- [ ] CHANGELOG 增加页脚与法律页面条目
- [ ] 全量验证：`npx tsc -b && npm run lint && npm test && npm run build`
- [ ] 提交 `docs: 同步页脚与法律页面部署说明`
