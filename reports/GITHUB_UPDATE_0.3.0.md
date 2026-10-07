# GitHub 0.3.0 软件候选更新

日期：2026-10-07。用户明确授权更新 GitHub 源码、仓库简介与 README，并要求参考 IOENV 的用语及组织结构。本次授权允许发布已有软件候选，不包含 Docker 镜像仓库发布、SDK、机器人或系统修改。

## 发布状态

已完成源码快进推送、About / topics 更新、README 重组与 [0.3.0 软件候选发布](https://github.com/GARERYIES/D1Env/releases/tag/v0.3.0-software-candidate)。发布时刻为 `2026-10-07T12:07:54Z`（UTC），即北京时间 20:07:54。仓库仍为 PRIVATE；候选保持 prerelease，不标为正式稳定版。

产品源码与 tag 固定在 `0ca407e8c94964118090a009b167a831fd543fd1`；本报告与最终核验记录随后独立更新 main，不修改 tag 或下载归档。

## 内容与组织

- README 从研发时间线改为项目概述、Features、Quick Start、Commands、Configuration、Architecture、Compatibility & Validation、Development、Notes、Roadmap、Documentation、License。
- 原 README 与交接入口分别保留为 `README-HISTORY.md`、`START_HERE-HISTORY.md`；原始设计、计划和阶段报告保留。
- 术语与职责沿用 Environment definition、Container lifecycle、Feature startup & checks；D1Env 独立实现部署引擎，不声称上游提供现成 D1 适配。
- 参考实际官方 [IOEnv CLI README](https://github.com/ioai-tech/ioenv_cli/blob/ec1f8354095de91a234dc31a9213ee1a410b5cc9/README.md) 和 [IO-Creed 教程](https://io-ai.tech/iocreed/en/docs/locomotion_00/)。固定源码 `ec1f8354095de91a234dc31a9213ee1a410b5cc9`；官网页面无可固定源码提交。`ioai-tech/ioenv` 未取得公开仓库，不使用猜测链接。

已生效且经 GitHub API 核对的 About：

> A profile-driven environment manager for D1 robotics development, with a Chinese web UI, Docker lifecycle orchestration and scoped ROS software checks. Apple Silicon preview.

## 源码与候选资产

- 仓库：[GARERYIES/D1Env](https://github.com/GARERYIES/D1Env)，本轮开始时实际 private、main；保留可见性和旧 `v0.1.0-mock-m2`。
- 仅从 `outputs/D1Env-GitHub` 的既有干净历史快进提交；不合并或推送研发仓库历史，不强推。
- 内部产品构建源码：`c4bd2f9094fc7f8340b7e7c7653de25457c20714`；原阶段交付记录 `c718529`。内部提交仅作来源映射，不声明能在 GitHub 解析。
- 已发布 tag：`v0.3.0-software-candidate`；Release ID `405702291`，`draft=false` / `prerelease=true`。
- 归档 `D1Env-0.3.0-macos-aarch64.tar.gz`：167626300 bytes；SHA-256 `e2866d49ff3e795ede21f6350a8edca97987e37fc26320fb542fb8859daff6ad`。
- 配套发布 `SHA256SUMS.txt` 与 `START-HERE.md`；不上传整个 outputs、解压运行时副本或工作目录。

## 发布检查

发布副本须去敏测试 CSRF 与个人临时路径，保留 RED/失败断言和真实退出码。受影响证据索引重新计算大小与摘要，并标记 `publication_redacted=true`，保留本次去敏前文件摘要。凭据不进入发布新提交。

本轮改动为介绍与发布记录，不更改产品代码或提升阶段证据等级。0.3.0 的软件测试、真实截图和未验证范围仍见 [M3-setup-summary](M3-setup-summary.md) / [独立审查](M3-setup-review.md)。新机首次安装、Linux、D1 SDK/硬件、发行签名/公证与全部内置动态库许可仍未验收；源码/候选上传不等于正式通用发行。

发布前后分别核对源码文件集、包内模块与来源锁、索引摘要、会话/个人路径、远端 head/README/About、Release 固定提交及附件大小/摘要。实际结果见下文及 [发布证据索引](evidence/github-0.3.0/INDEX.json)。

## 发布前实际核验

- 沿用现有干净发布历史，main 起点 `4e45ab29bc91634d86eee954007998d20e24c36c`；远端 fetch 确认一致。
- 导出481个受版本控制的文件，排除整个研发Git历史、运行状态、参考源码与安装器。115个产品/测试/前端/容器/配置/脚本文件与研发源逐字节一致；包内29个Python模块与发布副本一致。
- 发布日志替换7处测试CSRF值、16处mac临时路径，8个证据索引条目更新大小/SHA并记录去敏前摘要；再次去敏预览0项。保留原FAIL/RED与断言，不改原始研发日志。
- 当前481文件与旧发布历史143个blob的高置信凭据/个人路径模式命中0；有限模式扫描不保证任意秘密绝不存在。
- README/START_HERE/packaging本地链接存在，CLI帮助实际列出文档中的所有命令；GitHub Markdown API渲染成功，主要章节和真实截图引用存在。
- 实际归档大小与SHA核对一致；新增候选并不提升Linux、首次安装或硬件证据。
- 本轮没有功能改动，没有重跑Docker或机器人；阶段测试计数引用对应冻结日志，不伪称本轮新增硬件/安装PASS。

## 发布后实际核验

- GitHub main 已取得产品提交 `0ca407e8c94964118090a009b167a831fd543fd1`；远端 README、START_HERE、pyproject 和实际软件界面截图逐字节匹配发布副本。
- About 与 topics 已核对：`deployment`、`docker`、`environment-management`、`fastapi`、`robotics`、`ros2`、`typescript`。仓库保持 PRIVATE，默认分支 main。
- 新候选 tag 与 Release 的固定提交一致；按 tag 可读取已发布 Release。三个附件均为 `uploaded`，API 大小与 SHA-256 均匹配预期。
- 实际从 GitHub 回下载完整归档，下载退出码0；167626300 bytes 与 SHA-256 均匹配。只读检查2356个清单条目的内容/链接/权限及29个Python模块，全部匹配，没有执行下载包内程序。
- 旧 `v0.1.0-mock-m2` 仍固定 `644ec07375b2840bf86912c3373a7089846957a5`；旧 Release ID `404907306`、ZIP ID `615965775`、1278562 bytes 与 SHA-256 `4e1073a76632fd6a1e76110271f24f80a6c70bb1e18ac34f7f0db77cda1295d3` 均保持。旧校验附件另经实际读取核对。
- 独立只读审查确认发布状态、附件、旧版本、简介边界；详见 [最终发布审查](evidence/github-0.3.0/final-audit.md)。历史报告中的“尚未推送”保留其当时状态；当前发布状态以本报告和发布后证据为准。

| 附件 | Bytes | SHA-256 |
|---|---:|---|
| `D1Env-0.3.0-macos-aarch64.tar.gz` | 167626300 | `e2866d49ff3e795ede21f6350a8edca97987e37fc26320fb542fb8859daff6ad` |
| `SHA256SUMS.txt` | 99 | `1325ad342c722e9f929581d9c81ce721049fc219d3bfad072e5b52fc09e37d88` |
| `START-HERE.md` | 2229 | `5529ca170a831f1e4df26360f930b5778bf08d7044ae89de779210f2c9b67a2a` |

`START-HERE.md` 是本轮重新组织的 GitHub 下载入口，链接指向固定候选 tag；其来源为本轮 `START_HERE.md`，与冻结归档内较早的入口说明分别记录。完整运行归档未修改。

## 本轮实际命令与结果

下列操作在项目目录执行；源码推送的工作目录为 `outputs/D1Env-GitHub`。辅助核验脚本位于忽略的工作目录，仅读取文件/API，结果另存入公开证据。

| 实际命令 | 退出码 | 结果 |
|---|---:|---|
| `git push origin main` | 0 | 快进更新源码与介绍，未强推 |
| `gh release create v0.3.0-software-candidate outputs/D1Env-M3-Setup/D1Env-0.3.0-macos-aarch64.tar.gz work/github-release-0.3.0/SHA256SUMS.txt work/github-release-0.3.0/START-HERE.md --repo GARERYIES/D1Env --target 0ca407e8c94964118090a009b167a831fd543fd1 --title 'D1Env 0.3.0 · Environment Preparation & ROS Deployment Preview' --notes-file work/github-release-0.3.0/RELEASE-NOTES.md --draft --prerelease --latest=false` | 0 | 创建草稿并上传三个附件，上传完成后再发布 |
| `gh api repos/GARERYIES/D1Env/releases/assets/618535104 -H 'Accept: application/octet-stream' > work/github-release-0.3.0/downloaded-D1Env-0.3.0-macos-aarch64.tar.gz` | 0 | 实际完整回下载 |
| `python3 work/github-release-0.3.0/verify-downloaded.py` | 0 | 归档摘要、2356条清单与29个模块全部通过 |
| `gh api --method PATCH repos/GARERYIES/D1Env/releases/405702291 -F draft=false -F prerelease=true -f make_latest=false --jq '{id,tag_name,target_commitish,draft,prerelease,html_url,published_at}'` | 0 | 发布软件候选，保持预发布状态 |
| `python3 work/github-release-0.3.0/verify-published.py` | 0 | 新旧tag、附件、About、topics和私有权限断言全部通过 |

上述发布核验没有失败或跳过的断言。上传期间按 tag 查询草稿曾返回 HTTP404 / exit1，随后按 Release ID/列表核到草稿；未因此重复创建，发布后同一按 tag 查询退出码0。软件功能测试沿用冻结阶段证据，本轮未重跑；Linux、全新安装、下载隔离、签名/公证、完整动态库许可与机器人范围仍为未验证/blocked，未计入通过。
