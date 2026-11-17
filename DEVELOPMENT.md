# BossAndCompany — 开发与交接说明

**跨 AI 平台的上下文管理 skill：把 GitHub 沉淀成可检索、可交接、可续写的「个人公司」。** 本文件是产品目标、已确认决定与实现边界的权威来源，供开发与接手 AI 阅读。技能入口见 [SKILL.md](boss-and-company/SKILL.md)，面向使用者的概览见 [README.md](README.md)。

关键词：`AI 上下文管理` `个人知识库` `跨 AI 协作` `多 Harness` `项目交接` `agent context` `handover` `knowledge base`

> 给接手开发的 AI：先读本 README，理解目标、用户已经确认的决定和当前实现边界，再按任务读取 SKILL.md、references 和脚本。不要把规划写成已实现能力，也不要在开发 skill 时顺手初始化用户的 GitHub。

## 1. 项目目标与使用背景

BossAndCompany 是一个跨 AI 平台的 skill。用户首次主动调用后，agent 将其 GitHub 组织成一个可持续积累上下文、登记成果、汇报工作和交接任务的“个人公司”。人类是 Boss，AI 按编码、美术设计、策划等岗位参与工作。

最重要的结果是：后来的人类或 AI 能快速理解用户是谁、近期想完成什么、有哪些项目、项目做到哪里、产物在哪里，以及下一步如何接手。公司比喻用于组织协作，不要求 AI 模拟雇佣关系，也不能以“老板偏好”为由违背事实或隐瞒失败。

最初使用场景是用户个人求职、学习 AI、开发游戏/工具/skill 和展示成果；好用后希望将本 skill 开源，作为自己的作品。实现应当对其他用户可复用，不能把特定账号、电脑路径、真实简历或私人历史硬编码进源码。

## 2. 用户已确认的产品决定

以下内容是开发依据。后续 AI 不应反复重新询问；用户新指令可以改变这些决定。

1. 第一阶段面向个人使用，不开发可视化上传选择界面，不实现每个新 AI 的独立访问审批系统。
2. 用户主动说“对我的 GitHub 使用这个 skill”，触发首次初始化。安装 skill 与真正初始化 GitHub 是两个动作。
3. agent 搜集用户提供位置或已授权范围内的本地项目、简历、历史对话；路径不明确时再问，不默认扫描整台电脑。
4. 建立/复用 public 的 GitHub 主页仓库和个人网站仓库，网站需要实际部署。
5. 建立/复用 private 的 Boss_Passport 和 Company_Workspace。
6. 新建的实际项目仓库初始均为 private，后续由用户选择哪些公开源码。已有仓库保留原可见性。
7. 不建独立简历仓库。简历作为输入，解析后归入老板档案，并按公开范围更新主页和网站介绍。
8. 编码、美术设计、策划三个岗位放在 Company_Workspace 内，初期不拆成三个仓库。以后可复制岗位结构新增岗位。
9. 岗位用于职责规范、述职、总结、日志和交接；项目代码和正式产物存实际项目仓库。
10. 首次初始化后，规则成为纳入管理项目的默认工作约定；后续项目创建并上传 GitHub 时，也应在公司空间登记和留痕。
11. 遇到已有内容时，主要询问两个选择：是否覆盖主页 README、是否复用个人网站。保存选择，后续不重复询问。
12. 支持 Claude Code、Codex、WorkBuddy，以及 DeepSeek 所在的实际 agent/工具环境。
13. 主动性由用户级开关控制，默认**只读刷新开、所有写入关**：接入 GitHub 后自动读取并同步 Boss 档案与 Company_Workspace 最新信息；代码提交后是否自动维护公司空间记录由用户单独开启。开关跨 Harness 生效，本地只能调得更保守。
14. 个人网站作为对外品牌长期维护。后期"最近在忙…"可视化模块只消费严格白名单的公开活动投影，不直接读取 private 公司空间或事件正文；网站仓库的现有内容（含已有简历页面与文件）不因本 skill 自动改动。

## 3. GitHub 公司的结构

