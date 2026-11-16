# 日常留痕

开始：读取项目规则、仓库级 `company.json`、当前 checkout 的 `local.json` 和当前任务快照，按需要读取 Boss 简要目标/偏好和本岗位职责。不重复加载全部历史日志。识别本次 task_id、event_id、workspace_id、harness、实际执行者与岗位，不伪造其他模型评价。

岗位：Coder 交付代码与验证；Art 交付设计/资产规格与接入说明；Planning 交付规则、范围、验收条件。新增岗位复制职责模板后修改，不能复制旧岗位的历史评价。

触发：项目首次上传远端、关键决定、跨岗位交接、阻塞或阶段完成。小修改只在最终汇报时合并记录，禁止每次工具调用写日志。任务状态可为 planned/in-progress/blocked/implemented/verified/accepted；accepted 要有用户验收依据，不能 AI 自评验收。没有运行验证就用 not-run。岗位事件不是任务状态的第二份权威来源。

事件必填：schema_version（当前为 2）、id（以 workspace_id 为前缀）、workspace_id、harness、task_id、project（owner/repo）、role、actor、kind、summary、artifacts、verification、next、recorded_at（带时区的 ISO 8601）。格式见 assets/examples/event.json。`company.py event` 可自动生成合法 ID、workspace_id 和时间；显式 ID 必须属于当前 checkout。artifacts 链接实际项目文件/提交/设计稿；没有产物可为空但说明原因。private 公司空间保存记录，公共项目不写公司内部评价或 Boss 内容；私有仓库映射和绝对路径只写入 gitignored 的 local.json。

项目身份是唯一 `owner/repo`，不是本地目录或 Harness。多个 checkout/Harness 检出同一仓库时，`PROJECT.json` 与 `STATE.md` 仍只有一份。每位执行者写独立 `events/<id>.json`，每个 checkout 用 `company.py workspace` 生成独立 `workspaces/<workspace_id>.json` 登记；协调者读取远端 SHA 后合并唯一的 `projects/<slug>/STATE.md`。用户没有指定协调者时当前执行者负责本次汇总，但不能伪造跨会话调度。并行事件不共享可变日志文件；相同 id 重试应幂等，不同内容同 id 报冲突。项目登记保存在 `PROJECT.json`（实际 repo、状态、入口），重复登记合并而不创建副本。不同 `skill_version` 不得静默覆盖彼此的仓库级配置。

默认入口只在初始化选择的工作范围内写入。没有技能加载支持的 DeepSeek/其他聊天客户端需要显式提供上下文，不承诺自动执行。

自动化：会话开始按 [主动性开关](automation.md) 运行 `auto.py session-start`，只读刷新 Boss 与公司空间最新状态到 gitignored `cache/`，生成给接手 Agent 先读的 `CONTEXT.md`；缓存带远端 SHA，失败保留旧缓存并标 stale，不阻断工作也不伪称同步。提交后按 `auto_record` 由 `auto.py post-commit` 生成一条 private 事件，ID 与 commit 绑定、重放幂等、只含元数据且验证状态为 not-run；默认只落本地 outbox，需 `sync_after_record` 才上传并回读，且只同步本次事件。开关以 private Boss 档案的 `automation.json` 为准，本地 `local.json` 的 `automation_override` 只能降权。自动记录不能替代关键决定、交接与验收的人工事件，也不能修改唯一 `STATE.md`。供网站消费的 `activity.json` 只在 `activity_public` 开启且事件显式 public 时生成，输出严格白名单；事件正文、私有仓库与本地路径永不出云到公开位置。

离线：`company.py event` 先保存 `.boss-and-company/outbox/<id>.json`，`company.py workspace` 先保存 `.boss-and-company/outbox/workspaces/<workspace_id>.json`。outbox、receipts 和 local.json 都属于当前 checkout，均通过 .gitignore 排除，不能随公开项目上传。联网后优先执行 `sync.py --project <目录>`：脚本通过已登录 gh 核验 Company_Workspace 仍 private、读取默认分支、按独立文件写入 workspaces/ 与 events/、再次读取并逐字节比对，成功后才为事件调用 acknowledge 写远端 URL；不删除本地事件。同 id 已存在且内容一致直接回执，不重复写入；内容不同停止并修复标识。仅有网络请求发出不算同步成功；脚本返回 conflict/failed 时相关记录仍为 pending。项目登记和网站部署由宿主 agent 另行完成。

如果初始化尚未登记该项目，先把 `projects/<slug>/PROJECT.json` 写入公司空间，再同步工作区登记和事件。若登记失败则相关记录保持 pending，最终报告具体阻塞。正式需求/决定必须写回项目文档，事件引用该文件，避免用日志替代规格。
