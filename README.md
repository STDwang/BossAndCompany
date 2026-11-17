# BossAndCompany

**GitHub personal branding for beginners + AI context management — 一句话拥有个人名片品牌，也让项目上下文不再断片。**

> 一个跨 AI 平台的 Agent Skill，做两件事：**①让任何人（哪怕零基础、没有简历）一句话就在 GitHub 拥有个人主页 + 个人网站，打造自己的名片品牌；②把项目沉淀成可持续积累上下文的「个人公司」，让后来的你——或任何一个接手的 AI——快速搞清「你是谁、在做什么、东西在哪、下一步怎么接」。**

人类是 Boss，AI 按编码 / 美术 / 策划等岗位参与。公司只是组织协作的比喻，不要求模拟雇佣关系，也不会用「老板偏好」掩盖事实或失败。

[![skill version](https://img.shields.io/badge/skill-v7-blue)](boss-and-company/SKILL.md) ![MIT](LICENSE) ![Python 3.10+](README.md) ![Codex · Claude Code · WorkBuddy · DeepSeek](README.md)

<details>
<summary>关键词 / keywords（供人和 AI 检索）</summary>

`GitHub 个人名片` `个人主页` `个人网站` `作品集` `简历页` `个人品牌` `小白建站` `AI 上下文管理` `个人知识库` `项目交接` `跨 AI 协作` `多 Harness` `工作留痕` `任务快照` `个人公司` `GitHub profile` `personal website` `portfolio` `personal branding` `agent context management` `personal knowledge base` `multi-agent handover` `project journal` `cross-harness collaboration` `AI memory` `onboarding`

</details>

**适合谁**：想让别人在 GitHub 上搜到自己的任何人（不需要会写代码、不需要现成简历）；独立开发者、学习者、用多个 AI 编码助手（Claude Code / Codex / WorkBuddy / DeepSeek）的人；以及任何"换个会话就断片、换个 AI 就重来"的场景。

## 快速开始：一句话做个人名片

零基础也能用。对你正在用的 AI 说：

> 「帮我在 GitHub 做个个人名片 / 个人网站」

AI 会用几轮简单问题问你的称呼、做什么、3 个关键词和链接（**没有简历、没有项目也能开始**），确认哪些可以公开后，自动生成并部署 GitHub 主页 README + 个人网站，最后给你两个能打开的链接。完整流程见 [小白品牌名片快速路径](boss-and-company/references/brand-card.md)。

想进一步管理项目、跨 AI 协作留痕、做交接汇报？继续看下面的「个人公司」能力。

## 它解决什么问题

**个人品牌**：小白没有简历、不懂 GitHub 也能一句话生成名片主页和网站；已有材料的则从简历和项目提炼，公开前逐项确认隐私边界。

**协作记忆**：AI 会话是短暂的，项目上下文总会丢失。BossAndCompany 把分散在 GitHub、本地项目和历史对话里的信息，沉淀成一套可检索、可交接、可续写的结构：

- **老板档案**（private）：事实经历、协作偏好、近期目标、约束与来源，公开字段单独标记
- **公司空间**（private）：岗位规范、项目索引、任务快照、独立工作事件、跨 AI 交接记录
- **公开展示**（public）：GitHub 主页 README + 一个真实部署的个人网站，只投影明确允许公开的内容
- **默认协作规则**：给纳入管理的项目写入各平台的 agent 入口文件，统一留痕与交接协议

## 能力一览

- **小白品牌名片**：一句话触发、几轮问答收集（无简历也能从零开始）、自动生成主页 README + 个人网站并部署；已有主页/网站默认保留复用，不覆盖。[查看快速路径](boss-and-company/references/brand-card.md)。
- **首次初始化**：盘点已有仓库 / 项目 / 资料，建立或复用上述结构，主页覆盖与网站复用各问一次并记住选择，可断点重跑且幂等。
- **多 Harness 共处**：项目身份唯一 `owner/repo`；同一仓库可被多个本地 checkout、多个 AI Harness 使用，事件带 `workspace_id` + `harness`，绝不复制唯一状态快照。
- **留痕与交接**：登记、关键决定、交接、阻塞、阶段完成时追加独立事件；离线保留 pending，回读一致后才标 synced。
- **主动性开关（可选）**：会话开始只读刷新私有缓存、提交后记录私有事件、"最近在忙"公开投影——每项都由 private 档案里的开关控制，默认全部写入关闭。Skill 本身被动加载，**不会在后台自行运行**。
- **隐私优先**：私有仓库映射、本地路径、checkout 身份只存 gitignored 文件；公开投影走严格白名单并自检。

> ⚠️ 这是**协议 + 离线辅助脚本**，不是托管服务。仓库创建、网站部署、文档语义解析仍由宿主 Agent 结合可用工具执行；没有独立后台守护进程，也不保证未加载上下文的会话会自动留痕。

**不解决问题**：不调度多个 agent 并发执行任务、不开并行推理"会议"（那是运行时编排工具，如 AgentNave 的职责）；不管理凭证密钥；不做单次问答。想了解与运行时编排工具的分工，见 [DEVELOPMENT.md](DEVELOPMENT.md)。

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

- **做个人名片（小白入口）**：`帮我在 GitHub 做个个人名片 / 个人网站`（没简历也可以，AI 会问你几个简单问题）
- 首次初始化：`对我的 GitHub 使用 BossAndCompany。`
- 交接 / 汇报：`用 BossAndCompany 整理当前项目并写一份交接。`
- 查看自动化开关：`跑一下 auto.py status。`

首次初始化会授权常规创建、归档、规则绑定与网站部署；已有主页覆盖、网站复用会先问你并保存选择。主动性写入默认关闭，需你显式开启。

环境要求：Python 3.10+（仅标准库，无运行依赖）；远端留痕需要本机已登录且有权限的 `gh`，或使用已连接的 GitHub 工具。

## 仓库结构

```text
boss-and-company/        <- 可安装的 skill 本体
  SKILL.md               <- Agent 执行入口
  references/            <- 小白品牌名片 / 初始化 / 档案 / 平台 / 展示 / 留痕 / 交接 / 术语契约 / 自动化协议
  assets/examples/       <- 全部为虚构示例数据
  assets/templates/      <- 主页 / 项目 README / 网站模板
  assets/hooks/          <- 可选的 SessionStart / post-commit 钩子
  scripts/               <- 本地规划、生成、绑定、留痕、同步、刷新、投影脚本
tests/                   <- 单元测试（含模拟远端 gh）
scripts/                 <- 包结构检查与打包脚本
DEVELOPMENT.md           <- 面向开发 / 接手 AI 的完整说明
```

## 开发验证

面向开发与接手 AI 的完整说明（产品目标、已确认决定、实现边界）见 [DEVELOPMENT.md](DEVELOPMENT.md)。

```bash
python -B -m unittest discover -s tests -v
python -B scripts/check_package.py
python -B scripts/package_skill.py --output dist/boss-and-company.zip
```

## 许可

MIT — 见 [LICENSE](LICENSE)。