| 仓库 | 可见性 | 负责什么 | 不应存放什么 |
| --- | --- | --- | --- |
| owner/owner | public | GitHub 主页 README、简介、精选成果和网站入口 | 私密档案、内部评价、凭证 |
| 个人网站仓库 | public | 介绍、成果卡片、项目详情、允许展示的图片、部署配置 | 未授权公开的经历详情、原始隐私资料 |
| Boss_Passport | private | 个人信息、经历、协作偏好、近期目标、愿望、约束、资料来源、`automation.json` 用户级主动性开关 | 认证密钥、整包客户端配置 |
| Company_Workspace | private | 公司规则、岗位、项目登记、任务快照、工作事件、交接、初始化选择 | 实际项目代码的第二份副本 |
| 各实际项目仓库 | 新建 private | 代码、策划案、美术资产、测试、正式决定、项目内协作规则 | 老板私人档案、公司内部日志 |

仓库名称通过配置映射。已有同职责仓库经核对后可复用别名，不为了符合名称而擅自重命名、删除或创建重复仓库。

Company_Workspace 的目标结构：

```text
Company_Workspace/
  README.md
  company.json
  WORK_PROTOCOL.md
  positions/
    Coder_Position/POSITION.md
    Art_Position/POSITION.md
    Planning_Position/POSITION.md
  projects/<project-slug>/
    PROJECT.json
    STATE.md
  workspaces/<workspace-id>.json
  events/<event-id>.json
  backups/profile/<date>-<old-file-sha>.md
```

其中 events 和 backups 按实际需要产生，不应为了补齐目录伪造记录。项目状态在 STATE.md 中维护一份权威快照，独立岗位事件提供依据；正式需求和决定仍需写回实际项目文档。

## 4. 首次初始化的目标流程

### 4.1 发现与盘点

识别已连接 GitHub 账号、工具能力、已有仓库、现有主页和网站、用户指定的工作根目录、项目和资料位置。仓库列表需要完整分页，不能按仓库大小推断它是空库。

优先复用现有成果、设计、项目数据入口、路由和部署。不要把模板直接盖在用户现有的 Next.js 或其他工程上。历史对话先按目录/标题筛选，再读取任务相关内容，不把所有聊天一次性灌进上下文。

### 4.2 主要两个问题

| 检测条件 | 向用户提出的问题 | 处理结果 |
| --- | --- | --- |
| 已有主页 README，且未保存选择 | 检测到已有 GitHub 主页，是否重新生成并覆盖 README？ | keep 保留不改；replace 先备份原版，再按当前 SHA 更新 |
| 已有个人网站，且未保存选择 | 检测到已有个人网站，是否复用现有网站及部署？ | reuse 保留工程和部署并增量更新；new 另建并保留原站 |

推荐默认分别为 keep 和 reuse。但默认选项不等于用户已经回答；尚未回答时暂停依赖该选择的写入，继续其他不受影响的整理。

没有现成主页/网站时记录 create。选择 new 必须指向与旧站不同、可用的目标仓库。若有多个网站无法判定，才额外澄清目标。账号、范围、权限等关键缺失也可以询问，但不要逐仓库重复请求复用确认。

### 4.3 提炼资料并建立公司

创建/复用对应仓库，显式指定新库可见性。解析简历和必要历史资料，建立老板摘要、规范化档案、项目索引和岗位规范。已有仓库按差异增量合并，不整体重置。保存仓库映射、两问结果、工作范围和检查点。

### 4.4 生成展示并部署网站

从明确允许公开的资料中生成主页和网站；实际项目源码私有不妨碍单独展示已允许公开的介绍和截图。无现有网站时使用内置模板，有现有网站时优先接入原有内容源。

个人网站须完成真实部署并返回有效 URL。生成 HTML、提交部署工作流、构建成功、部署成功及 URL 可访问是不同状态，必须分别确认。遇到权限限制时报告具体未完成步骤，不能宣称已经上线。

### 4.5 绑定默认规则

向用户指定的项目增量写入平台规则，保留原文件内容，安装/加载 skill；登记项目和当前状态。工作根目录也可以配置共享入口，但不能保证所有客户端都会继承祖先目录规则。新项目在当前 agent 创建并上传时应主动绑定和登记，范围外项目需另行纳入。

### 4.6 输出验收结果

报告实际创建/复用的仓库及可见性、主页处理结果、网站部署 URL、项目规则覆盖范围、资料来源覆盖情况、未完成项和待同步事件。失败后重跑应继续补齐，不能重复建库或反复问已保存的选择。

