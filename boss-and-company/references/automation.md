# 主动性开关与自动同步

## 目标

让安装了本 skill 的任意 Harness 在接入 GitHub 项目后，拿到同一份最新的 Boss 档案与公司空间状态；并允许在代码提交后，把工作记录追加到 private 公司空间，供后续接手的 Agent 读取，也为将来个人网站的"最近在忙…"可视化模块准备数据。**主动性由用户开关决定，默认只读开、写入全关。**

## 能力边界（必须如实说明）

- Skill 是被动加载的知识和脚本，不会后台常驻。真正的自动触发只能来自宿主 SessionStart hook、git post-commit hook，或 skill 被加载时按项目规则执行 `auto.py`。[hooks 说明](../assets/hooks/README.md) 给出统一命令，不擅自改写任何宿主配置。
- 没有任何远端工具或离线时，`session-start` 保留旧缓存并标 `stale`；不假装同步成功。
- 自动记录只写 private 公司空间，不修改个人网站、不公开任何事件正文、不启动额外 agent。
- 网站"最近在忙"模块属于后期工作。本版只提供**可消费的数据契约与生成脚本**，不写网站仓库、不改现有页面。

## 用户级开关

权威文件：private `Boss_Passport/automation.json`。所有 Harness 读取同一份，用户改一次即全局生效。格式见 [示例](../assets/examples/automation.json)。

| 开关 | 默认 | 含义 |
| --- | --- | --- |
| `auto_refresh` | `true` | 会话开始只读拉取 Boss 档案 + Company_Workspace 最新状态到本 checkout 私有缓存 |
| `auto_record` | `false` | 代码提交后自动生成 private 事件并写入本地 outbox |
| `sync_after_record` | `false` | 提交事件生成后自动同步到 private 公司空间；`auto_record` 为 false 时强制 false |
| `activity_public` | `false` | 允许生成供网站消费的公开活动投影 |

解析规则：

- `automation_version` 与 `schema_version` 必须匹配，否则报版本冲突而不是静默套用默认值。
- 远端文件缺失 → 回退内置默认值（只读开、写入全关），绝不回退成"全开"。
- 每个 checkout 的 gitignored `local.json` 可有 `automation_override`，**只允许把 `true` 降为 `false`**；本地试图把用户关掉的开关打开会被记录为 `local_overrides_ignored` 并忽略。这样某个 Harness 可以临时更保守，但不能越权扩大写入。
- `auto.py status` 随时显示生效值、来源、本地覆盖与缓存新鲜度，不联网。

## 三个数据流

### 1. 会话开始（`session-start` → `refresh.py`）

只读 `gh api`，要求 Boss 与公司空间仓库均为 private；拉取 `automation.json`、`SUMMARY.md`、`company.json`、`README.md`、项目 `STATE.md` / `PROJECT.json`、最近事件与工作区登记索引，写入本 checkout 的 `.boss-and-company/cache/`（该路径由 bind 写入 .gitignore，`cache_guard` 会再次校验，旧绑定未保护时直接拒绝写缓存）。

同时生成 `CONTEXT.md`：项目身份、workspace_id、远端 SHA、项目状态摘要、近期事件、Boss 摘要和生效开关，供接手的 Agent **第一个读**。缓存是快照，不是权威状态；正式决定与验证仍以项目仓库和公司空间远端为准。

`snapshot.json` 记录 `refreshed_at`、`boss_sha`、`company_sha`、`stale`。刷新失败保留旧文件并置 `stale=true`，返回明确 `reason`。

### 2. 提交后（`post-commit` → `company.event`，可选 `sync.py`）

从本地 `git log -1` 读取 SHA、提交时间、主题首行、分支，生成一条 private 事件：

- ID 为 `{workspace_id}-commit-{sha前12位}`，`recorded_at` 取 commit 时间，因此**重放 hook 字节一致、不会重复造事件**；
- 含 `workspace_id`、`harness`、项目 `owner/repo`、摘要与明确的 `verification.status: not-run`（不伪造验证）；
- 只含元数据，**不含 diff、代码、作者邮箱、本地路径**；
- 默认只落本地 outbox，状态 `pending`；`sync_after_record` 开启时才调用 `sync.py --only <id>` 上传并远端回读，成功后写回执。只同步本次事件，不会顺带上传其它手动暂存的 pending 事件。

事件正文默认 `visibility: private`，公司空间仓库必须为 private，`sync.py` 会在写前核验。

### 3. 公开活动投影（`activity` → `activity.py`）

供后期"最近在忙…"模块消费，输出格式见 [示例](../assets/examples/activity.json)。一条事件进入投影需**同时**满足：

1. `activity_public` 开启；
2. 事件显式写 `visibility: "public"` 且带 `public: {title, stage}`（默认生成的提交事件没有，因此默认一条都不会出云）；
3. 事件所属项目在规范化 profile 中是 `visibility: public` 且 `status` 为 `verified` / `user-stated`。

输出字段是严格白名单：`date`、`project`（公开 `owner/repo`）、`title`（事件显式提供的公开短标题）、`stage`（`planning` / `in-progress` / `shipped` / `paused`）、`url`（该公开仓库的 HTTPS 地址）。生成后还会做一次自检：顶层与条目字段必须完全等于白名单，标题不得含联系方式、路径或提交哈希，URL 必须与项目匹配。

**绝不出云的内容**：事件 `summary`、`artifacts`、`actor`、`harness`、`workspace_id`、commit SHA、私有仓库名、本地路径、Boss 档案事实与任何凭证。脚本必须显式 `--output`，不自动挑选网站路径，也不自动部署。

## 多 Harness 一致性

- 项目身份仍是唯一 `owner/repo`；开关是**用户级**而不是 checkout 级，避免某个 Harness 悄悄给自己开权限。
- 缓存、outbox、receipts、`local.json` 都是每个 checkout 独立且 gitignored 的；远端公司空间只有唯一 `STATE.md` 和不可变事件文件，任何 Harness 都只追加，不并发改状态快照。
- 多个 Harness 同时提交会产生不同事件 ID（workspace_id 或 commit SHA 不同），不会互相覆盖；同 ID 不同内容会报冲突。
- 刷新缓存带远端 SHA，Agent 能判断自己读的是不是最新版本；冲突时由明确协调者按远端 SHA 合并状态。

## 验收

- 开关默认：只读开、三个写入类全关；缺失文件回退默认值；本地只能降权。
- `session-start` 全程无远端写；`status` 无网络请求；缓存目录必须 gitignored。
- 提交事件幂等、含 not-run 验证、默认 private 且默认只落本地；同步需回读一致才标 synced。
- `activity_public` 关闭时不写任何文件；开启时输出通过白名单自检，私有字段一个都不能出现。
- 所有失败都有明确状态与原因，退出码不阻断宿主会话或 git commit。
