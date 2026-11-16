<!-- BossAndCompany:begin -->
## BossAndCompany 默认工作约定

本项目：STDwang/BossAndCompany
项目身份是 owner/repo；同一仓库可被多个本地 checkout/AI Harness 管理。仓库级 company.json 与规则区块在所有工作区应完全一致，不得写入本地路径或工作区专属字段。
每个 checkout 的 workspace_id、私有仓库映射与绝对路径只保存在 gitignored 的 local.json；outbox、receipts、local.json 不随项目提交。
开始时读取 company.json 与 local.json，加载 BossAndCompany skill 和当前任务快照；按需读取 Boss 的目标/偏好，不加载所有私人历史。
事件必须带 workspace_id 与 harness，ID 以 workspace_id 为前缀；不同 Harness 分别追加独立事件，由明确协调者使用远端 SHA 维护唯一任务快照。
运行 `company.py workspace --project <目录>` 生成本 checkout 的不可变登记，再由 `sync.py` 上传到 private 公司空间 workspaces/。
关键决定、交接、阻塞及阶段完成时追加独立事件；实际代码、设计与正式决定留在项目。事件先写 outbox/，同步回读一致后再写回执；离线或权限不足时保留 pending。
不要伪造验证、人类验收或其他 AI 的工作；用户最新指令及宿主权限优先。DeepSeek 等环境按实际宿主加载技能和工具；无工具时仅整理上下文与待办。
<!-- BossAndCompany:end -->
