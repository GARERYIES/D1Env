# ROS 软件探针来源与验证边界

本镜像仅验证两个受限容器中的真实 ROS 2 消息通信。没有厂商 SDK、机器人连接、传感器、运动或急停接口。Mac Docker Desktop 的 Linux aarch64 daemon 已完成实际构建及内部 bridge 集成；Ubuntu x86_64 本机集成仍为 NOT_RUN。

## 固定来源

基础镜像来自 [Docker Official ROS](https://hub.docker.com/_/ros)，候选 tag 为 `humble-ros-core`。2026-10-07 实际查询 registry 得到 index digest `sha256:6892c5a0fec6c3bddc4cea502c7623f88988d7b1442419a23c685757249c7437`，选择并实际拉取的 Linux arm64/v8 平台 digest 为 `sha256:5d8bdefcfb553802cca2fff87233f0c0adfbbd50e87e7c64c9af9a098250e6b1`。Dockerfile 固定到后者，不依赖可变 tag。现有用户镜像未被当作受信来源，也没有删除或发布镜像。

官方 registry 的 source/revision annotation 指向 [osrf/docker_images 固定提交](https://github.com/osrf/docker_images/tree/58af41813ba67f611943c35c551387d652fcdbde/ros/humble/ubuntu/jammy/ros-core)。实际获取并保留了该提交的 Dockerfile 及 Apache-2.0 LICENSE；SHA256 在 `ROS_PROBE_LOCK.json`，许可证原文在 `licenses/OSRF-Docker-Images-APACHE-2.0.txt`。没有重新执行上游 apt 构建配方；此处依赖锁由不可变基础镜像及实际包清单构成。

基础镜像已含 `rclpy` 和 `std_msgs`，探针 Dockerfile 没有新增 apt/pip 包。实际基础镜像与最终候选镜像的 **389 个已安装 dpkg 包**和 **147 个 ROS package.xml**完全相同。精确版本、架构、版权文件路径及 SHA256、ROS 清单许可证保存在 `ROS_PROBE_PACKAGES.json`。关键版本包括：

| 包 | 实际版本 |
| --- | --- |
| python3 | 3.10.6-1~22.04.1 |
| ros-humble-rclpy | 3.3.22-1jammy.20260907.232408 |
| ros-humble-std-msgs | 4.9.2-1jammy.20260907.211527 |
| ros-humble-fastrtps | 2.6.12-1jammy.20260725.060440 |
| ros-humble-rmw-fastrtps-cpp | 6.2.10-1jammy.20260907.212405 |
| ros-humble-ros-core | 0.10.0-1jammy.20260908.041717 |

各包许可证是各包自身的许可证，不能由 Docker 源码的 Apache-2.0 统一替代。61 个包没有可提取的 `License:` 标头；其中 `python3-rospkg-modules` 在标准 dpkg 文档路径没有版权文件，清单明确记录 null 和原因。原有镜像内版权文本仍保留；机器提取不是完整法律审查。本项目尚未选择整体源码许可证，此记录没有擅自给新增探针源码分配许可证，也没有声称已完成再分发许可审查。上述缺失、项目许可选择和再分发审查均在 lock 的许可部分列为 `partial_blocked`，不影响已观察到的软件通信证据，但不支持“已完成发布许可审查”的结论。

## 固定入口与消息证据

镜像入口只能接受 `publisher`、`subscriber`、`idle` 三个角色，运行用户为 `10001:10001`。`D1ENV_RUN_ID` 必须是本次作业的 32 位小写十六进制 ID。发布端只向 `/d1env/test/probe` 发送 `std_msgs/String`，内容为本次 `run_id`、递增 `seq`、实际 Unix 秒 `sent_at`。

订阅端使用真实 `rclpy` 回调接收消息，仅接受匹配作业、有限且新鲜的时间戳、严格递增的序号和准确字段集合；状态原子写入 `/tmp/d1env-status.json`。固定读取命令为 `python3 /opt/d1env/read_status.py`，输出 `run_id`、`publisher_id`、`sample_count`、`last_sequence`、`last_sent_at`、`last_received_at`。文件缺失或无发布端时，样本为 0，发布身份与时间为 null。就绪判定仍需执行器确认至少 3 条真实样本及其新鲜度，容器 running 不是就绪。

内部 bridge 的首次真实测试出现发现失败：发布端只看到自身发布者，订阅端只看到自身订阅者，两端没有对端 endpoint。证据保留在 `work/evidence/m3-image-failure-*.json`。不能据此断言根因只是共享内存。依据实际安装的 Fast DDS 2.6.12 [UDP transport](https://fast-dds.docs.eprosima.com/en/v2.6.12/fastdds/transport/udp/udp.html)、[initial peers](https://fast-dds.docs.eprosima.com/en/v2.6.12/fastdds/use_cases/wifi/initial_peers.html) 和 [禁用 multicast](https://fast-dds.docs.eprosima.com/en/v2.6.12/fastdds/transport/disabling_multicast.html) 官方文档，探针改用固定的 UDPv4 transport，关闭 built-in transport，并从 Compose 的固定 `pub`/`sub` 服务别名解析对端 RFC1918 IPv4 地址，生成内部单播发现配置。无任意地址/模板输入，不需要主机网络或主机 IPC。ROS topic 与 domain ID 仅为通信配置；隔离边界仍是受限 Docker 网络及权限设置。

最终实际候选 ID 为 `sha256:52f259d5fa38acb3fd2018e1601593fc0f6ad1a85c8a968032695f9c15771a2c`。本地 tag 仅便于查看，不用于信任判定；未发布 registry。Docker 返回的是带构建证明的 OCI index digest，平台 manifest 和 config digest 分别另记在 lock，不能混为同一个摘要。

## 实际验证

- 先记录探针缺失实现的真实 RED，消息与读取契约 GREEN 35/35；发现配置新增测试 RED 为 7 failed / 35 passed，最小实现后 GREEN 42/42。
- 真实内部 bridge：非 root、只读根、cap_drop ALL、no-new-privileges、受限 CPU/内存/PID、`/tmp` noexec tmpfs，无公开端口、设备或主机目录挂载。订阅端实际收到 4 条同作业消息，序号 4，发送和接收时间均新鲜。
- 停止本次拥有的发布容器后，样本计数与时间戳保持不变，超过 5 秒进入过期；不存在假刷新。
- 发布角色改为 `idle` 后，订阅端保持 0 样本、null 发布身份和时间。此为明确的软件故障注入。
- 两轮测试仅删除验证过作业/计划归属标签的自建容器和网络，镜像保留，预先存在的容器保留。

原始命令、退出码和必要输出见 `work/evidence/m3-image-commands.jsonl`、`work/evidence/m3-image-integration-commands.jsonl`；结构化成功证据为 `work/evidence/m3-image-integration.json`。其 SHA256、源码及 Dockerfile SHA256、构建 argv、许可来源均在 `ROS_PROBE_LOCK.json`。这些证据只支持软件通信范围；不提升任何 D1 型号的支持等级。