## 5. Boss_Passport 的资料规则

信息至少分清：事实经历、协作偏好、近期目标、愿望探索、约束和 AI 观察。每条记录保留来源和日期；重要事实使用稳定 id，支持后续修正。

- 用户最新自述/纠正优先；历史 AI 的推测不是事实，曾讨论的愿望不是已决定的目标。
- 有冲突时记录来源和待核实状态，不直接按文件时间覆盖。
- 敏感资料在用户授权范围内可以归入 private 档案，不另加逐字段审批流程。
- 允许 AI 知道隐私，不等于允许网站公开隐私。公开字段必须单独明确标记。
- 姓名、年龄、性别、电话、邮箱、城市、履历和原版简历 PDF 都不能仅因为像“基础信息”就默认公开。
- 不整包上传聊天原文、工具输出、认证配置、密码、Cookie、访问令牌或其他人的原始私密资料。
- 新 AI 先读简短目标/偏好和任务状态，必要时再查详细经历。

实际 JSON 格式和合并规则见 [档案协议](boss-and-company/references/passport.md) 及 [虚构档案示例](boss-and-company/assets/examples/profile.json)。当前配置、盘点、档案和事件均为 `schema_version: 2`，技能版本为 2；档案中的 `projects` 是唯一项目登记表，每项必须包含 `repository` 和 `status`。盘点发现但未纳入档案的项目会形成阻塞，不能默默创建或登记。推测/争议状态的项目不进入公开投影。文档读取依赖宿主的 PDF/DOCX/OCR 能力；没有能力时说明缺口并请求可读输入。

## 6. 岗位、协作与持续留痕

| 岗位 | 工作范围 | 交接应提供什么 |
| --- | --- | --- |
| Coder_Position | 编码、审查、调试、工程验证 | 产物/提交、实现范围、验证命令和结果、已知问题 |
| Art_Position | 视觉设计、美术资产和规格 | 资产位置、版本、尺寸/接入说明、允许展示范围、验证情况 |
| Planning_Position | 需求、玩法、范围和验收条件 | 规则、变更影响、决定依据、执行要求及待确认项 |

岗位是可复用的职责，不绑定固定模型。执行者记录实际使用的工具/模型；未知则写未知。新增岗位复制职责结构，不复制旧岗位的评价历史。

留痕触发点为：项目首次上传远端、关键决定、跨岗位交接、阻塞、阶段完成。不要每个工具调用都写日志。每条记录必须帮助后来者找到实际产物、理解验证范围并继续工作，避免空泛述职。

事件最小字段：schema_version、id（以 workspace_id 为前缀）、workspace_id、harness、recorded_at（带时区的 ISO 8601）、task_id、project、role、actor、kind、summary、artifacts、verification、next。样例见 [事件示例](boss-and-company/assets/examples/event.json)。人类和其他 AI 读取同一记录；观察、解释和建议应区分，不能伪造其他 AI 的评价。

多个 agent 协作时分别追加独立事件，由本次协调者合并项目快照；不要同时追加同一可变日志。任务状态可分 planned、in-progress、blocked、implemented、verified、accepted；人类验收须有实际依据。工作完成、自动测试通过和用户认可不能混为一谈。

## 7. 多 Harness、离线、重试和同步边界

BossAndCompany 将**项目身份**定义为唯一 `owner/repo`，将**工作区身份**定义为本地 checkout。用户机器上的 Codex、Claude Code、WorkBuddy、DeepSeek 宿主可以各自检出同一个 GitHub 仓库，也可以多个 Harness 共用同一个本地目录；这些都不产生第二份项目档案。

