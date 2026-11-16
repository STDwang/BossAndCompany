---
name: boss-and-company
description: 将用户的 GitHub 初始化为个人公司，整理老板档案、公司空间与岗位，创建并部署个人网站，复用主页及项目，为后续项目写入默认协作和留痕规则。接入 GitHub 后按用户开关自动同步 Boss 与公司空间最新状态，提交后按开关维护公司空间记录，并生成严格公开的“最近在忙”数据。适用于“对我的 GitHub 使用 BossAndCompany”、公司初始化、项目登记、汇报、多 Harness 共处、自动化开关和跨 AI 交接。
version: 4
agent_created: true
---

# BossAndCompany

支持 Codex、Claude Code、WorkBuddy 和有适当工具的 DeepSeek 宿主。共用资料、流程和事件格式，按宿主加载规则。先读 [平台适配](references/platforms.md) 中当前环境对应部分；没有终端/文件/GitHub 工具时输出可交接材料和能力缺口，不假装执行远端操作。

## 模式

- 用户首次说“对我的 GitHub 使用这个 skill”：读取 [初始化流程](references/initialization.md)，完成已有仓库检查、资料归档、主页和网站发布、项目规则绑定。
- 已初始化项目工作：先按 [主动性开关](references/automation.md) 运行 `auto.py session-start` 读取最新私有缓存与 `CONTEXT.md`，再读取项目规则与 `.boss-and-company/company.json`，按 [留痕协议](references/work-protocol.md) 登记、交接、汇报和补传。
- 更新主动性开关 / 配置自动同步：读取 [主动性开关](references/automation.md) 与 [hooks 说明](assets/hooks/README.md)；开关放在 private Boss 档案，任何写入都需用户明确开启。
- 更新老板信息/导入简历：读取 [资料规则](references/passport.md)，保留来源并合并事实；没有独立简历仓库。
- 更新展示/部署网站：读取 [展示与部署](references/publishing.md)，优先复用现有工程、设计和托管。"最近在忙"只消费 `activity.json` 白名单投影，不直接读取 private 公司空间。

本 skill 的开发、安装与实际 GitHub 初始化是不同动作。用户要求制作 skill 时仅开发本地文件。初始化请求已授权执行其所涵盖的常规创建、归档、规则绑定及部署；已有主页覆盖和网站复用按下面两问处理，不重复增加审批步骤。敏感资料读取与公开发布分开，公开内容只使用已允许公开的字段。

## 公司结构

| 仓库 | 内容 | 初始可见性 |
| --- | --- | --- |
| `<owner>/<owner>` | 主页 README 与公开成果入口 | public |
| 独立网站仓库或复用现有网站仓库 | 个人介绍、成果详情和部署配置 | public |
| `Boss_Passport` | 经历、偏好、近期目标、愿望、约束及来源 | private |
| `Company_Workspace` | 公司协议、项目索引、工作区登记、岗位、任务快照、独立工作事件 | private |
| 实际项目仓库 | 代码、策划、美术、验证及正式项目决定 | 新建 private；已有仓库保留原可见性 |

已有职责相同的仓库可经内容核实后映射复用，不重建副本或擅自改名。岗位为 `positions/Coder_Position`、`Art_Position`、`Planning_Position`，允许以后复制结构新增岗位。岗位记录引用正式产物，项目状态只有一份权威快照；不能让几个岗位分别维护互相矛盾的进度。

## 多 Harness 身份模型

项目身份始终是唯一 `owner/repo`。同一 GitHub 仓库可被多个本地 checkout 和多个 AI Harness 使用，也可由多个 Harness 共用一个本地目录；这些都只增加独立的工作区登记和事件，绝不复制 `PROJECT.json` 或 `STATE.md`。

- `.boss-and-company/company.json` 是仓库级确定性文件，在所有 checkout 中必须一致，不含本地路径、workspace_id 或 Harness 专属状态。
- gitignored 的 `.boss-and-company/local.json` 属于当前 checkout，保存 `workspace_id`、本地路径和 private 仓库映射。工作区身份由本地路径派生，目录移动时可用 `bind --workspace-id` 沿用。
- 事件必须带 `workspace_id` 与 `harness`；ID 以 `workspace_id` 为前缀。同一 checkout 被不同 Harness 使用时，工作区身份相同但 harness 与事件 ID 不同。
- 每个 checkout 用 `company.py workspace` 生成不含绝对路径的不可变登记，由 `sync.py` 上传至 `workspaces/<workspace_id>.json`；事件仍上传至独立的 `events/<id>.json`。
- 各 Harness 只追加不可变文件；唯一 `STATE.md` 由明确协调者读取远端 SHA 后合并。没有协调者时不并发改状态快照。不同技能版本绑定同一仓库时先解决 `skill_version` 冲突。

## 主动性开关与自动同步

详细规则见 [主动性开关](references/automation.md)。**Skill 被动加载，不会后台自跑**；触发来自宿主 SessionStart hook、git post-commit hook，或 skill 被加载时按项目规则执行统一入口 `scripts/auto.py`。触发本身不等于授权写入。

