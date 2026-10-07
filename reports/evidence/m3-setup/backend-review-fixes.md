# 首次准备核心独立审查修复

日期：2026-10-07（Asia/Shanghai）。没有进行主机安装、启动/停止 Docker、创建容器或修改真实应用权限。

## 持久状态读取竞态

修改范围仅 `manager.py` 的 `_read` 与必要 `stat` 导入；未修改 root 负责的 cancel、worker finally、status 契约。

确定性 barrier：读线程已经打开任务 JSON，写线程通过原有 `_update` 正常 `os.replace` 新任务文件，读线程旧 fd 的 nlink 变 0。修复前不能读取合法新状态。只在旧 fd 仍为当前用户、私有权限普通文件且 nlink=0，当前路径为不同 inode 的当前用户、nlink=1、私有普通文件时重新打开。最多三次；不会接受 unlink 后旧 fd，不放宽 symlink/hardlink/owner/mode，也不会对路径缺失或同 inode 情况重读。耗尽返回 `SETUP_STATE_INVALID` 未知状态错误，不使用历史成功。

- `.venv/bin/python -m pytest --tb=short -q tests/test_setup_state_races.py`：RED 退出 1，2 failed / 9 passed；GREEN 退出 0，11 passed / 0 failed / 0 skipped。
- 证据：`state-race-{red,green,ruff,mypy}.log`；Ruff/mypy 退出 0。

## 应用内部权限及主执行文件

修改范围 `installer.py`、独立 `test_setup_app_permissions.py`；原有 installer 测试 helper `app_at` 加入真实格式的 CFBundleExecutable 与不执行的模拟主文件。

检查整个应用树：文件/目录归属为 root 或当前用户，没有 group/world 写权限；普通文件 nlink 必须为 1。合法资源 symlink 保留，但链接归属必须可信，解析必须存在且处于当前 app 内；不跟随目录 symlink 遍历。拒绝特殊文件、外部/失效/循环链接。主 Info.plist 中固定身份为 `com.docker.docker`，从实际官方版本取得的主执行文件为 `com.docker.backend`，必须为可信常规可执行文件。签名与 Gatekeeper 前后完整检查安全元数据指纹；变化不能沿用旧核验结果 `open`。没有用测试假签名绕过真实检查，也没有实际运行主二进制。

- `.venv/bin/python -m pytest --tb=short -q tests/test_setup_app_permissions.py`：RED 退出 1，18 failed / 1 passed；其中有一个实际已装官方 app 的只读字段检查，不能把它当成真实首次安装验证。
- `.venv/bin/python -m pytest --tb=short -q tests/test_setup_app_permissions.py tests/test_setup_installer.py tests/test_setup_state_races.py`：GREEN 退出 0，45 passed / 0 failed / 0 skipped。
- 证据：`app-permissions-red.log`、`app-race-combined-green.log`、`app-permissions-{ruff,mypy}.log`。
- 当前官方已装 4.80.0/232116 app 的纯只读统计：706 条目、30 个合法内部资源链接，没有不可信归属、组/所有人可写条目或普通硬链接；主文件 `com.docker.backend`。`_check_app` 实际执行验证成功。证据 `app-permissions-official-{readonly,function-green}.json`，主程序未运行、Docker 未启动、真实权限未改。

## 当前组合结果

运行命令：

`work/venv310/bin/python -m pytest --tb=short -q tests/test_setup_download.py tests/test_setup_installer.py tests/test_setup_manager.py tests/test_setup_state_races.py tests/test_setup_app_permissions.py`

`.venv/bin/python -m pytest --tb=short -q tests/test_setup_download.py tests/test_setup_installer.py tests/test_setup_manager.py tests/test_setup_state_races.py tests/test_setup_app_permissions.py`

两版本均退出 0：104 passed / 0 failed / 0 skipped，属于相同 104 个用例，包含 root 增加的 4 个取消测试。证据 `backend-review-final-python{310,312}.log`。`.venv/bin/ruff check src/d1env/setup tests/test_setup_*.py` 退出 0；`.venv/bin/mypy src/d1env/setup` 退出 0（5 source files），证据 `backend-review-final-{ruff,mypy}.log`。

真实首次 Docker 安装、无应用目录权限、原生协议接受、实际首次启动/取消、其他 Mac/Linux 和 D1 真机依旧未验证。这些测试/只读 app 检查不能提升对应通过声明。
