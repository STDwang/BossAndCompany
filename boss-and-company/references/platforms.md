# 平台适配

核心为标准 SKILL.md 和 Python 标准库脚本，不依赖 Codex 专属工具名称、特定模型或操作系统。先检查实际可用的文件读取、终端、GitHub、浏览器工具。JSON/Markdown 为交换格式；路径由当前环境提供，不硬编码个人电脑盘符。凭证使用宿主已有连接或 gh，不写进技能包。

| 宿主 | 项目技能目录 | 项目规则 |
| --- | --- | --- |
| Codex | `.agents/skills/boss-and-company` | `AGENTS.md` |
| Claude Code | `.claude/skills/boss-and-company` | `CLAUDE.md` |
| WorkBuddy | `.codebuddy/skills/boss-and-company` | `.codebuddy/CODEBUDDY.md`，兼容 AGENTS.md |
| DeepSeek 驱动的 agent | 使用该宿主的技能目录 | 使用该宿主规则，并显式加载 `DEEPSEEK_CONTEXT.md` |

初始化需要对当前宿主完成技能安装/加载检查。用户要求兼容多平台时可在所选工作根目录安装前三种目录的同一技能副本；检查已有同名技能，不覆盖未知修改，使用当前版本路径或报告冲突。不要在全盘或所有项目偷偷安装。其他平台首次接手时按其安装路径复制同一版本，不依赖某一客户端私有会话缓存。

`company.py bind` 写仓库级确定性入口、公开协调信息和每个 checkout 独立的 gitignored 私有映射；只有显式 `--install-skills` 才安装技能。必须分别验证“技能已可加载”和“项目规则已存在”。WorkBuddy 官方文档支持 `.codebuddy/skills`，部分运行环境也使用 `.workbuddy/skills`；接手时探测实际客户端约定，不假定两种路径都会同时生效。新项目不保证继承根目录规则：在当前任务明确创建新项目时，主动安装/引用 skill、bind 并登记；后续显式调用时核对遗漏项目。

同一个 `owner/repo` 可以同时被多个 Harness 检出。每个 checkout 单独执行 `bind` 和 `workspace`，但生成的项目级 `company.json` 与规则区块必须一致；`workspace_id`、绝对路径、outbox、receipts 只属于本地 checkout。不同 `skill_version` 绑定到同一项目时先解决版本冲突，不静默覆盖已有技能副本。事件中的 `harness` 记录实际执行宿主；同一目录由多个 Harness 共用时也各自生成独立事件 ID。唯一状态快照仍由协调者按远端 SHA 合并。

DeepSeek 是模型/服务与客户端生态，不假定存在统一 `.deepseek/skills` 标准目录。若通过 Claude Code、WorkBuddy 或其他 agent 使用 DeepSeek，按宿主适配。普通聊天环境缺少本地/远端工具时，以用户提供的文件整理结果和待执行清单，不宣称已创建仓库。工具调用需要应用实际执行并返回结果。

历史资料：Codex 可先索引 session_index.jsonl，再读取必要会话。Claude Code、WorkBuddy、DeepSeek 资料优先用户导出或提供目录；不得假定相同本地格式，不读认证文件，不为了取历史自动导出浏览器 Cookie。宿主不提供历史访问时明确覆盖范围。

没有 GitHub 工具但有终端时检查 gh 认证；工作区登记和事件同步可交给 `scripts/sync.py`，它只使用已登录 gh，不管理凭证或自动安装客户端。都没有 gh 与连接器时保留离线资料。没有浏览器时可校验部署状态/HTTP 和生成路径，但视觉验收记为未执行。不要自动安装客户端、Python、浏览器或付费 API。

官方依据（核对日期 2026-11-15；平台升级后再核实）：
- Codex skills：https://learn.chatgpt.com/docs/build-skills
- Codex/Claude 安装目录：https://developers.openai.com/api/reference/cli
- Claude skills：https://code.claude.com/docs/en/skills
- Claude 项目记忆：https://code.claude.com/docs/en/memory
- WorkBuddy 项目配置：https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Project
- DeepSeek tool calls：https://api-docs.deepseek.com/guides/tool_calls/

本版本提供文档依据及本地规则生成测试，不宣称四个客户端均已完成真实端到端运行。