- `.boss-and-company/company.json` 是仓库级、确定性、可提交的配置，只含 `schema_version`、`skill_version`、owner、project、platforms 等所有 checkout 必须一致的信息；不含绝对路径、workspace_id 或 Harness 专属字段。多个 checkout 中的该文件应逐字节一致。
- `.boss-and-company/local.json` 是每个 checkout 的私有状态，保存 `workspace_id`、本地绝对路径和 private 仓库映射；必须被 .gitignore 排除。`workspace_id` 由本地路径生成，也可用 `bind --workspace-id` 在目录移动后显式沿用；不绑定具体 Harness。
- 事件必须带 `workspace_id` 与 `harness`，ID 以 `workspace_id` 为前缀。`company.py event` 在 ID 缺省时自动生成全局唯一 ID；相同 checkout 被不同 Harness 使用时，事件共享工作区身份，但 `harness` 和 ID 各自独立。
- `company.py workspace` 生成不含绝对路径的不可变工作区登记；`sync.py` 将它上传到 private 公司空间的 `workspaces/<workspace_id>.json`。多个 checkout 各自上传独立文件，不维护共享可变工作区日志。
- 项目 `projects/<slug>/PROJECT.json` 与 `STATE.md` 只有一份，按 `owner/repo` 定位。各 Harness 只追加独立 `events/<id>.json`；明确协调者读取远端当前 SHA 后合并唯一状态快照。无协调者时不得并发改 STATE.md。
- 不同技能版本绑定到同一仓库时会报 `skill_version` 冲突；已有同名技能副本内容不同也不会被覆盖，先人工确定升级版本。
- outbox、receipts、local.json 每个 checkout 独立且被 .gitignore 排除；公开项目不因 bind 而暴露 Boss/公司仓库映射或本地路径。

目标流程：本地记录 → 核实 Company_Workspace 为 private → 登记项目/工作区 → 上传独立文件 → 回读核对一致 → 保存回执。相同事件 id 和内容重试应幂等，同 id 不同内容应保留原记录并报告冲突。同步失败保留 pending，恢复后补传。

`scripts/sync.py` 已实现事件与工作区登记的实际远端闭环：使用当前已登录的 `gh` 核验公司仓库 private、读取默认分支、读取远端同名文件、按独立文件上传、再次读取并逐字节比对，成功后才调用 acknowledge。已有相同内容不重复写入；远端内容不同、回读不一致或公司为 public 时不写回执，并在结果中逐项报告。多个事件中的单项失败不会把其他成功项改写成失败。此脚本不处理项目登记和网站部署，且尚未在真实 GitHub 账号上端到端验收。单独使用 acknowledge 仍只表示调用方确认了远端回读，不能冒充实际网络校验。

默认规则依赖宿主加载与工具权限；它不是一个已经运行的后台监控服务，不保证未加载上下文的会话、任意聊天网页或范围外项目自动留痕。

### 7.1 主动性开关与自动同步（v3）

用户要求"接入 GitHub 后自动读取 Boss 与公司空间最新信息、代码提交后按开关维护公司空间"，同时"主动性交给用户设置开关"。实现见 [主动性开关协议](boss-and-company/references/automation.md) 与 [hooks 说明](boss-and-company/assets/hooks/README.md)。

**Skill 仍然不能后台自跑**：触发只能来自宿主 SessionStart hook、git post-commit hook，或 skill 被加载时按项目规则执行 `scripts/auto.py`。触发不等于授权写入。

| 开关 | 默认 | 行为 |
| --- | --- | --- |
| `auto_refresh` | `true` | `session-start` 只读拉取 Boss 档案与 Company_Workspace，写入 gitignored `.boss-and-company/cache/`，生成给接手 Agent 先读的 `CONTEXT.md` |
| `auto_record` | `false` | `post-commit` 把最近一次 commit 记成 private 事件（ID 与 commit 绑定、重放幂等、验证状态 not-run），默认只落本地 outbox |
| `sync_after_record` | `false` | 提交事件生成后自动上传并回读；`auto_record` 为 false 时强制 false，且只同步本次事件 |
| `activity_public` | `false` | 允许生成供网站消费的公开活动投影 |

