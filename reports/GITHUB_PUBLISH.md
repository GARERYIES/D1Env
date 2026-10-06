# GitHub 上传与 Linux 就绪说明

日期：2026-10-06。用户明确授权将 D1Env 上传 GitHub；这替代原轮次“未授权推送”的限制，不授权 M3、SDK 或机器人操作。

## 待上传结果

计划位置：`GARERYIES/D1Env`。未指定可见性时使用 private；最终仓库/提交/Release 后状态由上传完成记录确认。

## 已验证源码上传

- 仓库：[GARERYIES/D1Env](https://github.com/GARERYIES/D1Env)，实际 visibility=PRIVATE，默认分支 main。
- 首次源码上传提交：`a4dbe38ca839341f7ac25ce9a42e1187224024ee`；实际 `git ls-remote origin refs/heads/main` 与发布副本 HEAD 完全一致。
- `gh repo create ... --private` 和干净发布副本的 `git push -u origin main` 均退出 0；远端 README contents API 核对成功。
- 发布副本为本交付中的 D1Env-GitHub 目录；只有它配置了 GitHub origin。原 d1env-foundation 研发仓库没有指向该远端，避免后续误推旧历史。
- 首次新历史已逐 blob 检查；凭据/个人路径命中为 0。旧失败日志去敏后仍保留原失败原因与断言，不把失败改成 PASS。
- 编译前端通过单独标识为 MOCK 的 prerelease 附件交付；GitHub 自动生成的 source zip 仍不含 frontend/dist。

发布使用只含当前清理后文件的新 Git 历史，保留本地 d1env-foundation 原研发历史。发布前发现并清理 1 枚 pytest 失败输出中的测试 CSRF 值与 5 处本地临时路径；普通清理提交不消除旧 blob，原历史不会上传。源码、日志、README、锁定依赖、报告和 MOCK 截图可上传；不含参考 checkout、厂商 SDK/二进制、凭据、运行数据库、虚拟环境或 node_modules。

## Linux 能否开箱即用

结论：**当前不能宣称 Linux 开箱即用。** 已实际验证的环境为 Darwin/macOS aarch64。Linux 结论来自本次实际代码/工件审查，全新 Ubuntu 的 A16/M3 为 NOT_RUN。

| 方式 | 已有内容 | 仍需条件/边界 |
|---|---|---|
| 源码 clone / GitHub 自动 source zip | 当前代码、配置、测试、报告 | 前端 dist 不在 Git；需要 uv、Node 24.x/npm、浏览器/桌面、网络与可写目录，先构建 |
| 单独附加的 D1Env-M0-M2.zip | 源码和已构建前端；启动脚本可执行 | 无需 Node；需要 uv、Chrome/Chromium 与桌面；首次 Python/依赖下载需要网络 |
| 无桌面服务器 | 源码 CLI 可作为开发入口 | 尚无可直接使用的远程认证向导；--no-browser 不提供引导凭据 |
| pip wheel | 当前仅打包 Python 代码 | 未独立打包 profiles、静态前端与项目数据；不是发行安装入口 |

依据：scripts/start-demo.sh:5–15；src/d1env/cli.py:20–22、90–102；pyproject.toml 的 wheel packages；.gitignore 忽略 frontend/dist；docs/ACCEPTANCE.md A16。实际 npm lock 对完整开发/测试的 Node 范围有要求，本轮实测 Node 24.19.0。启动仍只监听 127.0.0.1，不能用扩大监听范围替代远程会话设计。

真实 Docker 生命周期、免开发工具 Ubuntu 安装包和系统兼容属于 M3，SDK/机器人只读属于 M4。全部真实候选 disabled/not_implemented，遥测 UNKNOWN/null。GitHub 上传与提供预构建 MOCK 附件不提升它们的验证等级。

## 当前核验

- Git 工作区已核对，上传前没有原有未提交修改被覆盖。
- 本机 GitHub CLI 已认证至 GARERYIES，目标 D1Env 查询确实不存在。
- ZIP 静态内容检查通过：已构建前端存在、启动文件可执行，无 SDK、数据库或临时凭据文件。
- 文档补充不更改产品行为；沿用 M2 的 90 Python、12 UI、1 E2E 的 macOS 实测证据，不重新将它们算作 Linux PASS。
- 尚未运行 Linux 主机、Docker 生命周期、SDK、机器人、网络/固件修改或运动。
- 预构建前端补充实际 React 19.1.1、ReactDOM 19.1.1、scheduler 0.26.0 的 MIT 文本及 Vite 8.3.3 包中的许可全文；见 THIRD_PARTY_NOTICES.md。没有替项目选择整体许可证，完整 SBOM 仍未完成。
