# GitHub 0.3.0 软件候选更新

日期：2026-10-07。用户明确授权更新 GitHub 源码、仓库简介与 README，并要求参考 IOENV 的用语及组织结构。本次授权允许发布已有软件候选，不包含 Docker 镜像仓库发布、SDK、机器人或系统修改。

## 发布状态

准备阶段：尚未执行本轮 push、About 修改或新 Release 发布。发布后的实际提交、资产与校验结果将在本报告补充。

## 内容与组织

- README 从研发时间线改为项目概述、Features、Quick Start、Commands、Configuration、Architecture、Compatibility & Validation、Development、Notes、Roadmap、Documentation、License。
- 原 README 与交接入口分别保留为 `README-HISTORY.md`、`START_HERE-HISTORY.md`；原始设计、计划和阶段报告保留。
- 术语与职责沿用 Environment definition、Container lifecycle、Feature startup & checks；D1Env 独立实现部署引擎，不声称上游提供现成 D1 适配。
- 参考实际官方 [IOEnv CLI README](https://github.com/ioai-tech/ioenv_cli/blob/ec1f8354095de91a234dc31a9213ee1a410b5cc9/README.md) 和 [IO-Creed 教程](https://io-ai.tech/iocreed/en/docs/locomotion_00/)。固定源码 `ec1f8354095de91a234dc31a9213ee1a410b5cc9`；官网页面无可固定源码提交。`ioai-tech/ioenv` 未取得公开仓库，不使用猜测链接。

目标 About：

> A profile-driven environment manager for D1 robotics development, with a Chinese web UI, Docker lifecycle orchestration and scoped ROS software checks. Apple Silicon preview.

## 源码与候选资产

- 仓库：[GARERYIES/D1Env](https://github.com/GARERYIES/D1Env)，本轮开始时实际 private、main；保留可见性和旧 `v0.1.0-mock-m2`。
- 仅从 `outputs/D1Env-GitHub` 的既有干净历史快进提交；不合并或推送研发仓库历史，不强推。
- 内部产品构建源码：`c4bd2f9094fc7f8340b7e7c7653de25457c20714`；原阶段交付记录 `c718529`。内部提交仅作来源映射，不声明能在 GitHub 解析。
- 候选 tag：`v0.3.0-software-candidate`，预发布，不标为正式稳定版。
- 归档 `D1Env-0.3.0-macos-aarch64.tar.gz`：167626300 bytes；SHA-256 `e2866d49ff3e795ede21f6350a8edca97987e37fc26320fb542fb8859daff6ad`。
- 配套发布 `SHA256SUMS.txt` 与 `START-HERE.md`；不上传整个 outputs、解压运行时副本或工作目录。

## 发布检查

发布副本须去敏测试 CSRF 与个人临时路径，保留 RED/失败断言和真实退出码。受影响证据索引重新计算大小与摘要，并标记 `publication_redacted=true`，保留本次去敏前文件摘要。凭据不进入发布新提交。

本轮改动为介绍与发布记录，不更改产品代码或提升阶段证据等级。0.3.0 的软件测试、真实截图和未验证范围仍见 [M3-setup-summary](M3-setup-summary.md) / [独立审查](M3-setup-review.md)。新机首次安装、Linux、D1 SDK/硬件、发行签名/公证与全部内置动态库许可仍未验收；源码/候选上传不等于正式通用发行。

发布前后分别核对源码文件集、包内模块与来源锁、索引摘要、会话/个人路径、远端 head/README/About、Release 固定提交及附件大小/摘要。实际结果在下方记录。

## 发布前实际核验

- 沿用现有clean main，起点 `4e45ab29bc91634d86eee954007998d20e24c36c`；远端fetch确认一致。
- 导出481个tracked文件，排除整个研发Git历史、运行状态、参考源码与安装器。115个产品/测试/前端/容器/配置/脚本文件与研发源逐字节一致；包内29个Python模块与发布副本一致。
- 发布日志替换7处测试CSRF值、16处mac临时路径，8个证据索引条目更新大小/SHA并记录去敏前摘要；再次去敏预览0项。保留原FAIL/RED与断言，不改原始研发日志。
- 当前481文件与旧发布历史143个blob的高置信凭据/个人路径模式命中0；有限模式扫描不保证任意秘密绝不存在。
- README/START_HERE/packaging本地链接存在，CLI帮助实际列出文档中的所有命令；GitHub Markdown API渲染成功，主要章节和真实截图引用存在。
- 实际归档大小与SHA核对一致；新增候选并不提升Linux、首次安装或硬件证据。
- 本轮没有功能改动，没有重跑Docker或机器人；阶段测试计数引用对应冻结日志，不伪称本轮新增硬件/安装PASS。