- 权威开关在 private `Boss_Passport/automation.json`，**所有 Harness 读同一份**；每个 checkout 的 gitignored `local.json` 里 `automation_override` **只能把 true 降为 false**，试图提权会被记录并忽略。远端文件缺失时回退内置默认值，绝不回退成全开。
- 刷新缓存带 `boss_sha` / `company_sha` 和 `stale` 标记；失败保留旧缓存、返回原因、不阻断会话、不伪称同步。缓存目录由 bind 写进 .gitignore，`cache_guard` 二次校验。
- 提交事件只含元数据（SHA、时间、主题首行、分支），**不含 diff、代码、作者邮箱、本地路径**；公司仓库写入前核验 private，回读一致才标 synced。
- "最近在忙"投影需 `activity_public` 开启 + 事件显式 `visibility: public` + 项目 public/verified，输出字段严格限定 `date/project/title/stage/url` 并做自检。**必须显式 `--output`，脚本绝不自动写网站仓库或改现有页面**；把投影同步到网站是用户后续另行授权的动作。
- 版本区分：`SKILL.md` 包版本为 `6`（优化检索可发现性：description 触发词、中英文关键词、何时用/不用边界；v5 新增术语契约与交接/读历史纪律；基础格式未变）；绑定数据 `company.json` / `local.json` 的 `skill_version` 仍为 `2`（格式未变，已绑定项目无需重新 bind）；开关文件另有 `automation_version: 1`。

## 8. 跨平台兼容目标与安装

安装单元是 `boss-and-company/` 整目录，包含 SKILL.md、references、assets 和 scripts，不是只复制一个 Markdown 文件。

| 环境 | 项目级技能位置 | 默认项目入口 |
| --- | --- | --- |
| Codex | `.agents/skills/boss-and-company/` | `AGENTS.md` |
| Claude Code | `.claude/skills/boss-and-company/` | `CLAUDE.md` |
| WorkBuddy | `.codebuddy/skills/boss-and-company/` 或客户端技能导入入口 | `.codebuddy/CODEBUDDY.md` |
| 使用 DeepSeek 的 agent | 遵循实际宿主的技能加载方式 | 宿主规则及显式 `DEEPSEEK_CONTEXT.md` |

调用示例：

- Codex：`使用 $boss-and-company，对我的 GitHub 使用这个 skill。`
- Claude Code：`/boss-and-company 对我的 GitHub 初始化公司。`
- WorkBuddy：`调用 BossAndCompany，整理我的 GitHub 和这些项目目录。`

DeepSeek 是模型/服务生态，不能假设统一的技能目录或本地操作权限。经由其他 agent 使用时按宿主适配；普通聊天界面可整理用户提供的资料，但实际读写、终端与 GitHub 操作需要相应工具。各客户端不共享凭证，也不自动读取彼此历史。

当前兼容依据和参考来源见 [平台适配](boss-and-company/references/platforms.md)。本地规则生成测试不等于四个真实客户端都已端到端验收。

## 9. 当前代码与文件地图

```text
BossAndCompany/
  DEVELOPMENT.md                    产品目标、现状与开发交接（本文件，开发/接手 AI 用）
  boss-and-company/
    SKILL.md                        agent 执行入口
    agents/openai.yaml              Codex 展示元数据
    references/
      initialization.md             初始化、两问与恢复
      passport.md                   档案、简历导入与用户级开关
      platforms.md                  平台适配及能力边界
      publishing.md                 公开展示与部署
      work-protocol.md              岗位、留痕与交接/读历史纪律
      glossary.md                   术语契约：核心定义与反模式
      automation.md                 主动性开关、自动同步与公开活动投影
    assets/examples/                虚构配置、盘点、档案、事件、开关、活动投影
    assets/hooks/                   git post-commit 模板与宿主注册说明
    assets/templates/               主页、项目 README、网站、Pages 工作流
    scripts/
      company.py                    本地规划、生成、绑定、事件与回执
      render.py                     私密/公开分离的展示生成
      history_index.py              Codex 历史索引筛选
      sync.py                       已登录 gh 的事件上传与远端回读
      automation.py                 用户级开关解析与本地降权
      refresh.py                    只读刷新并生成私有接手上下文
      activity.py                   严格白名单的公开活动投影
      auto.py                       session-start / post-commit / activity / status 统一入口
  tests/test_company.py             本地行为、模拟同步与 CLI 流程测试
  scripts/check_package.py          无额外依赖的包结构检查
  scripts/package_skill.py          仅打包技能目录
  dist/boss-and-company.zip         可分发技能包
```

当前代码使用 Python 3.10+ 标准库，无运行依赖。