- 用户级权威开关在 private `Boss_Passport/automation.json`，所有 Harness 读同一份；本 checkout 的 gitignored `local.json` 只能把开关**调得更保守**，不能提权。远端文件缺失时回退默认值，不回退成全开。
- 当前默认（用户选择）：`auto_refresh=true`（只读拉取 Boss 与公司空间最新信息）、`auto_record=false`、`sync_after_record=false`、`activity_public=false`。用 `auto.py status` 查看生效值。
- 会话开始：只读刷新到 gitignored `.boss-and-company/cache/`，生成给接手 Agent 先读的 `CONTEXT.md`；缓存带远端 SHA，失败保留旧缓存并标 `stale`，**不写远端、不阻断会话、不伪称已同步**。
- 提交后：按开关把最近一次 commit 记成 private 事件（ID 与 commit 绑定，重放幂等；只含元数据，验证状态明确 `not-run`）；默认只落本地 outbox，需 `sync_after_record` 才上传并远端回读，且只同步本次事件。
- "最近在忙"投影：只有 `activity_public` 开启、事件显式 `visibility: public` 且项目在规范化档案中为 public/verified 时才生成；输出严格白名单字段并做自检。**脚本必须显式 `--output`，绝不自动写网站仓库或改现有页面。**
- 版本说明：本 skill 包为 `version: 4`；仓库绑定数据 `company.json` / `local.json` 的 `skill_version` 仍为 `2`（基础格式未变，已绑定项目无需重新 bind）。`automation_version: 1` 只管开关文件；`classification_version: 1` 只管 `PROJECT.json` 里可选的项目分类对象。
- 项目分类（v4 新增）：协调者可经只读 GitHub 元数据为 `PROJECT.json` 追加可选的 `classification` 对象，字段由 `scripts/classification.py` 定义并校验，含网站展示形态（`public-source`/`source-private`/`none`）、是否 fork、活跃度分层、星数与最近推送时间。分类是独立可选层，基础 `schema_version` 不变；公开投影仍只输出原本的白名单字段，分类信息只留在 private 公司空间。主页 public 项目排序规则：星数降序、同星数按最近推送时间降序。

## 首次初始化主要两问

仅检测到相应已有内容且无已保存决定时询问，可一次呈现：

1. “检测到已有 GitHub 主页 README，是否使用 BossAndCompany 重新生成并覆盖？”默认保留；覆盖前保存原版（受控备份与已有 Git 历史），新内容确认无私密字段后再写。
2. “检测到已有个人网站，是否复用现有网站及部署？”默认复用；选不复用时另建仓库/站点并保留原站。

未收到答案不视为同意，相关写入等待，其他不依赖选择的整理继续。保存决定和仓库映射，后续沿用，用户明确改意时更新。除此之外只问实质缺少的信息，如账号、项目范围、多个站点无法判定、权限障碍；不要逐库重复问是否复用。

## 默认协作与真实性

初始化后为用户选定项目写入 `AGENTS.md`、`CLAUDE.md`、`.codebuddy/CODEBUDDY.md` 和显式 DeepSeek 上下文入口，增量维护专属区块，保留原文件。公司规则不会高于用户最新指令和宿主权限。支持宿主的项目级 skill 安装，不能承诺任意模型或未加载上下文的会话都会自动执行。

不记录每次工具调用。登记、关键决定、交接、阻塞、阶段完成时追加带 `schema_version: 2`、`workspace_id`、`harness` 和时区时间的独立事件；事件 ID 必须以 workspace_id 为前缀。私有仓库映射、本地路径和 checkout 身份只存项目内 gitignored 的 `.boss-and-company/local.json`，不得写入公开项目内容。执行者分别记录，由本次协调者使用远端 SHA 更新唯一任务快照；无需为了留痕自动启动额外 agent。验证必须区分未运行、局部检查、实测通过与人类验收。离线事件保留待同步状态，确认 GitHub 文件已回读一致后才能标为 synced。远端工作区登记与事件同步使用 `sync.py`；单独调用 acknowledge 仍只代表调用方确认回读。

## 工具与验收

`scripts/company.py` 提供 plan/scaffold/bind/workspace/event/acknowledge；`scripts/render.py` 提供仅显式公开字段的展示生成；`scripts/classification.py` 定义并校验可选的项目分类对象（含排序键）；`scripts/history_index.py` 只筛选 Codex 会话元数据；`scripts/sync.py` 在已登录 gh 可用时完成工作区登记、事件上传、远端回读与回执。自动化部分：`scripts/automation.py` 解析用户级开关，`scripts/refresh.py` 只读拉取并生成私有上下文，`scripts/activity.py` 生成严格白名单的公开活动投影，`scripts/auto.py` 是 session-start/post-commit/activity/status 的统一入口；`scripts/sync.py` 的 `only` 参数保证提交同步不波及其它 pending 事件。plan 必须同时读取 config、inventory 和规范化的 profile 项目登记表；配置、盘点、档案、事件、开关与活动投影均为 `schema_version: 2`。格式见 [配置示例](assets/examples/config.json)、[盘点示例](assets/examples/inventory.json)、[档案示例](assets/examples/profile.json)、[事件示例](assets/examples/event.json)、[开关示例](assets/examples/automation.json) 和 [活动投影示例](assets/examples/activity.json)。全部是虚构数据。

远端优先已连接 GitHub 工具，不足时用已登录 gh；不自动变更认证。新库可见性显式指定；私有档案写入前核实目标 private；读取当前 SHA、合并再更新，禁止强推。部分成功记录准确检查点，重跑应补齐而非重复创建。凭证不进配置/日志。完成报告包含实际仓库 URL、网站部署 URL、规则覆盖范围、待同步事件及未完成项；仅生成文件不算已部署。
