# BossAndCompany

> 一个跨 AI 平台的 Agent Skill：把你的 GitHub 整理成一座可持续积累上下文的「个人公司」，让后来的你——或任何一个接手的 AI——快速搞清「你是谁、在做什么、东西在哪、下一步怎么接」。

人类是 Boss，AI 按编码 / 美术 / 策划等岗位参与。公司只是组织协作的比喻，不要求模拟雇佣关系，也不会用「老板偏好」掩盖事实或失败。

## 它解决什么问题

AI 会话是短暂的，项目上下文总会丢失。BossAndCompany 把分散在 GitHub、本地项目和历史对话里的信息，沉淀成一套可检索、可交接、可续写的结构：

- **老板档案**（private）：事实经历、协作偏好、近期目标、约束与来源，公开字段单独标记
- **公司空间**（private）：岗位规范、项目索引、任务快照、独立工作事件、跨 AI 交接记录
- **公开展示**（public）：GitHub 主页 README + 一个真实部署的个人网站，只投影明确允许公开的内容
- **默认协作规则**：给纳入管理的项目写入各平台的 agent 入口文件，统一留痕与交接协议

## 能力一览

- **首次初始化**：盘点已有仓库 / 项目 / 资料，建立或复用上述结构，主页覆盖与网站复用各问一次并记住选择，可断点重跑且幂等。
- **多 Harness 共处**：项目身份唯一 `owner/repo`；同一仓库可被多个本地 checkout、多个 AI Harness 使用，事件带 `workspace_id` + `harness`，绝不复制唯一状态快照。
- **留痕与交接**：登记、关键决定、交接、阻塞、阶段完成时追加独立事件；离线保留 pending，回读一致后才标 synced。
- **主动性开关（可选）**：会话开始只读刷新私有缓存、提交后记录私有事件、"最近在忙"公开投影——每项都由 private 档案里的开关控制，默认全部写入关闭。Skill 本身被动加载，**不会在后台自行运行**。
- **隐私优先**：私有仓库映射、本地路径、checkout 身份只存 gitignored 文件；公开投影走严格白名单并自检。

> ⚠️ 这是**协议 + 离线辅助脚本**，不是托管服务。仓库创建、网站部署、文档语义解析仍由宿主 Agent 结合可用工具执行；没有独立后台守护进程，也不保证未加载上下文的会话会自动留痕。

## 安装

安装单元是 `boss-and-company/` **整个目录**（含 SKILL.md、references、assets、scripts），不是单个 Markdown 文件。复制到对应平台的技能目录：

| 平台 | 技能目录 | 项目入口文件 |
| --- | --- | --- |
| Codex | `.agents/skills/boss-and-company/` | `AGENTS.md` |
| Claude Code | `.claude/skills/boss-and-company/` | `CLAUDE.md` |
| WorkBuddy | `.codebuddy/skills/boss-and-company/` | `.codebuddy/CODEBUDDY.md` |
| 其他 Agent | 遵循宿主加载方式 | 显式上下文文件 |

## 用法

安装后对你正在使用的 Agent 说：

- 首次初始化：`对我的 GitHub 使用 BossAndCompany。`
- 交接 / 汇报：`用 BossAndCompany 整理当前项目并写一份交接。`
- 查看自动化开关：`跑一下 auto.py status。`

首次初始化会授权常规创建、归档、规则绑定与网站部署；已有主页覆盖、网站复用会先问你并保存选择。主动性写入默认关闭，需你显式开启。

环境要求：Python 3.10+（仅标准库，无运行依赖）；远端留痕需要本机已登录且有权限的 `gh`，或使用已连接的 GitHub 工具。

## 仓库结构

```text
boss-and-company/        <- 可安装的 skill 本体
  SKILL.md               <- Agent 执行入口
  references/            <- 初始化 / 档案 / 平台 / 展示 / 留痕 / 自动化协议
  assets/examples/       <- 全部为虚构示例数据
  assets/templates/      <- 主页 / 项目 README / 网站模板
  assets/hooks/          <- 可选的 SessionStart / post-commit 钩子
  scripts/               <- 本地规划、生成、绑定、留痕、同步、刷新、投影脚本
tests/                   <- 单元测试（含模拟远端 gh）
scripts/                 <- 包结构检查与打包脚本
README.md                <- 面向开发 / 接手 AI 的完整说明
```

## 开发验证

```bash
python -B -m unittest discover -s tests -v
python -B scripts/check_package.py
python -B scripts/package_skill.py --output dist/boss-and-company.zip
```

## 许可

MIT — 见 [LICENSE](LICENSE)。
