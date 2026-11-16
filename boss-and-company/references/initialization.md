# 初始化与恢复

1. 盘点账号、工具能力与用户指定的工作根目录。只搜索授权范围，先列简历/项目候选再读需要的内容。多个目录可分批。获取当前 GitHub 全部可访问仓库（分页），识别主页、网站、私密档案、公司空间与项目。查看内容后才认定用途；不要按 repo size 推断空库。
2. 保存本地配置：schema_version（当前为 2）、skill_version（当前为 2）、owner、repositories 映射、decisions、workspace_roots、platforms、已完成检查点。owner 未知先读取已连接账号。`assets/examples/config.json` 为示例；工作根目录为本机配置，不随公开项目提交。配置、盘点、档案和事件均须带当前 `schema_version`，旧格式先迁移再生成。
3. 两问：现有主页 README 未决定时问 keep/replace；已有网站未决定时问 reuse/new。选择保存，未答就仅阻塞相关写入。选择 new 需与旧站不同的仓库名；存在多个网站需让用户指明一个。保留主页时不自动追加新内容；输出建议变更即可。覆盖时备份原版到 private 公司空间的 backups/profile/日期-原文件SHA.md，再按 SHA 更新原 README。
4. 仓库增量创建/复用。指定已有 Boss 档案别名时直接核对 private 并复用。Boss 或公司目标若 public，暂停向该目标写入私密资料，不默默改成 private，也不要求其他不受影响步骤停工。新实际项目默认 private；现有 public 项目不改可见性。项目已有远端且明确属于用户时直接登记，不能无故复制。
5. 资料提炼进 Boss_Passport；规范化 profile 的 projects 是唯一项目登记表，每项带 repository、status、贡献、真实完成范围、源码状态和展示范围。inventory 中发现但未进入 profile 的项目产生阻塞，不能默默登记。推测/争议项目不进入公开投影。岗位规范存公司空间，策划/美术实际产物仍在项目中。`scaffold` 仅生成候选文件，已有仓库逐文件差异合并，不能整目录覆盖。
6. 网站/主页按两问结果更新，详情见 publishing.md。同步私密资料和公司结构前再次核实可见性；新增库明确 private/public。不要把生成目录顶层整体 push 到某个公开仓库。
7. 为每个纳入管理的本地 checkout 执行 `company.py bind --project <目录> --config <配置> --repo <owner/repo> --install-skills`；同一仓库的不同 checkout 使用相同 `owner/repo`，不重复登记项目。可提交的 `company.json` 是各 checkout 必须逐字节一致的确定性文件；`workspace_id`、本地路径和 private 仓库名只留在 gitignored 的 `local.json`。目录移动后用 `--workspace-id` 沿用身份。随后执行 `company.py workspace --project <目录>` 生成不可变工作区登记。各本地 checkout 的 outbox/receipts/local.json 独立，不共享。
8. 完成真实部署与回读验证；工作区登记和事件在已登录 gh 可用时执行 `sync.py --project <目录>`，由脚本核验 private、逐文件上传并回读一致后写回执。输出各仓库和网站链接，以及每个工作区/事件的 synced/already-synced/conflict/failed 状态。重跑读取现有配置，补齐缺失步骤，检查私密与公开可见性没有漂移。不要重复发起两问。项目登记和网站部署仍须按 publishing.md 单独核实。

工具示例：优先当前平台 GitHub 连接器。需要创建仓库且连接器不支持时，在已认证 gh 中执行 `gh repo create owner/Boss_Passport --private` 等明确可见性的命令；当前官方命令有变时查看 gh help。只读盘点与上传写入分开，失败不要泄露 token。

更新文件使用实时 blob SHA，内容相同不创建重复提交。工作区登记和事件都使用独立文件名，由 `sync.py` 读取当前默认分支、远端回读及冲突检测；多个 Harness 只追加不可变文件，唯一 `STATE.md` 由明确协调者按 SHA 合并，其他远端并发变化先重读合并。同步结果记在私有公司空间，不在公共仓库暴露 Boss 内容或私有项目清单。
