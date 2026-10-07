# GitHub 最终发布独立只读核对

核对时间：2026-10-07T20:09:40.917854+08:00

结论：本轮源码与0.3.0软件候选发布的远端状态核对通过。旧M2保留；仓库仍PRIVATE；没有D1硬件或通用正式发行声明。后续核验文档提交可以推进main，不应移动已发布产品tag。

## 新版本

实际API确认Release id405702291，tag `v0.3.0-software-candidate`，draft=false、prerelease=true。tag ref为commit且实际SHA、Release target_commitish均为 `0ca407e8c94964118090a009b167a831fd543fd1`。

| 附件 | id | bytes | API SHA-256 | 状态 |
|---|---:|---:|---|---|
| D1Env-0.3.0-macos-aarch64.tar.gz | 618535104 | 167626300 | e2866d49ff3e795ede21f6350a8edca97987e37fc26320fb542fb8859daff6ad | uploaded |
| SHA256SUMS.txt | 618535103 | 99 | 1325ad342c722e9f929581d9c81ce721049fc219d3bfad072e5b52fc09e37d88 | uploaded |
| START-HERE.md | 618535101 | 2229 | 5529ca170a831f1e4df26360f930b5778bf08d7044ae89de779210f2c9b67a2a | uploaded |

大包API大小与摘要等于冻结候选的期望值；父执行者另外完成实际回下载、2356清单条目/29Python模块匹配，本审查未重复下载168MB归档，也不把父执行者的执行写成独立重跑。

本审查实际读取远端START-HERE附件，摘要/大小与API一致，并与实际发布来源 `work/github-release-0.3.0/START-HERE.md` 逐字节相同。它是使用固定GitHub tag链接的本轮发布入口；与冻结包内旧入口不同是有意更新。SHA256SUMS API摘要与本地候选文件实际摘要相同。

## 旧M2保持

旧tag `v0.1.0-mock-m2`仍为commit `644ec07375b2840bf86912c3373a7089846957a5`。Release id404907306仍draft=false/prerelease=true，target_commitish未变。旧ZIP保持1278562bytes、SHA `4e1073a76632fd6a1e76110271f24f80a6c70bb1e18ac34f7f0db77cda1295d3`；旧checksum保持82bytes、SHA `b67eb49ec287a2e223f98428ad3086ca325313fc922aa13478c5f74229f124b8`；均uploaded。与之前独立post审计和历史实下载记录一致。

## 私有状态与介绍

实际仓库GARERYIES/D1Env仍private=true、默认main。About准确称profile-driven environment manager、Chinese web UI、Docker lifecycle和scoped ROS software checks、Apple Silicon preview。远端README blob仍 `13f777b33a704bfeb88ddc30dba3b8674ef4960a`，与此前已核对的正文一致；新Release已公开于本private仓库的授权用户，因此README新版本下载链接不再处于草稿过渡状态。

Release/README/START-HERE明确默认MOCK、环境准备和ROS软件范围、真实机器人禁用/UNKNOWN/null/无运动；保留新机安装/系统授权、Linux/Intel Mac、SDK硬件、发行签名/公证/下载隔离及完整动态库许可未验收。未把Docker官方包签名或软件测试成功当作D1/全新系统验收。

## 方法与限制

只读gh api核对仓库、新旧Release与tag ref、README、新START-HERE小附件；只读本地发布入口/校验文件。调用均exit0。只新增本报告，未改Git、资产、产品或其他报告，未运行Docker/SDK/机器人。已发布产品tag仍固定0ca407e8c94964118090a009b167a831fd543fd1。