| 入口 | 已实现的实际行为 | 不能误称为 |
| --- | --- | --- |
| plan | 读取 config、inventory 和规范化的 profile 项目登记表，生成问题、动作和阻塞 | 自动实时盘点 GitHub |
| scaffold | 生成各仓库的本地候选文件；keep 不生成替换主页，reuse 输出网站适配数据 | 已创建仓库、更新远端或部署网站 |
| bind | 写入所有 checkout 一致的确定性规则与配置，另写本地私有 workspace 映射，可安装前三种宿主技能副本 | 已登记远端项目或全局自动监控 |
| workspace | 为当前 checkout 生成不含绝对路径的不可变工作区登记 | 已上传 GitHub |
| event | 校验并追加带 workspace_id/harness 的本地独立事件，按完整回执校验显示 pending/synced | 已上传 GitHub |
| acknowledge | 校验本地事件哈希、配置对应的远端文件链接并保存回执 | 脚本自身执行了远端回读 |
| sync | 通过已登录 gh 核验 private、上传工作区登记与独立事件、回读一致后写回执；冲突和失败逐项报告 | 已同步项目登记、已部署网站或已通过真实账号验收 |
| render | 仅投影显式公开且非推测/争议的 facts/projects，生成公开展示 | 自主理解简历或核实事实 |
| history_index | 按标题找 Codex 会话元数据及可找到的路径，不读取正文 | 自动读取四个平台全部历史 |
| automation | 解析 private Boss 档案的用户级开关，本地只能降权 | 自行替用户打开写入权限 |
| refresh | 只读拉取 Boss/公司空间最新状态，生成 gitignored 私有缓存与 CONTEXT.md | 已写远端、后台常驻监控或实时订阅 |
| activity | 按开关生成白名单公开投影并自检 | 自动改网站仓库、部署页面或公开事件正文 |
| auto | 会话开始/提交后/投影/状态四个动作的统一入口，失败不阻断宿主 | 未经宿主触发就能自行运行 |

GitHub 仓库创建、项目登记、文档语义解析、既有网站适配和部署验收，目前仍由宿主 agent 结合可用工具及 references 执行。没有独立的同步守护进程、自动调度器、通用 PDF/OCR 引擎或四个平台的统一登录系统。

## 10. 本地使用与开发验证

输入格式参考 assets/examples，所有示例均带 `schema_version: 2`，真实配置与资料放到技能源码之外。先让 agent 盘点，填好 inventory 和规范化的 profile 项目登记表，再生成计划。两个选择解决后，将决策写入配置：profile_readme 为 create/keep/replace，website 为 create/reuse/new。每个本地 checkout 都单独执行 bind/workspace；目录移动后可用 `--workspace-id` 沿用原工作区身份。

```text
python boss-and-company/scripts/company.py plan --config config.json --inventory inventory.json --profile profile.json
python boss-and-company/scripts/company.py scaffold --config config.json --profile profile.json --output new-output-directory
python boss-and-company/scripts/company.py bind --project project-directory --config config.json --repo owner/project --install-skills
python boss-and-company/scripts/company.py workspace --project project-directory
python boss-and-company/scripts/company.py event --project project-directory --record record.json --harness workbuddy
python boss-and-company/scripts/sync.py --project project-directory
python boss-and-company/scripts/company.py acknowledge --project project-directory --id event-id --remote-url https://github.com/owner/Company_Workspace/blob/main/events/event-id.json
python boss-and-company/scripts/history_index.py --root codex-home --query 简历 求职 交接 --limit 20
python boss-and-company/scripts/auto.py status --project project-directory
python boss-and-company/scripts/auto.py session-start --project project-directory --harness workbuddy
python boss-and-company/scripts/auto.py post-commit --project project-directory --harness workbuddy
python boss-and-company/scripts/auto.py activity --project project-directory --profile profile.json --output activity.json
```

`event --record` 的记录若省略 `id`、`workspace_id`、`harness` 或 `recorded_at`，命令会按当前 checkout 生成合法的全局唯一 ID、工作区身份和时间；显式 ID 必须以当前 `workspace_id` 为前缀。`sync.py` 要求本机已有已登录且有目标 private 仓库权限的 `gh`，不会保存凭证或打印 gh 的错误输出；它同步工作区登记与事件，不替用户创建仓库或部署网站。`acknowledge` 保留给宿主 agent 在自行完成并确认远端回读后登记。

