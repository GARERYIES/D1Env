# D1Env 诊断报告 · 真实软件测试

Docker/ROS 软件通信测试证据，未连接真机。

模式：software_test；验证范围：software

真实主机观测的来源为 local_probe；它不提高作业验证范围。

```json
{
  "schema_version": 1,
  "mode": "software_test",
  "verified_scope": "software",
  "job": {
    "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
    "plan_id": "07c01d6de357f06b8b56271bcb7671b062e9627938e4e2772d4c80ac90990085",
    "target_id": "local",
    "mode": "software_test",
    "state": "FAILED",
    "verified_scope": "software",
    "current_operation_id": "verify",
    "created_at": "2026-10-07T05:37:30.662135Z",
    "updated_at": "2026-10-07T05:37:50.840307Z",
    "error_code": "DOCKER_TIMEOUT",
    "current_software_ready": null,
    "current_health_evidence": {}
  },
  "checks": [
    {
      "code": "PLATFORM",
      "status": "PASS",
      "reason": "Linux Docker 软件测试平台已取得（未接真机）",
      "remediation": "检查本地 Docker Desktop/Engine；Mac 软件测试不替代全新 Ubuntu 安装验收",
      "origin": "local_probe",
      "observed_at": "2026-10-07T05:37:52.722532Z",
      "evidence": {
        "host_os": "Darwin",
        "docker_os": "linux",
        "architecture": "aarch64"
      }
    },
    {
      "code": "DOCKER",
      "status": "PASS",
      "reason": "本机 Docker 入口只读检测通过",
      "remediation": "检查本地 Docker 安装、服务及权限；本工具不会改权限或启动 daemon",
      "origin": "local_probe",
      "observed_at": "2026-10-07T05:37:52.722532Z",
      "evidence": {
        "available": true,
        "accessible": true,
        "error": null,
        "context": "fixed local Unix entry"
      }
    },
    {
      "code": "COMPOSE",
      "status": "PASS",
      "reason": "Compose 版本只读检测通过",
      "remediation": "MOCK 不需要 Compose；真实容器验证在 M3",
      "origin": "local_probe",
      "observed_at": "2026-10-07T05:37:52.722532Z",
      "evidence": {
        "available": true
      }
    },
    {
      "code": "DISK",
      "status": "PASS",
      "reason": "本地项目可用磁盘检查（软件阈值 100 MiB）",
      "remediation": "确认项目磁盘空间；不自动清理数据",
      "origin": "local_probe",
      "observed_at": "2026-10-07T05:37:52.722532Z",
      "evidence": {
        "free_bytes": 148275453952
      }
    },
    {
      "code": "GPU",
      "status": "SKIPPED",
      "reason": "CPU 演示与基础诊断不需要 GPU",
      "remediation": "无需为本轮安装显卡驱动",
      "origin": "local_probe",
      "observed_at": "2026-10-07T05:37:52.722532Z",
      "evidence": {
        "available": null
      }
    },
    {
      "code": "NETWORK",
      "status": "SKIPPED",
      "reason": "只枚举本机接口，不探测任何机器人或远端",
      "remediation": "本轮无需配置网卡",
      "origin": "local_probe",
      "observed_at": "2026-10-07T05:37:52.722532Z",
      "evidence": {
        "interfaces": [
          "lo0",
          "gif0",
          "stf0",
          "anpi0",
          "anpi1",
          "en2",
          "en3",
          "en1",
          "en4",
          "bridge0",
          "utun0",
          "utun1",
          "utun2",
          "utun3",
          "utun4",
          "utun5",
          "utun6",
          "utun7",
          "utun8",
          "utun9",
          "utun11",
          "utun12",
          "utun13",
          "utun14",
          "utun10",
          "ap1",
          "en0",
          "awdl0",
          "llw0"
        ]
      }
    },
    {
      "code": "ROBOT",
      "status": "UNKNOWN",
      "reason": "未连接机器人，未取得电量、姿态或传感器数据",
      "remediation": "真实只读适配属于 M4；不要用演示结果判断真机状态",
      "origin": "local_probe",
      "observed_at": "2026-10-07T05:37:52.722532Z",
      "evidence": {
        "battery_percent": null,
        "pose": null
      }
    }
  ],
  "events": [
    {
      "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
      "seq": 1,
      "timestamp": "2026-10-07T05:37:30.662346Z",
      "event_type": "state",
      "operation_id": null,
      "mode": "software_test",
      "origin": "docker",
      "message": "软件通信测试作业已创建，未连接真机。",
      "evidence": {
        "state": "PLANNED"
      }
    },
    {
      "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
      "seq": 2,
      "timestamp": "2026-10-07T05:37:30.664792Z",
      "event_type": "state",
      "operation_id": "preflight",
      "mode": "software_test",
      "origin": "docker",
      "message": "软件测试 正在执行：复核本地 Docker 与工件身份。",
      "evidence": {
        "state": "PREFLIGHT"
      }
    },
    {
      "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
      "seq": 3,
      "timestamp": "2026-10-07T05:37:30.666177Z",
      "event_type": "operation_started",
      "operation_id": "preflight",
      "mode": "software_test",
      "origin": "docker",
      "message": "软件测试 开始：复核本地 Docker 与工件身份。",
      "evidence": {}
    },
    {
      "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
      "seq": 4,
      "timestamp": "2026-10-07T05:37:30.845309Z",
      "event_type": "operation_succeeded",
      "operation_id": "preflight",
      "mode": "software_test",
      "origin": "docker",
      "message": "本地 Docker/Compose 及 Linux CPU 运行时已检查；Docker 操作权仍属于高权限信任边界。",
      "evidence": {
        "docker_preflight": true
      }
    },
    {
      "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
      "seq": 5,
      "timestamp": "2026-10-07T05:37:30.846530Z",
      "event_type": "state",
      "operation_id": "acquire",
      "mode": "software_test",
      "origin": "docker",
      "message": "软件测试 正在执行：校验已有真实 ROS 镜像（不伪造下载进度）。",
      "evidence": {
        "state": "ACQUIRING"
      }
    },
    {
      "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
      "seq": 6,
      "timestamp": "2026-10-07T05:37:30.847176Z",
      "event_type": "operation_started",
      "operation_id": "acquire",
      "mode": "software_test",
      "origin": "docker",
      "message": "软件测试 开始：校验已有真实 ROS 镜像（不伪造下载进度）。",
      "evidence": {}
    },
    {
      "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
      "seq": 7,
      "timestamp": "2026-10-07T05:37:30.901785Z",
      "event_type": "operation_succeeded",
      "operation_id": "acquire",
      "mode": "software_test",
      "origin": "docker",
      "message": "已核对本地可信镜像的实际 ID 和 CPU 架构；没有下载或删除用户镜像。",
      "evidence": {
        "artifact_verified": true,
        "image_id": "sha256:52f259d5fa38acb3fd2018e1601593fc0f6ad1a85c8a968032695f9c15771a2c"
      }
    },
    {
      "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
      "seq": 8,
      "timestamp": "2026-10-07T05:37:30.903062Z",
      "event_type": "state",
      "operation_id": "configure",
      "mode": "software_test",
      "origin": "docker",
      "message": "软件测试 正在执行：生成本作业的受限容器配置。",
      "evidence": {
        "state": "CONFIGURING"
      }
    },
    {
      "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
      "seq": 9,
      "timestamp": "2026-10-07T05:37:30.903658Z",
      "event_type": "operation_started",
      "operation_id": "configure",
      "mode": "software_test",
      "origin": "docker",
      "message": "软件测试 开始：生成本作业的受限容器配置。",
      "evidence": {}
    },
    {
      "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
      "seq": 10,
      "timestamp": "2026-10-07T05:37:30.905866Z",
      "event_type": "operation_succeeded",
      "operation_id": "configure",
      "mode": "software_test",
      "origin": "docker",
      "message": "软件测试配置已生成；仅使用内部网络、非 root 用户及本项目资源。",
      "evidence": {
        "compose_generated": true,
        "host_mounts": false,
        "public_ports": false
      }
    },
    {
      "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
      "seq": 11,
      "timestamp": "2026-10-07T05:37:30.906876Z",
      "event_type": "state",
      "operation_id": "start",
      "mode": "software_test",
      "origin": "docker",
      "message": "软件测试 正在执行：启动真实 ROS 软件测试服务。",
      "evidence": {
        "state": "STARTING"
      }
    },
    {
      "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
      "seq": 12,
      "timestamp": "2026-10-07T05:37:30.907480Z",
      "event_type": "operation_started",
      "operation_id": "start",
      "mode": "software_test",
      "origin": "docker",
      "message": "软件测试 开始：启动真实 ROS 软件测试服务。",
      "evidence": {}
    },
    {
      "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
      "seq": 13,
      "timestamp": "2026-10-07T05:37:31.681563Z",
      "event_type": "operation_succeeded",
      "operation_id": "start",
      "mode": "software_test",
      "origin": "docker",
      "message": "本项目软件容器已创建；尚须验证真实 ROS 接收证据。",
      "evidence": {
        "containers_started": true,
        "software_ready": false
      }
    },
    {
      "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
      "seq": 14,
      "timestamp": "2026-10-07T05:37:31.682818Z",
      "event_type": "state",
      "operation_id": "verify",
      "mode": "software_test",
      "origin": "docker",
      "message": "软件测试 正在执行：故障注入：无发布者检查。",
      "evidence": {
        "state": "VERIFYING"
      }
    },
    {
      "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
      "seq": 15,
      "timestamp": "2026-10-07T05:37:31.683489Z",
      "event_type": "operation_started",
      "operation_id": "verify",
      "mode": "software_test",
      "origin": "docker",
      "message": "软件测试 开始：故障注入：无发布者检查。",
      "evidence": {}
    },
    {
      "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
      "seq": 16,
      "timestamp": "2026-10-07T05:37:46.723590Z",
      "event_type": "operation_failed",
      "operation_id": "verify",
      "mode": "software_test",
      "origin": "docker",
      "message": "ROS 状态读取失败；检测证据包含实际退出码/超时/取消；请检查本地 Docker 后重试。",
      "evidence": {
        "software_ready": false,
        "fault_injection": true,
        "freshness_threshold_s": 5,
        "run_id": "7c3a97b12b84459da76d571dd5c9eac2",
        "publisher_id": null,
        "sample_count": 0,
        "last_sequence": null,
        "last_sent_at": null,
        "last_received_at": null,
        "stdout": "",
        "stderr": "",
        "returncode": null,
        "timed_out": true,
        "cancelled": false,
        "error_code": "DOCKER_TIMEOUT",
        "missing_evidence": [
          "software_ready"
        ]
      }
    },
    {
      "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
      "seq": 17,
      "timestamp": "2026-10-07T05:37:50.839227Z",
      "event_type": "cleanup",
      "operation_id": null,
      "mode": "software_test",
      "origin": "docker",
      "message": "软件测试资源清理盘点；用户镜像、地图和 bag 保留。",
      "evidence": {
        "removed_resources": [
          "1b1ea2dd1636ed2ccc5ab6a086edc5a842e273ca705da0f3463dec4e1f2bda09",
          "f106715a515568f5a9ebb65339d083ca3767e1732e95951ad6caf7dabc1afa0f",
          "5a6d3f878d764e7b96c50feb7611875c8b5c09ceb12cf101c3491569c5288315"
        ],
        "mode": "software_test",
        "origin": "docker",
        "verified_scope": "software",
        "resources": [
          {
            "id": "1b1ea2dd1636ed2ccc5ab6a086edc5a842e273ca705da0f3463dec4e1f2bda09",
            "kind": "container",
            "role": "pub",
            "present": false,
            "owned": false,
            "tracked": true,
            "preserved": false,
            "preserved_reason": null
          },
          {
            "id": "f106715a515568f5a9ebb65339d083ca3767e1732e95951ad6caf7dabc1afa0f",
            "kind": "container",
            "role": "sub",
            "present": false,
            "owned": false,
            "tracked": true,
            "preserved": false,
            "preserved_reason": null
          },
          {
            "id": "5a6d3f878d764e7b96c50feb7611875c8b5c09ceb12cf101c3491569c5288315",
            "kind": "network",
            "role": "network",
            "present": false,
            "owned": false,
            "tracked": true,
            "preserved": false,
            "preserved_reason": null
          }
        ],
        "untracked_resources": [],
        "inventory_complete": true,
        "remaining_owned": [],
        "preserved_resources": []
      }
    },
    {
      "job_id": "7c3a97b12b84459da76d571dd5c9eac2",
      "seq": 18,
      "timestamp": "2026-10-07T05:37:50.840398Z",
      "event_type": "state",
      "operation_id": "verify",
      "mode": "software_test",
      "origin": "docker",
      "message": "ROS 状态读取失败；检测证据包含实际退出码/超时/取消；请检查本地 Docker 后重试。",
      "evidence": {
        "state": "FAILED"
      }
    }
  ],
  "source_locks": {
    "schema_version": 1,
    "scope": "static_source_audit",
    "production_usable": false,
    "observed_at": "2026-10-06T06:43:47.693814+00:00",
    "repositories": [
      {
        "id": "ioenv_cli",
        "repository": "https://github.com/ioai-tech/ioenv_cli.git",
        "checkout_ref": "main",
        "commit_sha": "ec1f8354095de91a234dc31a9213ee1a410b5cc9",
        "observed_at": "2026-10-06T06:43:47.515242+00:00",
        "reference_directory": "work/upstream/ioenv_cli",
        "source_ids": [
          "S01",
          "S02",
          "S03",
          "S04",
          "S05",
          "S06",
          "S07"
        ],
        "paths": [
          "LICENSE",
          "README.md",
          "bin/ioenv",
          "conf.d/mirrors.env",
          "env.d/isaaclab.env",
          "env.d/mujocosim.env",
          "env.d/onboard.env",
          "ioenv.sh"
        ],
        "file_hashes": {
          "LICENSE": "305ca1ea1ab1d7ef11521eb96aa70041a24ad246c48fe7f689427235dadeb8a0",
          "README.md": "dd7b80510b3665b1e8ebbf2f72ac63c53ba87da93b893aa5ef233c7daa6a1125",
          "bin/ioenv": "9e580d837e0ee68ca7cd6958502bbb89e4ac21cee88834b2e252d28bb05001c1",
          "conf.d/mirrors.env": "3c42e86de4f43d92ddf86d427a6a1d575947c461ac453a14a98d8028fe859e07",
          "env.d/isaaclab.env": "4ebfe1d92c4f5c76f5d853b3834854b14a475cf8d3559923b3b7be0ae8ca6ceb",
          "env.d/mujocosim.env": "fa48abda598d77e82ee9bb05d05e31224897fccab0e9bd62d581b7debea2a628",
          "env.d/onboard.env": "21a364590e933b9fc447f25d2dc68053b9c28a3ba33ec40b772f59366eeda308",
          "ioenv.sh": "796472954da8ed47e19ad0cf1ae2eafe84e8494ba7f43633286e0c840d1c37b5"
        },
        "license_path": "LICENSE",
        "license_identifier": "MIT",
        "retrieval_status": "retrieved",
        "blocked_reasons": {},
        "available_tags": [],
        "git_refs_query_status": "retrieved",
        "available_releases": [],
        "releases_query_status": "retrieved",
        "binary_metadata": [],
        "transitive_dependency_audit": "not_completed",
        "hardware_status": "not_implemented",
        "evidence_logs": [
          "work/evidence/task0-ioenv_cli-commands.jsonl",
          "work/evidence/task0-ioenv_cli-tree.txt",
          "work/evidence/task0-file-hashes.json",
          "work/evidence/task0-http-commands.jsonl",
          "work/evidence/task0-curl-commands.jsonl",
          "work/evidence/task0-ioenv_cli-releases.json"
        ]
      },
      {
        "id": "humanoid_controller",
        "repository": "https://github.com/ioai-tech/humanoid_controller.git",
        "checkout_ref": "main",
        "commit_sha": "2f94ff0ebd072e255d90bbbb2122d0f1a622a0b3",
        "observed_at": "2026-10-06T06:43:47.557126+00:00",
        "reference_directory": "work/upstream/humanoid_controller",
        "source_ids": [
          "S09",
          "S10",
          "S11"
        ],
        "paths": [
          "CMakeLists.txt",
          "LICENSE",
          "README.md",
          "include/humanoid_controller/tasks/motion_tracking/LICENCE",
          "launch/mujoco.launch.py",
          "launch/real.launch.py",
          "launch/wandb.launch.py",
          "package.xml"
        ],
        "file_hashes": {
          "CMakeLists.txt": "40c463d430f1f1a02ead78a65199dfd255d9a02d9f79e5c6f49a487588eee900",
          "LICENSE": "4ea1dc2a8225bb54a0842ca3f3c77a8e54d02211b5603c38f386ef53eb1327e0",
          "README.md": "27501f0b9f2d9a9e8fa6eaf543aeea4a092763fbe64bc681fc598be7c50539d3",
          "include/humanoid_controller/tasks/motion_tracking/LICENCE": "e77307080e79d146cd55e50396a1cd80ead0eabc2d474d880ec5e3fb30a4f2e2",
          "launch/mujoco.launch.py": "9f6b0ac3f342b055819e585195b7d1b8201e9b2d9f02e8e9f6e3c5a01237fbfc",
          "launch/real.launch.py": "2ffd9b28a027f1711f969bc5acd6f3dae72b1eef0680b672e7adcd27df8b35f3",
          "launch/wandb.launch.py": "6ee35895b5c3c6c43611da29d481e953a03004f01fd38ee946acf971aeb92720",
          "package.xml": "409b6639d6dd91bc787a01d8cab6ebbd53d0416ef32d732296b616f0c75f6edb"
        },
        "license_path": "LICENSE",
        "license_identifier": "MIT",
        "retrieval_status": "retrieved",
        "blocked_reasons": {},
        "available_tags": [],
        "git_refs_query_status": "retrieved",
        "available_releases": [],
        "releases_query_status": "retrieved",
        "binary_metadata": [],
        "transitive_dependency_audit": "not_completed",
        "hardware_status": "not_implemented",
        "evidence_logs": [
          "work/evidence/task0-humanoid_controller-commands.jsonl",
          "work/evidence/task0-humanoid_controller-tree.txt",
          "work/evidence/task0-file-hashes.json",
          "work/evidence/task0-http-commands.jsonl",
          "work/evidence/task0-curl-commands.jsonl",
          "work/evidence/task0-humanoid_controller-releases.json"
        ]
      },
      {
        "id": "robot_hardware_interface",
        "repository": "https://github.com/ioai-tech/robot_hardware_interface.git",
        "checkout_ref": "main",
        "commit_sha": "fbc18ed07a1926a9f8731b182931d17e1217dbd7",
        "observed_at": "2026-10-06T06:43:47.582036+00:00",
        "reference_directory": "work/upstream/robot_hardware_interface",
        "source_ids": [
          "S12"
        ],
        "paths": [
          "CMakeLists.txt",
          "LICENSE",
          "README.md",
          "include/robot_hardware_interface/agibot/x2.hpp",
          "package.xml",
          "robot_hardware_interface.xml",
          "src/agibot/x2.cpp"
        ],
        "file_hashes": {
          "CMakeLists.txt": "6bf26e5210ed89d2f6b003f9b21f17b581ca9735c8cf859fb0c7929af72cfaa9",
          "LICENSE": "305ca1ea1ab1d7ef11521eb96aa70041a24ad246c48fe7f689427235dadeb8a0",
          "README.md": "e76a5ac817d8fc7ca688d9542d250de4d38d58ec9e3a0da60f2f849d5d8591ea",
          "include/robot_hardware_interface/agibot/x2.hpp": "b27d5840046b81908e33c92ba0260bd255f158dcd450afd917c60f674e23864d",
          "package.xml": "eda3fa5da38b8e49565e977e2eb38ec3065d255607c4eee408057057291c23bf",
          "robot_hardware_interface.xml": "4bca2a79203338a9f04fe2d77c9bdad3b0d48feac3f28b390b26d045f8239439",
          "src/agibot/x2.cpp": "8b28ddf3610acbc65c4617b49ef00876dcb4af802bf4b961a7b20d3e08ebb900"
        },
        "license_path": "LICENSE",
        "license_identifier": "MIT",
        "retrieval_status": "retrieved",
        "blocked_reasons": {},
        "available_tags": [],
        "git_refs_query_status": "retrieved",
        "available_releases": [],
        "releases_query_status": "retrieved",
        "binary_metadata": [],
        "transitive_dependency_audit": "not_completed",
        "hardware_status": "not_implemented",
        "evidence_logs": [
          "work/evidence/task0-robot_hardware_interface-commands.jsonl",
          "work/evidence/task0-robot_hardware_interface-tree.txt",
          "work/evidence/task0-file-hashes.json",
          "work/evidence/task0-http-commands.jsonl",
          "work/evidence/task0-curl-commands.jsonl",
          "work/evidence/task0-robot_hardware_interface-releases.json"
        ]
      },
      {
        "id": "agibot_D1_Edu-Ultra",
        "repository": "https://github.com/AgibotTech/agibot_D1_Edu-Ultra.git",
        "checkout_ref": "main",
        "commit_sha": "b5fe0a86094507238944ad118721376a98615ac0",
        "observed_at": "2026-10-06T06:43:47.605528+00:00",
        "reference_directory": "work/upstream/agibot_D1_Edu-Ultra",
        "source_ids": [
          "S13",
          "S14",
          "S15",
          "S16",
          "S17",
          "S23"
        ],
        "paths": [
          "LICENSE",
          "README.md",
          "README_zh.md",
          "demo/zsl-1/cpp/CMakeLists.txt",
          "demo/zsl-1w/cpp/CMakeLists.txt",
          "docs/about.md",
          "docs/api.md",
          "docs/api_lowlevel.md",
          "docs/api_zsl-1.md",
          "docs/api_zsl-1w.md",
          "docs/architecture.md",
          "docs/changelog.md",
          "docs/deploy.md",
          "docs/faq.md",
          "docs/index.md",
          "docs/sdk_download.md",
          "docs/video.md",
          "include/zsl-1/highlevel.h",
          "include/zsl-1w/highlevel.h",
          "lib/zsl-1/aarch64/libmc_sdk_zsl_1_aarch64.so",
          "lib/zsl-1/aarch64/mc_sdk_zsl_1_py.cpython-310-aarch64-linux-gnu.so",
          "lib/zsl-1/x86_64/libmc_sdk_zsl_1_x86_64.so",
          "lib/zsl-1/x86_64/mc_sdk_zsl_1_py.cpython-310-x86_64-linux-gnu.so",
          "lib/zsl-1w/aarch64/libmc_sdk_zsl_1w_aarch64.so",
          "lib/zsl-1w/aarch64/mc_sdk_zsl_1w_py.cpython-310-aarch64-linux-gnu.so",
          "lib/zsl-1w/x86_64/libmc_sdk_zsl_1w_x86_64.so",
          "lib/zsl-1w/x86_64/mc_sdk_zsl_1w_py.cpython-310-x86_64-linux-gnu.so"
        ],
        "file_hashes": {
          "LICENSE": "c0cc52d6bdaf4f5d3d0b21d6a2c16629e77d6ca3d67646fd6b91dde99b734e3a",
          "README.md": "bdbb2cf06b56ba02e91ab946e7fd0532ca97b4301e069e6cddfddbeec1df99e3",
          "README_zh.md": "cf308c5598a4b133771290e60025d2f343752677b6848b8a724633dbeeaed9fe",
          "demo/zsl-1/cpp/CMakeLists.txt": "4658b135784be9bb7ff0670d5a883742862f73b1e7679bb1b167004e2c505a06",
          "demo/zsl-1w/cpp/CMakeLists.txt": "cfbdb488be4cc66f2c3e86342d8848ff93460da873b01e0044fcc7dff3e29fc9",
          "docs/about.md": "72f52d8e473e70c4f5308e23652ec9e4d03b8b3701f9c2f83b4bd1d70f4e5323",
          "docs/api.md": "340969d0528a7949abd6f18d2cd72a54ea7bad6ee710fe4a3e04f1cc42580688",
          "docs/api_lowlevel.md": "5f3cda786caf94418baae35c3d12ca6c64ae0f6317da9653342499610072e9d9",
          "docs/api_zsl-1.md": "a3c287d9b56ce3e8d4fe7249cb7739330add9dff88a3f3c21bfbcd940e142301",
          "docs/api_zsl-1w.md": "20a2a5fcda926b7047c9cb34d88e093fecdc888afc7416370fd4bfdbe454ea63",
          "docs/architecture.md": "6decdd00c6a7e9361d65d2c1f39e4d150a66c1995747a1f324888be3e5c9dd4d",
          "docs/changelog.md": "f94432b824b95c051e2d173bb979ff2a6370475840175a55186efe15c5efff43",
          "docs/deploy.md": "6bd72ea9f6159091f095a149703baf09066398261ced188dccdf931ff0bf0e63",
          "docs/faq.md": "109b0ec4ac218145ef27140eb037e56ed824d101d1ba6fa6651d52ef525fe689",
          "docs/index.md": "6cb16914d3fd075d04f2ef1f56221d37a30609ef727c0712f23692b03345f4be",
          "docs/sdk_download.md": "fc36c255e1fa611d149e1ef8a3014b46c3e7dcc9083a9ef5ee3715f18c8bca48",
          "docs/video.md": "a2df0f75053cd6bd6bdad4642d4cd6ca3c731c94f2516b4c8b6ab29828e2f22f",
          "include/zsl-1/highlevel.h": "f82c3529451fa93f990b6018b12b3760e9a341e2cbab3107533f5aacc7fb542f",
          "include/zsl-1w/highlevel.h": "6fe1310f1ef131736f0864fd109041cd07aa98593d8aa595995d98ffc2b5d43b",
          "lib/zsl-1/aarch64/libmc_sdk_zsl_1_aarch64.so": "bacd06930fc054be431e5dd5363c38146fc69796b280356504c7157d19b3919b",
          "lib/zsl-1/aarch64/mc_sdk_zsl_1_py.cpython-310-aarch64-linux-gnu.so": "1e7b53ffeefc7914f224686f675d2caf610c4a536e660ed5099e88e548817c2c",
          "lib/zsl-1/x86_64/libmc_sdk_zsl_1_x86_64.so": "c03aa3503a6de49f50871e995221c6695d35320494e8e8d5ddde78a8b026594e",
          "lib/zsl-1/x86_64/mc_sdk_zsl_1_py.cpython-310-x86_64-linux-gnu.so": "a0814e9ef9acd88a6193882c09742992a1aa1af133e0fa80b337c1574554b38e",
          "lib/zsl-1w/aarch64/libmc_sdk_zsl_1w_aarch64.so": "38bfb8f84d6cdde3a94ceee03507c0366298edc9bff935ed6fb282d881f56084",
          "lib/zsl-1w/aarch64/mc_sdk_zsl_1w_py.cpython-310-aarch64-linux-gnu.so": "e28c4bfa917c67040706e2a977e47247ced9e62e341a81873aab2be4525d3d92",
          "lib/zsl-1w/x86_64/libmc_sdk_zsl_1w_x86_64.so": "77f02f1c7827b2023509c538ee8d3372d6c14bb6814a2963cfce1fdf84421934",
          "lib/zsl-1w/x86_64/mc_sdk_zsl_1w_py.cpython-310-x86_64-linux-gnu.so": "24e958a358c037b1e5f73022b89a47dc9c1219dd6441712ca984e66883c73576"
        },
        "license_path": "LICENSE",
        "license_identifier": "BSD-3-Clause",
        "retrieval_status": "partial",
        "blocked_reasons": {
          "binary_metadata[].sdk_version": "本轮仅静态检查；未获得将这些确切二进制 SHA-256 与 SDK 语义版本及固件组合绑定的可信厂商证据，未调用 GetSdkVersion 或加载库。目录名/README 更新日志不能替代实际工件版本。"
        },
        "available_tags": [],
        "git_refs_query_status": "retrieved",
        "available_releases": [],
        "releases_query_status": "retrieved",
        "binary_metadata": [
          {
            "path": "lib/zsl-1/aarch64/libmc_sdk_zsl_1_aarch64.so",
            "git_blob_sha": "61fdaf196385b0552ee8ba2192c4df2f6bdc0941",
            "size_bytes": 265744,
            "sha256": "bacd06930fc054be431e5dd5363c38146fc69796b280356504c7157d19b3919b",
            "retrieval_status": "static_inspected",
            "declared_architecture": "aarch64",
            "verified_architecture": "aarch64",
            "file_format": "elf64-littleaarch64",
            "dynamic_dependencies": [
              "ld-linux-aarch64.so.1",
              "libc.so.6",
              "libgcc_s.so.1",
              "libstdc++.so.6"
            ],
            "abi_symbol_versions": [
              "CXXABI_1.3",
              "CXXABI_1.3.11",
              "CXXABI_1.3.13",
              "CXXABI_1.3.3",
              "CXXABI_1.3.9",
              "GCC_3.0",
              "GLIBCXX_3.4",
              "GLIBCXX_3.4.11",
              "GLIBCXX_3.4.14",
              "GLIBCXX_3.4.19",
              "GLIBCXX_3.4.21",
              "GLIBCXX_3.4.22",
              "GLIBCXX_3.4.9",
              "GLIBC_2.17",
              "GLIBC_2.32",
              "GLIBC_2.34"
            ],
            "sdk_version": null,
            "blocked_reasons": {
              "sdk_version": "本轮仅静态检查；未获得将这些确切二进制 SHA-256 与 SDK 语义版本及固件组合绑定的可信厂商证据，未调用 GetSdkVersion 或加载库。目录名/README 更新日志不能替代实际工件版本。"
            },
            "evidence_logs": [
              "work/evidence/task0-binary-commands.jsonl",
              "work/evidence/task0-agibot_D1_Edu-Ultra-binary-results.json",
              "work/evidence/task0-curl-commands.jsonl"
            ]
          },
          {
            "path": "lib/zsl-1/aarch64/mc_sdk_zsl_1_py.cpython-310-aarch64-linux-gnu.so",
            "git_blob_sha": "206977cada05576bc8a3b28c041c9d40c22acce9",
            "size_bytes": 405672,
            "sha256": "1e7b53ffeefc7914f224686f675d2caf610c4a536e660ed5099e88e548817c2c",
            "retrieval_status": "static_inspected",
            "declared_architecture": "aarch64",
            "verified_architecture": "aarch64",
            "file_format": "elf64-littleaarch64",
            "dynamic_dependencies": [
              "ld-linux-aarch64.so.1",
              "libc.so.6",
              "libgcc_s.so.1",
              "libpython3.10.so.1.0",
              "libstdc++.so.6"
            ],
            "abi_symbol_versions": [
              "CXXABI_1.3",
              "CXXABI_1.3.11",
              "CXXABI_1.3.13",
              "CXXABI_1.3.2",
              "CXXABI_1.3.3",
              "CXXABI_1.3.5",
              "CXXABI_1.3.9",
              "GCC_3.0",
              "GCC_3.3.1",
              "GLIBCXX_3.4",
              "GLIBCXX_3.4.11",
              "GLIBCXX_3.4.14",
              "GLIBCXX_3.4.18",
              "GLIBCXX_3.4.19",
              "GLIBCXX_3.4.20",
              "GLIBCXX_3.4.21",
              "GLIBCXX_3.4.22",
              "GLIBCXX_3.4.29",
              "GLIBCXX_3.4.9",
              "GLIBC_2.17",
              "GLIBC_2.32",
              "GLIBC_2.34"
            ],
            "sdk_version": null,
            "blocked_reasons": {
              "sdk_version": "本轮仅静态检查；未获得将这些确切二进制 SHA-256 与 SDK 语义版本及固件组合绑定的可信厂商证据，未调用 GetSdkVersion 或加载库。目录名/README 更新日志不能替代实际工件版本。"
            },
            "evidence_logs": [
              "work/evidence/task0-binary-commands.jsonl",
              "work/evidence/task0-agibot_D1_Edu-Ultra-binary-results.json",
              "work/evidence/task0-curl-commands.jsonl"
            ]
          },
          {
            "path": "lib/zsl-1/x86_64/libmc_sdk_zsl_1_x86_64.so",
            "git_blob_sha": "790adcde786e033ba84e251f27aeed9977dc7a72",
            "size_bytes": 274168,
            "sha256": "c03aa3503a6de49f50871e995221c6695d35320494e8e8d5ddde78a8b026594e",
            "retrieval_status": "static_inspected",
            "declared_architecture": "x86_64",
            "verified_architecture": "x86_64",
            "file_format": "elf64-x86-64",
            "dynamic_dependencies": [
              "ld-linux-x86-64.so.2",
              "libc.so.6",
              "libgcc_s.so.1",
              "libstdc++.so.6"
            ],
            "abi_symbol_versions": [
              "CXXABI_1.3",
              "CXXABI_1.3.11",
              "CXXABI_1.3.13",
              "CXXABI_1.3.3",
              "CXXABI_1.3.9",
              "GCC_3.0",
              "GLIBCXX_3.4",
              "GLIBCXX_3.4.11",
              "GLIBCXX_3.4.14",
              "GLIBCXX_3.4.19",
              "GLIBCXX_3.4.21",
              "GLIBCXX_3.4.22",
              "GLIBCXX_3.4.9",
              "GLIBC_2.14",
              "GLIBC_2.2.5",
              "GLIBC_2.3",
              "GLIBC_2.3.2",
              "GLIBC_2.3.4",
              "GLIBC_2.32",
              "GLIBC_2.34",
              "GLIBC_2.4",
              "GLIBC_2.7",
              "GLIBC_2.8",
              "GLIBC_2.9"
            ],
            "sdk_version": null,
            "blocked_reasons": {
              "sdk_version": "本轮仅静态检查；未获得将这些确切二进制 SHA-256 与 SDK 语义版本及固件组合绑定的可信厂商证据，未调用 GetSdkVersion 或加载库。目录名/README 更新日志不能替代实际工件版本。"
            },
            "evidence_logs": [
              "work/evidence/task0-binary-commands.jsonl",
              "work/evidence/task0-agibot_D1_Edu-Ultra-binary-results.json",
              "work/evidence/task0-curl-commands.jsonl"
            ]
          },
          {
            "path": "lib/zsl-1/x86_64/mc_sdk_zsl_1_py.cpython-310-x86_64-linux-gnu.so",
            "git_blob_sha": "835492f3762860965ea2037346eb148e7eca65a5",
            "size_bytes": 434592,
            "sha256": "a0814e9ef9acd88a6193882c09742992a1aa1af133e0fa80b337c1574554b38e",
            "retrieval_status": "static_inspected",
            "declared_architecture": "x86_64",
            "verified_architecture": "x86_64",
            "file_format": "elf64-x86-64",
            "dynamic_dependencies": [
              "ld-linux-x86-64.so.2",
              "libc.so.6",
              "libgcc_s.so.1",
              "libpython3.10.so.1.0",
              "libstdc++.so.6"
            ],
            "abi_symbol_versions": [
              "CXXABI_1.3",
              "CXXABI_1.3.11",
              "CXXABI_1.3.13",
              "CXXABI_1.3.2",
              "CXXABI_1.3.3",
              "CXXABI_1.3.5",
              "CXXABI_1.3.9",
              "GCC_3.0",
              "GCC_3.3.1",
              "GLIBCXX_3.4",
              "GLIBCXX_3.4.11",
              "GLIBCXX_3.4.14",
              "GLIBCXX_3.4.18",
              "GLIBCXX_3.4.19",
              "GLIBCXX_3.4.20",
              "GLIBCXX_3.4.21",
              "GLIBCXX_3.4.22",
              "GLIBCXX_3.4.29",
              "GLIBCXX_3.4.9",
              "GLIBC_2.14",
              "GLIBC_2.2.5",
              "GLIBC_2.3",
              "GLIBC_2.3.2",
              "GLIBC_2.3.4",
              "GLIBC_2.32",
              "GLIBC_2.34",
              "GLIBC_2.4",
              "GLIBC_2.7",
              "GLIBC_2.8",
              "GLIBC_2.9"
            ],
            "sdk_version": null,
            "blocked_reasons": {
              "sdk_version": "本轮仅静态检查；未获得将这些确切二进制 SHA-256 与 SDK 语义版本及固件组合绑定的可信厂商证据，未调用 GetSdkVersion 或加载库。目录名/README 更新日志不能替代实际工件版本。"
            },
            "evidence_logs": [
              "work/evidence/task0-binary-commands.jsonl",
              "work/evidence/task0-agibot_D1_Edu-Ultra-binary-results.json",
              "work/evidence/task0-curl-commands.jsonl"
            ]
          },
          {
            "path": "lib/zsl-1w/aarch64/libmc_sdk_zsl_1w_aarch64.so",
            "git_blob_sha": "e55c99dac77f74b82e88f7706158761bf0b4dcae",
            "size_bytes": 224688,
            "sha256": "38bfb8f84d6cdde3a94ceee03507c0366298edc9bff935ed6fb282d881f56084",
            "retrieval_status": "static_inspected",
            "declared_architecture": "aarch64",
            "verified_architecture": "aarch64",
            "file_format": "elf64-littleaarch64",
            "dynamic_dependencies": [
              "ld-linux-aarch64.so.1",
              "libc.so.6",
              "libgcc_s.so.1",
              "libstdc++.so.6"
            ],
            "abi_symbol_versions": [
              "CXXABI_1.3",
              "CXXABI_1.3.11",
              "CXXABI_1.3.13",
              "CXXABI_1.3.3",
              "CXXABI_1.3.9",
              "GCC_3.0",
              "GLIBCXX_3.4",
              "GLIBCXX_3.4.11",
              "GLIBCXX_3.4.14",
              "GLIBCXX_3.4.19",
              "GLIBCXX_3.4.21",
              "GLIBCXX_3.4.22",
              "GLIBCXX_3.4.9",
              "GLIBC_2.17",
              "GLIBC_2.32",
              "GLIBC_2.34"
            ],
            "sdk_version": null,
            "blocked_reasons": {
              "sdk_version": "本轮仅静态检查；未获得将这些确切二进制 SHA-256 与 SDK 语义版本及固件组合绑定的可信厂商证据，未调用 GetSdkVersion 或加载库。目录名/README 更新日志不能替代实际工件版本。"
            },
            "evidence_logs": [
              "work/evidence/task0-binary-commands.jsonl",
              "work/evidence/task0-agibot_D1_Edu-Ultra-binary-results.json",
              "work/evidence/task0-curl-commands.jsonl"
            ]
          },
          {
            "path": "lib/zsl-1w/aarch64/mc_sdk_zsl_1w_py.cpython-310-aarch64-linux-gnu.so",
            "git_blob_sha": "1b8acdb4a5f05791cde0c4f7f564004c43c0acaa",
            "size_bytes": 303232,
            "sha256": "e28c4bfa917c67040706e2a977e47247ced9e62e341a81873aab2be4525d3d92",
            "retrieval_status": "static_inspected",
            "declared_architecture": "aarch64",
            "verified_architecture": "aarch64",
            "file_format": "elf64-littleaarch64",
            "dynamic_dependencies": [
              "ld-linux-aarch64.so.1",
              "libc.so.6",
              "libgcc_s.so.1",
              "libpython3.10.so.1.0",
              "libstdc++.so.6"
            ],
            "abi_symbol_versions": [
              "CXXABI_1.3",
              "CXXABI_1.3.11",
              "CXXABI_1.3.13",
              "CXXABI_1.3.2",
              "CXXABI_1.3.3",
              "CXXABI_1.3.5",
              "CXXABI_1.3.9",
              "GCC_3.0",
              "GCC_3.3.1",
              "GLIBCXX_3.4",
              "GLIBCXX_3.4.11",
              "GLIBCXX_3.4.14",
              "GLIBCXX_3.4.18",
              "GLIBCXX_3.4.19",
              "GLIBCXX_3.4.20",
              "GLIBCXX_3.4.21",
              "GLIBCXX_3.4.22",
              "GLIBCXX_3.4.29",
              "GLIBCXX_3.4.9",
              "GLIBC_2.17",
              "GLIBC_2.32",
              "GLIBC_2.34"
            ],
            "sdk_version": null,
            "blocked_reasons": {
              "sdk_version": "本轮仅静态检查；未获得将这些确切二进制 SHA-256 与 SDK 语义版本及固件组合绑定的可信厂商证据，未调用 GetSdkVersion 或加载库。目录名/README 更新日志不能替代实际工件版本。"
            },
            "evidence_logs": [
              "work/evidence/task0-binary-commands.jsonl",
              "work/evidence/task0-agibot_D1_Edu-Ultra-binary-results.json",
              "work/evidence/task0-curl-commands.jsonl"
            ]
          },
          {
            "path": "lib/zsl-1w/x86_64/libmc_sdk_zsl_1w_x86_64.so",
            "git_blob_sha": "06043b2d45651452a3f42530bcbb146d06df7af2",
            "size_bytes": 237200,
            "sha256": "77f02f1c7827b2023509c538ee8d3372d6c14bb6814a2963cfce1fdf84421934",
            "retrieval_status": "static_inspected",
            "declared_architecture": "x86_64",
            "verified_architecture": "x86_64",
            "file_format": "elf64-x86-64",
            "dynamic_dependencies": [
              "ld-linux-x86-64.so.2",
              "libc.so.6",
              "libgcc_s.so.1",
              "libstdc++.so.6"
            ],
            "abi_symbol_versions": [
              "CXXABI_1.3",
              "CXXABI_1.3.11",
              "CXXABI_1.3.13",
              "CXXABI_1.3.3",
              "CXXABI_1.3.9",
              "GCC_3.0",
              "GLIBCXX_3.4",
              "GLIBCXX_3.4.11",
              "GLIBCXX_3.4.14",
              "GLIBCXX_3.4.19",
              "GLIBCXX_3.4.21",
              "GLIBCXX_3.4.22",
              "GLIBCXX_3.4.9",
              "GLIBC_2.14",
              "GLIBC_2.2.5",
              "GLIBC_2.3",
              "GLIBC_2.3.2",
              "GLIBC_2.3.4",
              "GLIBC_2.32",
              "GLIBC_2.34",
              "GLIBC_2.4",
              "GLIBC_2.7",
              "GLIBC_2.8",
              "GLIBC_2.9"
            ],
            "sdk_version": null,
            "blocked_reasons": {
              "sdk_version": "本轮仅静态检查；未获得将这些确切二进制 SHA-256 与 SDK 语义版本及固件组合绑定的可信厂商证据，未调用 GetSdkVersion 或加载库。目录名/README 更新日志不能替代实际工件版本。"
            },
            "evidence_logs": [
              "work/evidence/task0-binary-commands.jsonl",
              "work/evidence/task0-agibot_D1_Edu-Ultra-binary-results.json",
              "work/evidence/task0-curl-commands.jsonl"
            ]
          },
          {
            "path": "lib/zsl-1w/x86_64/mc_sdk_zsl_1w_py.cpython-310-x86_64-linux-gnu.so",
            "git_blob_sha": "ffa64c70ac0d0b5abe6c4596069005498470f366",
            "size_bytes": 332176,
            "sha256": "24e958a358c037b1e5f73022b89a47dc9c1219dd6441712ca984e66883c73576",
            "retrieval_status": "static_inspected",
            "declared_architecture": "x86_64",
            "verified_architecture": "x86_64",
            "file_format": "elf64-x86-64",
            "dynamic_dependencies": [
              "ld-linux-x86-64.so.2",
              "libc.so.6",
              "libgcc_s.so.1",
              "libpython3.10.so.1.0",
              "libstdc++.so.6"
            ],
            "abi_symbol_versions": [
              "CXXABI_1.3",
              "CXXABI_1.3.11",
              "CXXABI_1.3.13",
              "CXXABI_1.3.2",
              "CXXABI_1.3.3",
              "CXXABI_1.3.5",
              "CXXABI_1.3.9",
              "GCC_3.0",
              "GCC_3.3.1",
              "GLIBCXX_3.4",
              "GLIBCXX_3.4.11",
              "GLIBCXX_3.4.14",
              "GLIBCXX_3.4.18",
              "GLIBCXX_3.4.19",
              "GLIBCXX_3.4.20",
              "GLIBCXX_3.4.21",
              "GLIBCXX_3.4.22",
              "GLIBCXX_3.4.29",
              "GLIBCXX_3.4.9",
              "GLIBC_2.14",
              "GLIBC_2.2.5",
              "GLIBC_2.3",
              "GLIBC_2.3.2",
              "GLIBC_2.3.4",
              "GLIBC_2.32",
              "GLIBC_2.34",
              "GLIBC_2.4",
              "GLIBC_2.7",
              "GLIBC_2.8",
              "GLIBC_2.9"
            ],
            "sdk_version": null,
            "blocked_reasons": {
              "sdk_version": "本轮仅静态检查；未获得将这些确切二进制 SHA-256 与 SDK 语义版本及固件组合绑定的可信厂商证据，未调用 GetSdkVersion 或加载库。目录名/README 更新日志不能替代实际工件版本。"
            },
            "evidence_logs": [
              "work/evidence/task0-binary-commands.jsonl",
              "work/evidence/task0-agibot_D1_Edu-Ultra-binary-results.json",
              "work/evidence/task0-curl-commands.jsonl"
            ]
          }
        ],
        "transitive_dependency_audit": "not_completed",
        "hardware_status": "not_implemented",
        "evidence_logs": [
          "work/evidence/task0-agibot_D1_Edu-Ultra-commands.jsonl",
          "work/evidence/task0-agibot_D1_Edu-Ultra-tree.txt",
          "work/evidence/task0-file-hashes.json",
          "work/evidence/task0-http-commands.jsonl",
          "work/evidence/task0-curl-commands.jsonl",
          "work/evidence/task0-agibot_D1_Edu-Ultra-releases.json"
        ]
      },
      {
        "id": "Agibot_D1_MaxPro",
        "repository": "https://github.com/AgibotTech/Agibot_D1_MaxPro.git",
        "checkout_ref": "main",
        "commit_sha": "7828aef8238388c11267e56d5e44bac9f6dd2eb4",
        "observed_at": "2026-10-06T06:43:47.636153+00:00",
        "reference_directory": "work/upstream/Agibot_D1_MaxPro",
        "source_ids": [
          "S18"
        ],
        "paths": [
          "README.md",
          "arm64/high_level_remote_client_209/build/libhigh_level_remote_tcp_client.so",
          "arm64/high_level_remote_client_209/include/high_level_base.h",
          "docs/source/1.1产品概述.md",
          "docs/source/1.2产品清单.md",
          "docs/source/1.3产品参数.md",
          "docs/source/1.4背部负载安装.md",
          "docs/source/1.5电气拓展接口.md",
          "docs/source/2.1AGI_MaxPro系统架构.md",
          "docs/source/2.2SDK软件服务接口列表.md",
          "docs/source/2.3SDK接口框图.md",
          "docs/source/3.1SDK介绍.md",
          "docs/source/3.2环境依赖.md",
          "docs/source/3.3设备登录.md",
          "docs/source/3.4SDK获取.md",
          "docs/source/3.5Demo运行.md",
          "docs/source/4.1高层运动控制接口.md",
          "docs/source/4.2底层电机控制接口.md",
          "docs/source/4.3运控诊断异常码.md",
          "docs/source/5.1视频流数据.md",
          "docs/source/index.md",
          "docs/source/一、产品介绍.md",
          "docs/source/三、SDK开发指南.md",
          "docs/source/二、系统架构.md",
          "docs/source/五、调试指南.md",
          "docs/source/四、API函数介绍.md",
          "x86/high_level_remote_client_209/build/libhigh_level_remote_tcp_client.so",
          "x86/high_level_remote_client_209/include/high_level_base.h",
          "x86/high_level_remote_client_209/include/nlohmann/json.hpp"
        ],
        "file_hashes": {
          "README.md": "cff8d07bd3703df71ae757e9e3cd3f6012bbb6502caa862f13be84e937b67a5f",
          "arm64/high_level_remote_client_209/build/libhigh_level_remote_tcp_client.so": "c039cc3e2d6b18a6dea6b8b2ccd799e8c90d3099f0c5c31be36fb83da29f4cfe",
          "arm64/high_level_remote_client_209/include/high_level_base.h": "e51dc37df3c6f8cb861b36004b48ae041cebb47de73bdb372a12517b365da391",
          "docs/source/1.1产品概述.md": "1438918049a19ee0c33957f535d83eb47bf1e26f1b9961a7379c260a56aceb1e",
          "docs/source/1.2产品清单.md": "d079af35cfe881b636b5986b147b98ffe8af7dbd81a308974c32cc2d96e4fbe4",
          "docs/source/1.3产品参数.md": "95d8077edcaf2a201ffb7c1323e9f25c182043ea18f5f3435ebe92f13e169454",
          "docs/source/1.4背部负载安装.md": "c4fab37fc112091f12b710abe6b66fa9a7d60f9399f3d3c94e007766d2712086",
          "docs/source/1.5电气拓展接口.md": "019ae94ff80a7725d9332c7694cf7839341e65254704b970d390294b4a58421a",
          "docs/source/2.1AGI_MaxPro系统架构.md": "e0c798cf4b9235cf8e5b4a36bb1bd8d3a6a884db60fe58930f8376dc4c1dfb70",
          "docs/source/2.2SDK软件服务接口列表.md": "4465ffb6fd4b5106b866828c232bff1a90d216f1ea6ccb1e5f7d6c821c0d9224",
          "docs/source/2.3SDK接口框图.md": "05faeb47263bc55fd40690e78b4651fc6a2350573ffc31ba7c249914422e8e0b",
          "docs/source/3.1SDK介绍.md": "b30e93ccf5a8fa436154d4256e9e0b13d5a82a44312bb164ff222c75a00504b2",
          "docs/source/3.2环境依赖.md": "92186749912710226397a5e9d730a0e6aafa82942055a350ddd8ae9b0f3bd156",
          "docs/source/3.3设备登录.md": "7bac584016a4bf2917c61bf037c9dfdb695de050979bec78c5593f2f9289321b",
          "docs/source/3.4SDK获取.md": "4262937ba1e468660347223f4e46ef92a6baf716b308a2e5f79192488eafb3ba",
          "docs/source/3.5Demo运行.md": "da53ac9bcc9275250abc0987258666488f15b8404b502d96d6da5b324bd6e646",
          "docs/source/4.1高层运动控制接口.md": "0210ef7568f6e67dfa3b017d5dd1ae281eebed582844c7e38ea7ae2a0c1aad9b",
          "docs/source/4.2底层电机控制接口.md": "a9c6f4e579980823c3f6fc09137ea82058a3e5f5905993005c355a7a4c227527",
          "docs/source/4.3运控诊断异常码.md": "f951a24d2a2b5b40279a26870a68b214cf69a48f345a0339adcf7a2bf203fd21",
          "docs/source/5.1视频流数据.md": "fed8818ca77ba17383338d74782422ec8b180f7c8c8d7893f9beaab7b7318806",
          "docs/source/index.md": "64b047aa437cb71a728a641eef4ce42d6cb854847567815b2114d61167d49b81",
          "docs/source/一、产品介绍.md": "d3ff03e73b10ed83fffc859239e6293eb7705f8e943438bedc359c358a7d8301",
          "docs/source/三、SDK开发指南.md": "b060f282d53c7eff83887f098f92e417c905e943d1eb603dd042c1d119435725",
          "docs/source/二、系统架构.md": "4bc3d9c691d7ee0db6ebc05872adc863defa1d1b88c841af0c96a56398964e90",
          "docs/source/五、调试指南.md": "c38267aefe6e3be681d2e52edeb449b8ae7e91497706e7beafc89a365d69441a",
          "docs/source/四、API函数介绍.md": "38c2553c816dec50eb906fa1ccec001ec1eeac6fe175fad8ffc4e0af63990b17",
          "x86/high_level_remote_client_209/build/libhigh_level_remote_tcp_client.so": "392b4abf2ad8e2e67db2078e9be390b5b092c683e3b964c9dde7d4e55b457135",
          "x86/high_level_remote_client_209/include/high_level_base.h": "e51dc37df3c6f8cb861b36004b48ae041cebb47de73bdb372a12517b365da391",
          "x86/high_level_remote_client_209/include/nlohmann/json.hpp": "8797664683b05ec108fb34582787745ff16dec2d50f3969c625541cccb887d86"
        },
        "license_path": null,
        "license_identifier": null,
        "retrieval_status": "partial",
        "blocked_reasons": {
          "license_path": "锁定提交的完整 Git 树未找到仓库级 LICENSE/COPYING 文件；第三方 nlohmann 头文件内的 MIT 文本不证明厂商 SDK 再分发许可。",
          "license_identifier": "无仓库级许可证据；厂商 SDK 使用/二进制再分发权限需另获确认。",
          "binary_metadata[].sdk_version": "本轮仅静态检查；未获得将这些确切二进制 SHA-256 与 SDK 语义版本及固件组合绑定的可信厂商证据，未调用 GetSdkVersion 或加载库。目录名/README 更新日志不能替代实际工件版本。"
        },
        "available_tags": [],
        "git_refs_query_status": "retrieved",
        "available_releases": [],
        "releases_query_status": "retrieved",
        "binary_metadata": [
          {
            "path": "arm64/high_level_remote_client_209/build/libhigh_level_remote_tcp_client.so",
            "git_blob_sha": "ba0b86d08f2fd6875fe7eb94f5946514f1154d1f",
            "size_bytes": 2095984,
            "sha256": "c039cc3e2d6b18a6dea6b8b2ccd799e8c90d3099f0c5c31be36fb83da29f4cfe",
            "retrieval_status": "static_inspected",
            "declared_architecture": "aarch64",
            "verified_architecture": "aarch64",
            "file_format": "elf64-littleaarch64",
            "dynamic_dependencies": [
              "ld-linux-aarch64.so.1",
              "libc.so.6",
              "libgcc_s.so.1",
              "libstdc++.so.6"
            ],
            "abi_symbol_versions": [
              "CXXABI_1.3",
              "CXXABI_1.3.11",
              "CXXABI_1.3.3",
              "CXXABI_1.3.9",
              "GCC_3.0",
              "GLIBCXX_3.4",
              "GLIBCXX_3.4.11",
              "GLIBCXX_3.4.14",
              "GLIBCXX_3.4.15",
              "GLIBCXX_3.4.18",
              "GLIBCXX_3.4.19",
              "GLIBCXX_3.4.21",
              "GLIBCXX_3.4.22",
              "GLIBC_2.17"
            ],
            "sdk_version": null,
            "blocked_reasons": {
              "sdk_version": "本轮仅静态检查；未获得将这些确切二进制 SHA-256 与 SDK 语义版本及固件组合绑定的可信厂商证据，未调用 GetSdkVersion 或加载库。目录名/README 更新日志不能替代实际工件版本。"
            },
            "evidence_logs": [
              "work/evidence/task0-binary-commands.jsonl",
              "work/evidence/task0-Agibot_D1_MaxPro-binary-results.json",
              "work/evidence/task0-curl-commands.jsonl"
            ]
          },
          {
            "path": "x86/high_level_remote_client_209/build/libhigh_level_remote_tcp_client.so",
            "git_blob_sha": "f68be580c261c12831cf56501c6b8e5afe1093c4",
            "size_bytes": 2085464,
            "sha256": "392b4abf2ad8e2e67db2078e9be390b5b092c683e3b964c9dde7d4e55b457135",
            "retrieval_status": "static_inspected",
            "declared_architecture": "x86_64",
            "verified_architecture": "x86_64",
            "file_format": "elf64-x86-64",
            "dynamic_dependencies": [
              "ld-linux-x86-64.so.2",
              "libc.so.6",
              "libgcc_s.so.1",
              "libstdc++.so.6"
            ],
            "abi_symbol_versions": [
              "CXXABI_1.3",
              "CXXABI_1.3.11",
              "CXXABI_1.3.3",
              "CXXABI_1.3.9",
              "GCC_3.0",
              "GLIBCXX_3.4",
              "GLIBCXX_3.4.11",
              "GLIBCXX_3.4.14",
              "GLIBCXX_3.4.15",
              "GLIBCXX_3.4.18",
              "GLIBCXX_3.4.19",
              "GLIBCXX_3.4.21",
              "GLIBCXX_3.4.22",
              "GLIBC_2.2.5",
              "GLIBC_2.3",
              "GLIBC_2.3.2",
              "GLIBC_2.4",
              "GLIBC_2.7",
              "GLIBC_2.8",
              "GLIBC_2.9"
            ],
            "sdk_version": null,
            "blocked_reasons": {
              "sdk_version": "本轮仅静态检查；未获得将这些确切二进制 SHA-256 与 SDK 语义版本及固件组合绑定的可信厂商证据，未调用 GetSdkVersion 或加载库。目录名/README 更新日志不能替代实际工件版本。"
            },
            "evidence_logs": [
              "work/evidence/task0-binary-commands.jsonl",
              "work/evidence/task0-Agibot_D1_MaxPro-binary-results.json",
              "work/evidence/task0-curl-commands.jsonl"
            ]
          }
        ],
        "transitive_dependency_audit": "not_completed",
        "hardware_status": "not_implemented",
        "evidence_logs": [
          "work/evidence/task0-Agibot_D1_MaxPro-commands.jsonl",
          "work/evidence/task0-Agibot_D1_MaxPro-tree.txt",
          "work/evidence/task0-file-hashes.json",
          "work/evidence/task0-http-commands.jsonl",
          "work/evidence/task0-curl-commands.jsonl",
          "work/evidence/task0-Agibot_D1_MaxPro-releases.json"
        ]
      },
      {
        "id": "slam_toolbox",
        "repository": "https://github.com/SteveMacenski/slam_toolbox.git",
        "checkout_ref": "humble",
        "commit_sha": "dccc5d1fd2b5007098f4050e681d20da37ef183f",
        "observed_at": "2026-10-06T06:43:47.668709+00:00",
        "reference_directory": "work/upstream/slam_toolbox",
        "source_ids": [
          "S21"
        ],
        "paths": [
          "CMakeLists.txt",
          "LICENSE",
          "README.md",
          "package.xml"
        ],
        "file_hashes": {
          "CMakeLists.txt": "bcb1b006a6c0388ec3f5a2799b0542b9a4b3f6e830af297ba7f86771cf930497",
          "LICENSE": "20c17d8b8c48a600800dfd14f95d5cb9ff47066a9641ddeab48dc54aec96e331",
          "README.md": "04496faac8cf7d1f9f37976e5f42e88c6c756cb9d4ee4e5533c72a0da5167830",
          "package.xml": "b48da9ec8fec4e9e60097a0a0861df951cd10b13f8e4d5af0491b186d7b34c46"
        },
        "license_path": "LICENSE",
        "license_identifier": "LGPL-2.1 (license text; package declares LGPL)",
        "retrieval_status": "retrieved",
        "blocked_reasons": {},
        "available_tags": [
          "0.4.0",
          "0.7.0",
          "0.7.1",
          "0.7.2",
          "0.7.3",
          "1.0.0",
          "1.1.0",
          "1.1.1",
          "1.1.2",
          "1.1.3",
          "1.1.4",
          "1.1.5",
          "1.1.6",
          "1.5.0",
          "1.5.1",
          "1.5.2",
          "1.5.3",
          "1.5.4",
          "1.5.5",
          "1.5.6",
          "1.5.7",
          "2.0.0",
          "2.0.1",
          "2.0.2",
          "2.0.3",
          "2.0.4",
          "2.1.0",
          "2.1.1",
          "2.10.0",
          "2.2.0",
          "2.3.0",
          "2.4.0",
          "2.4.1",
          "2.5.0",
          "2.5.1",
          "2.6.0",
          "2.6.1",
          "2.6.10",
          "2.6.2",
          "2.6.3",
          "2.6.4",
          "2.6.5",
          "2.6.6",
          "2.6.7",
          "2.6.8",
          "2.6.9",
          "2.7.0",
          "2.7.1",
          "2.7.2",
          "2.7.3",
          "2.7.4",
          "2.8.0",
          "2.8.1",
          "2.8.2",
          "2.8.3",
          "2.8.4",
          "2.8.5",
          "2.9.0"
        ],
        "git_refs_query_status": "retrieved",
        "available_releases": [
          {
            "tag_name": "2.10.0",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.10.0"
          },
          {
            "tag_name": "2.8.5",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.8.5"
          },
          {
            "tag_name": "2.8.4",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.8.4"
          },
          {
            "tag_name": "2.9.0",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.9.0"
          },
          {
            "tag_name": "2.8.3",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.8.3"
          },
          {
            "tag_name": "2.6.10",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.6.10"
          },
          {
            "tag_name": "2.8.2",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.8.2"
          },
          {
            "tag_name": "2.6.9",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.6.9"
          },
          {
            "tag_name": "2.8.1",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.8.1"
          },
          {
            "tag_name": "2.8.0",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.8.0"
          },
          {
            "tag_name": "2.7.4",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.7.4"
          },
          {
            "tag_name": "2.6.8",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.6.8"
          },
          {
            "tag_name": "2.6.7",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.6.7"
          },
          {
            "tag_name": "2.7.2",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.7.2"
          },
          {
            "tag_name": "2.6.6",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.6.6"
          },
          {
            "tag_name": "2.7.1",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.7.1"
          },
          {
            "tag_name": "2.6.5",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.6.5"
          },
          {
            "tag_name": "2.7.0",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.7.0"
          },
          {
            "tag_name": "2.6.4",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.6.4"
          },
          {
            "tag_name": "1.5.7",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/1.5.7"
          },
          {
            "tag_name": "2.6.3",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.6.3"
          },
          {
            "tag_name": "2.6.1",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.6.1"
          },
          {
            "tag_name": "2.6.0",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.6.0"
          },
          {
            "tag_name": "2.5.1",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.5.1"
          },
          {
            "tag_name": "2.4.1",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.4.1"
          },
          {
            "tag_name": "1.5.6",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/1.5.6"
          },
          {
            "tag_name": "2.5.0",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.5.0"
          },
          {
            "tag_name": "2.4.0",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.4.0"
          },
          {
            "tag_name": "2.0.4",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.0.4"
          },
          {
            "tag_name": "1.5.5",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/1.5.5"
          },
          {
            "tag_name": "2.3.0",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.3.0"
          },
          {
            "tag_name": "1.5.4",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/1.5.4"
          },
          {
            "tag_name": "1.5.3",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/1.5.3"
          },
          {
            "tag_name": "1.5.2",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/1.5.2"
          },
          {
            "tag_name": "1.5.1",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/1.5.1"
          },
          {
            "tag_name": "2.2.0",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.2.0"
          },
          {
            "tag_name": "1.5.0",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/1.5.0"
          },
          {
            "tag_name": "1.1.6",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/1.1.6"
          },
          {
            "tag_name": "1.1.5",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/1.1.5"
          },
          {
            "tag_name": "1.1.4",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/1.1.4"
          },
          {
            "tag_name": "2.1.1",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.1.1"
          },
          {
            "tag_name": "2.0.3",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.0.3"
          },
          {
            "tag_name": "1.1.3",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/1.1.3"
          },
          {
            "tag_name": "2.1.0",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.1.0"
          },
          {
            "tag_name": "1.1.2",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/1.1.2"
          },
          {
            "tag_name": "2.0.2",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.0.2"
          },
          {
            "tag_name": "2.0.1",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.0.1"
          },
          {
            "tag_name": "2.0.0",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/2.0.0"
          },
          {
            "tag_name": "1.1.1",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/1.1.1"
          },
          {
            "tag_name": "1.1.0",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/1.1.0"
          },
          {
            "tag_name": "0.4.0",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/0.4.0"
          },
          {
            "tag_name": "1.0.0",
            "html_url": "https://github.com/SteveMacenski/slam_toolbox/releases/tag/1.0.0"
          }
        ],
        "releases_query_status": "retrieved",
        "binary_metadata": [],
        "transitive_dependency_audit": "not_completed",
        "hardware_status": "not_implemented",
        "evidence_logs": [
          "work/evidence/task0-slam_toolbox-commands.jsonl",
          "work/evidence/task0-slam_toolbox-tree.txt",
          "work/evidence/task0-file-hashes.json",
          "work/evidence/task0-http-commands.jsonl",
          "work/evidence/task0-curl-commands.jsonl",
          "work/evidence/task0-slam_toolbox-releases.json"
        ]
      }
    ],
    "limitations": [
      "来源锁是静态审计证据；不得作为 production ArtifactRef 或硬件兼容已验证声明。",
      "未运行上游安装器、demo、SDK、Docker 容器、ROS launch 或任何机器人指令。",
      "所有 SDK 二进制实际语义版本、固件对应关系和 Linux ABI 运行兼容性未验证。",
      "MaxPro 仓库级许可及 SDK 二进制再分发许可缺失；全部仓库的传递依赖许可证/SBOM 未完成。",
      "IOENV 镜像仅见可变 tag，没有 registry manifest digest、构建来源全链或可复现构建证据。",
      "Edu docs/D1_Edu-Ultra 是未初始化的 gitlink a97aa97059f1b6e373d6eeef1819bd47f477320c；本轮仅审计主仓已选文本。",
      "GitHub releases 查询每仓最多 100 条；本轮最多 52 条，未发现分页截断。"
    ],
    "evidence_logs": [
      "work/evidence/task0-retrieval-results.json",
      "work/evidence/task0-checkout-results.json",
      "work/evidence/task0-http-retry-results.json",
      "work/evidence/task0-binary-summary.json",
      "work/evidence/task0-validation-commands.jsonl"
    ],
    "ros_probe_build": {
      "schema_version": 1,
      "recorded_at_unix": 1791310709.446456,
      "retrieval_status": "verified",
      "kind": "local_build",
      "source": "d1env/ros-probe",
      "image_id": "sha256:52f259d5fa38acb3fd2018e1601593fc0f6ad1a85c8a968032695f9c15771a2c",
      "image_id_type": "local OCI image index digest returned by Docker image inspect",
      "registry_published": false,
      "tag": "d1env/ros-probe:m3-20261007-aarch64",
      "architecture": "aarch64",
      "docker_architecture": "arm64",
      "os": "linux",
      "platform_manifest_digest": "sha256:de539eab9fcd31710ad7c0767d63657d1c5a4698fa15a08e0a131bcd27e8c8a5",
      "config_digest": "sha256:fa6cbf77edea92b3cd7c1513395e5d9bea5fd94ed7a65e2b555b12440d508425",
      "base": {
        "official_repository": "docker.io/library/ros",
        "resolved_tag": "humble-ros-core",
        "index_digest": "sha256:6892c5a0fec6c3bddc4cea502c7623f88988d7b1442419a23c685757249c7437",
        "platform": "linux/arm64/v8",
        "platform_digest": "sha256:5d8bdefcfb553802cca2fff87233f0c0adfbbd50e87e7c64c9af9a098250e6b1",
        "dockerfile_from": "docker.io/library/ros@sha256:5d8bdefcfb553802cca2fff87233f0c0adfbbd50e87e7c64c9af9a098250e6b1",
        "source_repository": "https://github.com/osrf/docker_images",
        "source_commit": "58af41813ba67f611943c35c551387d652fcdbde",
        "source_path": "ros/humble/ubuntu/jammy/ros-core/Dockerfile",
        "source_dockerfile_sha256": "474d2c4d43c1b665fe5ef117b1963412fcd8a89e923345ce59acf1f6b393c2e8",
        "source_attribution_method": "Official registry OCI source/revision annotations and fetched commit file",
        "upstream_recipe_rebuilt": false,
        "ubuntu_base_digest_from_registry_annotation": "sha256:30dfd7fe96f97c5f5ddf388ce8d098aa509644ad68fdef67244fb71b8169ffcb",
        "verification": "registry digest resolved, exact digest pulled, installed dependencies inspected"
      },
      "build": {
        "context": "containers/ros-probe",
        "argv": [
          "docker",
          "--context",
          "default",
          "build",
          "--platform",
          "linux/arm64",
          "--tag",
          "d1env/ros-probe:m3-20261007-aarch64",
          "--iidfile",
          "work/evidence/m3-image-id.txt",
          "containers/ros-probe"
        ],
        "exit_code": 0,
        "dockerfile_sha256": "3aead50c0f705a9fbe494478b82e2727ce0840ffa95467298130fb2b679ddb53",
        "source_hash": "7d02f984a53bd9cfaf484171633e247c82006dab13aab1be04dc9cd380ba5806",
        "source_hash_algorithm": "SHA256 over each sorted filename + NUL + bytes + NUL for the five listed build inputs",
        "source_files": {
          ".dockerignore": {
            "sha256": "05cc6ae53cfd6129f1d7010aa874c6cf0a6019b1adfeff3f4fab27f2d04f43ca",
            "bytes": 18
          },
          "Dockerfile": {
            "sha256": "3aead50c0f705a9fbe494478b82e2727ce0840ffa95467298130fb2b679ddb53",
            "bytes": 655
          },
          "entrypoint.sh": {
            "sha256": "9e595c205a1a375a7d91ee31e8e65e64b724f1fd75303a8ed475dbfc9ff84fae",
            "bytes": 380
          },
          "probe.py": {
            "sha256": "b65ca2d9e2db512aab209078cfb3ea809e284563e22a70bfdbc34bec9cdeed74",
            "bytes": 7833
          },
          "read_status.py": {
            "sha256": "12fe24340327a1266107998a322be270e61e8d142503eb6bcf65d93dd264060f",
            "bytes": 2415
          }
        },
        "no_apt_or_pip_additions": true,
        "new_packages": []
      },
      "installed_packages": {
        "manifest": "docs/build/ROS_PROBE_PACKAGES.json",
        "manifest_sha256": "49685624260f174fbcddb5cfb8ab923e639a29e9257254febb4b8a85d8c73d92",
        "dpkg_installed_count": 389,
        "ros_package_xml_count": 147,
        "base_and_candidate_exactly_equal": true,
        "version_lock_method": "immutable base platform digest plus exact observed dpkg and ROS package manifests"
      },
      "licenses": {
        "retrieval_status": "partial_blocked",
        "blocked_reasons": [
          "python3-rospkg-modules copyright file was unavailable at the standard dpkg path",
          "D1Env probe source license has not been selected",
          "redistribution legal review was not run"
        ],
        "docker_source_license": "Apache-2.0",
        "docker_source_license_url": "https://raw.githubusercontent.com/osrf/docker_images/58af41813ba67f611943c35c551387d652fcdbde/LICENSE",
        "docker_source_license_copy": "docs/build/licenses/OSRF-Docker-Images-APACHE-2.0.txt",
        "docker_source_license_sha256": "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
        "package_license_evidence": "individual copyright paths/hashes and license headers in ROS_PROBE_PACKAGES.json; original copyright texts remain in the inherited image",
        "standard_copyright_path_missing_packages": [
          "python3-rospkg-modules"
        ],
        "license_header_parse_not_exhaustive": true,
        "d1env_probe_source_license": null,
        "d1env_probe_source_license_reason": "The project has not selected an overall source license; no license is inferred or assigned here",
        "redistribution_legal_review": "not_run"
      },
      "runtime": {
        "user": "10001:10001",
        "entrypoint": [
          "/opt/d1env/entrypoint.sh"
        ],
        "roles": [
          "publisher",
          "subscriber",
          "idle"
        ],
        "status_reader_argv": [
          "python3",
          "/opt/d1env/read_status.py"
        ],
        "run_id_environment": "D1ENV_RUN_ID=32-lowercase-hex-job-id",
        "fixed_topic": "/d1env/test/probe",
        "network": "project-owned internal bridge with fixed pub/sub DNS aliases",
        "dds": "Fast DDS 2.6.12 UDPv4, fixed RFC1918 unicast peer discovery, built-in transports disabled",
        "read_only_root": true,
        "tmp_tmpfs": "rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=1770",
        "cap_drop": [
          "ALL"
        ],
        "security_opt": [
          "no-new-privileges"
        ],
        "host_network_or_ipc": false,
        "device_mounts": [],
        "public_ports": []
      },
      "verification": {
        "scope": "software",
        "origin": "docker",
        "host": "macOS Docker Desktop linux aarch64 daemon",
        "probe_unit_tests": {
          "passed": 42,
          "failed": 0,
          "exit_code": 0
        },
        "actual_fresh_ros_pubsub": "PASS",
        "actual_stale_after_publisher_stop": "PASS",
        "actual_no_publisher_has_no_samples": "PASS",
        "owned_resources_cleaned": true,
        "preexisting_containers_preserved": true,
        "integration_evidence": "work/evidence/m3-image-integration.json",
        "integration_evidence_sha256": "59b07ac6d59c042679ab9a7bd7e3938fc3f5494858bc11c406fbd13da04eea53",
        "commands_evidence": [
          "work/evidence/m3-image-commands.jsonl",
          "work/evidence/m3-image-integration-commands.jsonl"
        ],
        "initial_real_discovery_failure": "retained as m3-image-failure-*.json; fixed by documented UDP/unicast discovery; original cause was not proven as SHM-only",
        "not_run": [
          "Ubuntu x86_64 native daemon integration",
          "manufacturer SDK",
          "robot connection or telemetry",
          "sensors",
          "motion",
          "hardware emergency stop"
        ]
      },
      "robot_sdk_invoked": false,
      "robot_connected": false,
      "sources": [
        "https://hub.docker.com/_/ros",
        "https://github.com/osrf/docker_images/tree/58af41813ba67f611943c35c551387d652fcdbde/ros/humble/ubuntu/jammy/ros-core",
        "https://fast-dds.docs.eprosima.com/en/v2.6.12/fastdds/transport/udp/udp.html",
        "https://fast-dds.docs.eprosima.com/en/v2.6.12/fastdds/use_cases/wifi/initial_peers.html",
        "https://fast-dds.docs.eprosima.com/en/v2.6.12/fastdds/transport/disabling_multicast.html"
      ]
    },
    "ros_probe_offline": {
      "schema_version": 1,
      "filename": "d1env-ros-probe-m3-aarch64.tar",
      "sha256": "8da67f547b7885be741f8fbf0b2fd06f989cec0e2b7ed41d4a24c2adaf2414df",
      "size_bytes": 140574720,
      "source": "d1env/ros-probe",
      "image_id": "sha256:52f259d5fa38acb3fd2018e1601593fc0f6ad1a85c8a968032695f9c15771a2c",
      "architecture": "aarch64",
      "manifest": {
        "schema_version": 1,
        "kind": "d1env_ros_image",
        "source": "d1env/ros-probe",
        "architecture": "aarch64",
        "image_id": "sha256:52f259d5fa38acb3fd2018e1601593fc0f6ad1a85c8a968032695f9c15771a2c",
        "image_archive": {
          "path": "payload/image.tar",
          "sha256": "e4dc5b64caa6d61ab02f1c4c545a10593fdbdf72a3f3c54ef574c604d7a5d467",
          "size_bytes": 140562432
        }
      },
      "generation": {
        "commands": [
          {
            "command": [
              "docker",
              "--context",
              "default",
              "image",
              "save",
              "--output",
              "work/evidence/m3-docker-offline-build-final/image.tar",
              "sha256:52f259d5fa38acb3fd2018e1601593fc0f6ad1a85c8a968032695f9c15771a2c"
            ],
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "image_id": "sha256:52f259d5fa38acb3fd2018e1601593fc0f6ad1a85c8a968032695f9c15771a2c"
          },
          {
            "command": [
              ".venv/bin/python",
              "work/evidence/m3-docker-build-offline.py"
            ],
            "exit_code": 0
          }
        ],
        "image_save_by_immutable_id": true,
        "registry_published": false,
        "bundle_relative_path": "outputs/D1Env-M3/d1env-ros-probe-m3-aarch64.tar"
      },
      "verification": {
        "scope": "software",
        "origin": "docker",
        "host": "macOS Docker Desktop Linux aarch64",
        "docker_load_exit_code": 0,
        "import_status": "imported",
        "repeat_import_status": "reused",
        "repeat_import_did_not_load_again": true,
        "actual_load_with_expected_image_already_present": true,
        "all_preexisting_image_bindings_preserved": true,
        "private_staging_cleaned": true,
        "lifecycle_success": "PASS",
        "no_publisher_labelled_failure": "PASS",
        "repeated_start_same_resource_ids": "PASS",
        "owned_stop_cleanup": "PASS",
        "foreign_name_and_endpoint_preserved": "PASS",
        "unit_tests_passed": 62,
        "unit_tests_failed": 0,
        "ruff_exit_code": 0,
        "mypy_exit_code": 0,
        "evidence": [
          {
            "path": "work/evidence/m3-docker-real-import.json",
            "sha256": "e69aa982a760fc8288a3bafaeca15232edfa7e845296b84a0f403640ed8c17f4"
          },
          {
            "path": "work/evidence/m3-docker-real-ownership.json",
            "sha256": "ccaf2c53817c6e803acc7fd217d969d53319cf59c513dc92c2b15cf4e33fea13"
          },
          {
            "path": "work/evidence/m3-docker-real/650592d73fa948189a65adcba0c46a4e/actual-lifecycle.json",
            "sha256": "6eaec941b6a39fd1bb62fa18646757f8bbe8479c705c07dc1b0b2cd0e637a92a"
          },
          {
            "path": "work/evidence/m3-docker-real/7ea0303ffcca49fdb9b7e741ea8c699b/actual-lifecycle.json",
            "sha256": "473c69dc375c595011b41393320c0d78b7bd47338235caa206920c1f5fc1c468"
          },
          {
            "path": "work/evidence/m3-docker-final-static.json",
            "sha256": "f22ee8afd19c233d16d4a56254deacb9e41ea63f409bf1483bf0eeb9b1cf8f77"
          },
          {
            "path": "work/evidence/m3-docker-final-green.log",
            "sha256": "b80b88369eca76d183fe7797eeacbeb592be97f0edcac582c504a27cd949ef85"
          }
        ],
        "not_run": [
          "import into empty Docker daemon",
          "native Ubuntu x86_64 Docker integration",
          "manufacturer SDK",
          "robot connection, telemetry, motion or emergency stop"
        ]
      }
    }
  },
  "unverified_items": [
    "M3 全新 Ubuntu 22.04 x86_64 安装与桌面入口未验证",
    "该作业仅验证 Docker/ROS 软件测试，不能证明 D1 功能或安装包已完成",
    "M4 厂商 SDK 与真机遥测未验证",
    "M5 传感器、建图与导航未验证",
    "M6 运动与硬件停止行为未验证"
  ],
  "redactions": []
}
```
