# superpowers 工作流目录

本目录承载项目「设计先行 + 计划拆解」的协作文档。文档合并后长期保留，作为历史决策记录。

## Spec（设计规格）

- 路径：`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- 何时写：跨前后端、涉及对外契约（API/OIDC/数据库迁移）、安全、UI 视觉等非平凡改动
- 必含：目标、现状与约束、方案与取舍、接口/数据模型变更、安全影响、UI 设计（引用 design-system）、验收标准、风险
- 作用：先对齐「做什么、为什么」，再写实施计划

## Plan（实施计划）

- 路径：`docs/superpowers/plans/YYYY-MM-DD-<topic>.md`
- 何时写：需要多步实现时；小型改动可只写 spec 或直接实现
- 必含：Goal / Architecture / Tech Stack / Global Constraints，随后按 Task N 拆分
- 每个 Task：精确文件清单（Create/Modify/Test）、接口（Consumes/Produces）、checkbox 步骤
- 铁律：面向零上下文工程师，无 TBD/TODO 占位；每 Task 可独立验证；步骤遵循 TDD（红→绿→提交）

## 执行

- 隔离工作区：`git worktree add .worktrees/<topic> -b codex/<topic>`（`.worktrees/` 已 gitignore）
- 逐 Task 执行，每个 Task 一个独立提交
- 多任务可派子 agent：每 Task 一个实现 agent + 两段评审（superpowers:subagent-driven-development）
- 完工后按 [AGENTS.md](../../AGENTS.md) 第六节做全量验证与收尾

## 生命周期

- spec 与 plan 合并后不删除；后续推翻旧决策时在新 spec 中明确说明差异
- 文件名用 `YYYY-MM-DD` 前缀与 kebab-case topic，保证按时间排序