生成目录须为空，避免覆盖已有成果。已有仓库须先比较差异再合并，不能把 scaffold 生成目录整体推到 public 仓库。上传文件要使用实时 SHA/受保护更新，相同内容不重复提交，远端变化时重读合并，不强推。

开发检查：

```text
python -B -m unittest discover -s tests -v
python -B scripts/check_package.py
python -B scripts/package_skill.py --output dist/boss-and-company.zip
```

打包脚本不覆盖已有 ZIP；重建时先检查并移走旧产物，或指定新的输出文件名。不要删除源码以解决打包冲突。

截至本轮开发交付，本地测试覆盖两问、可见性、规则保留、跨平台安装、公开/私密分离、项目状态过滤、事件幂等、多 checkout/多 Harness 身份隔离、模拟 gh 上传与回读、冲突/篡改检测、CLI 流程，以及新增的开关默认/降权、只读刷新与 stale 降级、提交事件幂等、公开投影白名单自检。分发包使用允许列表，不收隐藏文件、缓存和符号链接；`SKILL.md` 含 `version: 6` 与 `agent_created: true`，绑定数据 `skill_version` 仍为 `2`。这些仍不代表四个真实客户端的 hook 已完成端到端验收。没有实际证据时，不宣称后台自动同步已在所有宿主流行或网站模块已经上线。

## 11. 接手 AI 的下一步与验收标准

以下是建议的后续开发顺序，不是要求本次立即修改功能，也不应被理解为用户已批准上线新服务。

1. 阅读本 README 与当前脚本，复现已有测试，核对实现和协议的差异。
2. 用临时工程和虚构资料完成一次全链路试用：盘点、两问、生成、绑定、登记、事件、补传。真实 GitHub 验证需在用户明确指定的账号/仓库范围内执行。
3. 优先验证已有主页 keep、已有网站 reuse 的路径：保留原工程与内容，只补缺失结构，重跑不重复询问。
4. 在用户明确指定的临时账号/仓库中验收 `sync.py` 的真实 gh 行为，并把项目登记从宿主手工流程改成同样可回读、可重试的远端操作；处理远端并发写入与默认分支差异。不要只增加“已完成”文案。
5. 在 Codex、Claude Code、WorkBuddy 和一个实际 DeepSeek 宿主分别验证技能加载、默认规则、工具缺失及断网表现，记录实测与未测部分。
6. 用两个 Harness 检出同一个仓库，验证 company.json 一致、workspace_id 独立、事件 ID 不冲突、STATE.md 由单一协调者按 SHA 合并；再验证同一目录由两个 Harness 共用时事件 harness 字段可区分。
7. 使用一个真实项目做 AI 交接：接手者能找到当前目标、可用版本、正式规则、产物、验证结果和下一步，且不必重读全部日志。

成功标准：

- 首次初始化能得到正确可见性的仓库、有效网站 URL 与规则覆盖清单。
- 两个初始化选择正确执行并持久保存，重复运行可恢复且不破坏已有内容。
- 私密资料、来源路径和内部日志不进入公开展示及分发包。
- 新项目远端创建后能登记，阶段结束/交接/阻塞时能留下有证据的工作记录。
- 离线和部分失败如实保留状态，不把本地生成/回执冒充实际远端成功。
- 平台兼容报告说明具体宿主、验证范围和限制，不泛称任何模型均可自动执行。

## 12. 开发边界与交付约定

当前开发位置为本仓库目录，产品名称 BossAndCompany，技能标识 boss-and-company。后续部署到不同电脑时从实际位置解析，不能依赖这台机器的绝对盘符。

开发过程中保持 skill 源码、个人配置与真实档案分离。local/、private-data/、对话原文、认证凭证、生成的私人文件不进入分发包。示例和测试使用虚构资料。

保留公开主页和个人网站这两种入口；不重新引入独立简历仓库、三个岗位独立仓库、逐 AI 审批或可视化上传选择。若未来要增加，先与用户确认目标变化。

所有收尾说明都应区分：本地开发、已运行测试、真实远端写入、部署、人工验收。只修改文档时无需运行无关完整测试；涉及脚本行为变化时执行适当的已有检查。用户要求开发 skill 不等于授权修改其真实 GitHub 或项目。
