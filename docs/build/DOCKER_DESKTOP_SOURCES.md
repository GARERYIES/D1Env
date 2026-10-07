# Docker Desktop 首次准备来源与边界

核验日期：2026-10-07，Asia/Shanghai。候选锁见 `DOCKER_DESKTOP_LOCK.json`。本记录只核查来源、下载和签名，不安装、启动或停止 Docker，不创建容器，不接入机器人。

按已采用 IOENV 蓝图，此步骤是环境层的部署前置准备，复用已有运行环境并补齐缺失时的安装体验。Docker 安装/daemon 可访问、镜像准备、容器运行、ROS 消息和 D1 功能就绪继续分层记录；安装器或 Docker 启动成功不能替代业务检查。

## 固定来源

| 项目 | 官方来源与实际核对 |
|---|---|
| 版本 | [Docker 官方发行说明](https://docs.docker.com/desktop/release-notes/#4800)：4.80.0，2026-06-29；Apple 芯片链接实际指向 build 232116 |
| DMG | [官方 arm64 DMG](https://desktop.docker.com/mac/main/arm64/232116/Docker.dmg)：实际 HTTPS HEAD 为 HTTP 200、575,775,824 bytes；不是由 `latest` URL 推断 |
| 摘要 | [官方 checksums.txt](https://desktop.docker.com/mac/main/arm64/232116/checksums.txt)：实际下载 77 bytes、HTTP 200；`41d0e5c61327a877f229a1e1158d056d37f003902189fd5e0ba8629619c1819f` 对应 `Docker.dmg` |
| 安装与首次许可 | [Docker 官方 Mac 安装](https://docs.docker.com/desktop/setup/install/mac-install/)与[服务协议](https://www.docker.com/legal/docker-subscription-service-agreement/) |
| 权限与 socket | [Docker 官方 Mac 权限说明](https://docs.docker.com/desktop/setup/install/mac-permission-requirements/) |

官方页面在核验时已有 4.94.0（2026-10-05）。本候选固定已有软件测试使用的 4.80.0，不称它为最新版，也不自动升级已有安装。候选所需版本选择和后续安全更新仍需要单独验收。

`retrieval_status=verified` 表示固定版本、官方下载链接、发布摘要与实际 HEAD 大小已经核对。完整下载、DMG 完整性、DMG 内 app 签名各自记在 `download_verification`，不能用 metadata verified 代替这些结果。源码提交为 null/blocked：未取得与该专有应用发行版对应的完整源代码提交；binary SHA 不是源码提交。

## 用户许可与权限衔接

Docker 首次运行展示其协议；D1Env 只链接官方协议和衔接该界面，用户自己确认许可与适用订阅。代码不得自动选择 Accept、传入 `--accept-license`、购买订阅或通过账号登录。官方页面说明不同用途/组织有不同许可条件，本工具不替用户判断免费资格。

Docker Mac 安装既有交互方式也有命令行安装方式。官方 `--user` 会配置系统 symlink/helper 等，不能把它当作无副作用安装选项。本候选应复用已有安装，仅在不存在时使用固定 DMG 的受控安装流程；不得覆盖已有 Docker.app、改 Docker 偏好、shell profile、系统 socket 或用户资源。受保护目录的授权由 macOS 交互和用户控制，不收集管理员密码。

本项目采取 **官方按需下载，不打包 Docker Desktop 安装器**。没有据官方可下载就声称第三方再分发获许可；Docker DMG 不应进入 Git 或 D1Env 发行压缩。

无特权设置可仅使用 `desktop-linux` context 与用户 Unix socket，而不创建 `/var/run/docker.sock`。因此新安装路径不能为了保持旧 `default` 行为去改系统 socket；运行层必须验证本机 Unix endpoint，禁止远程 context 或自由 `DOCKER_HOST`。

现有 app 实际包含 `Contents/Resources/bin/docker` 和 `Contents/Resources/cli-plugins/docker-compose`。不要求用户另装 CLI、Compose 或手改 PATH；这些路径仅在 app 来源和权限验证后可被信任。

## 实际只读 app 核验

已经存在的 `/Applications/Docker.app`：实际 `CFBundleShortVersionString=4.80.0`、`CFBundleVersion=232116`、架构 arm64、`LSMinimumSystemVersion=14.0`、bundle ID `com.docker.docker`、Team ID `9BNSXJN65R`。14.0 是二进制声明的最低门槛，不能代替 Docker 当前支持版本政策；本轮产品已测 macOS 26.6.2，其他 Mac 环境未因此获得 PASS。

实际命令与退出码：

| 命令 | exit | 范围 |
|---|---:|---|
| `curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 --head <固定 DMG URL>` | 0 | HEAD 200，575,775,824 bytes |
| 同样 TLS 参数实际下载 `<固定 checksum URL>` | 0 | HTTP 200，77 bytes，发布摘要已核对 |
| `/usr/bin/codesign --display --verbose=4 /Applications/Docker.app` | 0 | 上述版本对应已有 app 的签名身份；display 本身不证明有效性 |
| `/usr/bin/codesign --verify --deep --strict --verbose=2 -R '=identifier "com.docker.docker" and anchor apple generic and certificate leaf[subject.OU] = "9BNSXJN65R"' /Applications/Docker.app` | 0 | 已有 app on-disk、Designated Requirement、显式厂商身份均通过 |
| `/usr/sbin/spctl --assess --type execute --verbose=4 /Applications/Docker.app` | 0 | 已有 app `accepted`，`source=Notarized Developer ID` |
| `/usr/bin/xcrun stapler validate /Applications/Docker.app` | 65 | 已有 app 无 stapled ticket；不能将此项写成 PASS；在线 Gatekeeper assessment 已另行通过 |
| 初次 codesign `-R` 缺少 inline 字符串前导 `=` | 1 | 命令格式错误，误按文件读取；修正后才通过，原错误证据保留 |
| `python3` 来源 metadata 断言 | 0 | 官方 release-section 链接/版本、checksum 文本、HEAD 大小一致 |
| 固定 DMG URL 的 `curl --range 575000000-575775823` | 0 | 实际 HTTP 206、775,824 bytes、正确 Content-Range；只证明官方源当前支持 Range，不是产品断点恢复验收 |

证据在私有 `work/setup-evidence/`，锁中记录取得文件的 SHA/大小。没有关闭 TLS 验证。已经安装 app 的上述验证不等于下载 DMG 验证，更不等于首次安装验收。

## 完整下载与只读 DMG 核验

完整官方归档实际取得，curl exit 0、HTTP 200，575,775,824 bytes；SHA-256 与上列官方值一致。`download_verification.status=verified` 现在表示下表的实际来源检查，仍不表示软件已安装或启动。

实际 `.venv/bin/python work/setup-evidence/verify-docker-dmg-readonly.py` exit 0。脚本先核固定 bytes/SHA，再核 DMG 结构，只读挂载并核查固定 app；不执行内部 install/Docker，finally 仅卸载本次自己的挂载。

| 实际子命令/断言 | exit | 证据与范围 |
|---|---:|---|
| `hdiutil verify <完整固定 DMG>` | 0 | 16.588s，介质结构完整性，不单独代表厂商身份 |
| `hdiutil attach -readonly -nobrowse -noautoopen -mountpoint <本次私有目录> -plist <完整 DMG>` | 0 | 0.451s；仅本次 DMG 只读挂载 |
| 挂载 app 的 Info.plist 断言 | 0 | 4.80.0 / 232116、`com.docker.docker`、14.0 与固定值一致 |
| 挂载 app 的 `codesign --verify --deep --strict` 加上表显式厂商 requirement | 0 | 24.520s，厂商身份/完整性均验证；不是只执行 display |
| 挂载 app 的 `codesign --display --verbose=4` 与身份/arm64 断言 | 0 | 0.063s，Team ID `9BNSXJN65R`、bundle ID 与 arm64 一致 |
| 挂载 app 的 `spctl --assess --type execute --verbose=4` | 0 | 25.684s，实际 `accepted` / `Notarized Developer ID`；没有绕过 Gatekeeper |
| `xcrun stapler validate <完整 DMG>` | 0 | DMG 的 stapled ticket 实际通过；与已装 app 本身无 stapled ticket 的 exit 65 分开 |
| `hdiutil detach <本次挂载目录>` | 0 | 本次挂载已卸，复核其中 Docker.app 不再存在；未处理其他挂载 |
| 用发行包同一 Python 3.10.20、`-I -S -B` 实际 HTTPS HEAD | 0 | 当前 Mac 默认 TLS 下 HTTP 200、固定 final URL/size；不要求用户安装 curl/Xcode，不是产品下载服务运行验收 |

完整命令、各子命令退出码和结果分别在 `docker-dmg-readonly-commands.json`、`docker-dmg-readonly-results.json`、`docker-dmg-readonly-verification.log`；锁保留其实际 SHA/大小。下载 DMG 仅位于忽略的研发工作目录，不进入 Git 或用户发行包。

首次安装/首次许可/系统授权的真实新机路径、下载安装中断恢复、目标 app 路径竞态和故障行为须由本轮实现测试分别报告。来源核验不把这些未执行内容算通过。Linux 安装、D1 SDK、真机和运动不在本记录范围。
