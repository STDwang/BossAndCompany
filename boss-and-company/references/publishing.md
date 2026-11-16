# 公开展示与部署

已有网站选择 reuse 时，保留现有源码、设计、数据入口、路由和托管，增量更新资料。new 时另建公开网站库，不覆盖或停用原站。主页 keep 不改 README；replace 先在 private 公司空间保存旧版与 SHA，再受并发保护更新。选择保存后后续不重复询问。

公开内容只来自显式 public、且 status 为 user-stated/verified 的事实和项目；推测或争议记录不进入投影。性别、年龄、电话、家庭、财务、履历详情、简历 PDF 不自动公开。不能用 HTML 隐藏字段、注释、JSON、图片或源码夹带私密信息。生成的私有档案目录不能被 Pages 工件包含。

`scripts/render.py` 使用内置网站/主页/项目 README 模板，输出 public 和 private 分离的目录；company scaffold 将 public 安排到独立网站 repo/site，主页及其资源放 profile repo。模板用深墨蓝、纸白、薄荷绿和排版 SVG；SVG 是封面，不是实机截图。真实图文 README 优先使用项目已允许公开的截图，缺少时明确待补，不冒充实机效果。用户已有优秀视觉时优先复用。

新静态网站默认 GitHub Pages：候选模板 `.github/workflows/pages.yml` 只上传 site/，不上传仓库根目录。写入默认分支后，按账号权限启用 Pages 的 GitHub Actions 来源，核对 environment 和 pages/id-token 权限，等待部署成功并打开服务器返回的 URL。配置 Pages 需要管理权限，连接器无能力时用已登录 gh 的相应 API；缺权限报告待办，不绕过。实际默认分支非 main 时适配 workflow，不能照搬。

已公开的源码要保持用户原本选择；新项目私有不影响将已允许展示的介绍/图片发布到网站。构建产物、源代码、源码许可与展示授权分别核实。不要自动把私有源码迁到网站仓库。

验收：主页链接和图片、网站路由、项目数量、真实演示版本、手机和桌面布局；公开 PDF 若存在要单独检查内容。没有浏览器时报告视觉检查未运行。工作流已提交、构建成功、部署成功、实际 URL 可访问分别记录，不能混为完成。

官方部署参考：https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages （2026-11-15 核对）。使用前确认当前账号可用能力与实际 action 版本。
