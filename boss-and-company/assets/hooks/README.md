# 自动化触发入口

Skill 是被动加载的知识和脚本，**不会自己在后台运行**。所谓"自动"只能来自以下三种触发方式之一。无论哪一种，真正能不能执行都由 private Boss 档案里的 `automation.json` 决定；触发本身不等于授权写入。

## 统一命令

```text
python <skill>/scripts/auto.py status        --project <项目目录>
python <skill>/scripts/auto.py session-start --project <项目目录> --harness <宿主名>
python <skill>/scripts/auto.py post-commit   --project <项目目录> --harness <宿主名>
python <skill>/scripts/auto.py activity     --project <项目目录> --profile <profile.json> --output <activity.json>
```

`<skill>` 是该 Harness 实际安装技能的位置，例如 WorkBuddy 的 `C:/Users/<用户>/.workbuddy/skills/boss-and-company`，或项目级 `.codebuddy/skills/boss-and-company`。不同 Harness 路径不同，但脚本内容相同。

- `status`：只读显示当前生效开关、开关来源、本地覆盖情况和缓存新鲜度，不联网。
- `session-start`：按 `auto_refresh` 只读拉取 Boss 档案与 Company_Workspace 最新状态，写入本 checkout 的 gitignored `.boss-and-company/cache/`，生成 `CONTEXT.md` 供接手 Agent 先读。**不写任何远端**。
- `post-commit`：按 `auto_record` 把最近一次本地 commit 记成 private 事件；只有 `sync_after_record` 也为 true 才上传到 private 公司空间，且只同步本次事件，不会顺带上传其它 pending 事件。
- `activity`：按 `activity_public` 生成供网站消费的公开投影。**必须显式给 `--output`**，脚本绝不自行选择网站路径，也绝不直接修改网站仓库。

## 注册方式

1. **宿主 SessionStart / 会话启动 hook**：把 `session-start` 命令注册到宿主自身的 hook 配置中。各宿主配置文件名和 JSON 结构不同（Claude Code 用 settings 的 hooks 字段，CodeBuddy/WorkBuddy 用各自的配置入口，DeepSeek 等无工具环境只能人工提供上下文），请按当前宿主官方文档填写，本 skill 不擅自改写宿主配置。
2. **Git post-commit hook**：把 `assets/hooks/post-commit` 复制进 `.git/hooks/` 并设为可执行；若已有 hook，把其中最后一条 python 命令追加进去。可用 `BOSS_AND_COMPANY_SCRIPTS` 指向技能脚本目录。
3. **无 hook 的"软自动"**：项目规则区块（`AGENTS.md` / `CLAUDE.md` / `.codebuddy/CODEBUDDY.md`）已写明，skill 被加载时应先运行 `session-start`、提交后按开关运行 `post-commit`。这依赖宿主确实加载了 skill，不能承诺未加载的会话也会执行。

## 失败与降级

- 刷新失败：保留上一次缓存并标记 `stale`，返回明确原因，**不伪称已同步**，不阻断会话。
- 提交记录失败：返回 `failed` 原因，不阻断 git commit（hook 始终以 0 退出）。
- 任何动作都不会把私有内容写进公开仓库、网站或日志；stdout 只输出状态 JSON，不含档案正文。

## 开关优先级

`Boss_Passport/automation.json`（用户级，跨 Harness）→ 本 checkout `local.json` 的 `automation_override`（**只能把 true 降为 false**，试图提权会被记录并忽略）→ 远端文件缺失时回退到内置默认值（只读开、写入全关）。

`auto_record` 为 false 时，`sync_after_record` 强制为 false。
