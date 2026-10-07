# 下载读取与时限边界补充

2026-10-07（Asia/Shanghai）。修改仅 `download.py` 与新增 `test_setup_download_deadline.py`；没有实际下载、安装或启动 Docker。

官方 HTTP adapter 将 `HTTPResponse.read` 改为 `read1(count)`，每轮最多一次底层接收，避免持续小片段导致为填满 1 MiB 不返回。注入 opener 的测试 read 语义保持原样。整体下载 deadline 默认 1800 秒，仅可信构造时可设定，必须 `0 < timeout <= 3600`；clock 可测试注入，HTTP payload 不开放该参数。打开连接后、每次 chunk 前后、验证前后和缓存晋升前检查整体时限，过期片段不会晋升为 `.dmg`。TLS、官方地址/拒绝跳转、大小和 SHA 校验不变。

进度回调满足任一条件才写：距离上次至少 250 ms、累计至少 1 MiB、达到锁定的完整字节数。避免每个字节回调导致重复 fsync；每轮取消检查仍保留。网络打开/单次接收本身仍由系统 socket 的 15 秒 timeout 控制，整体 deadline 在这些同步调用返回时检查；没有宣称毫秒级取消或测试所有 TLS/HTTP 恶意慢速响应。

真实命令与结果：

- `.venv/bin/python -m pytest --tb=short -q tests/test_setup_download_deadline.py`：RED 退出 1，10 failed（新行为未实现），日志 `download-deadline-red.log`。
- `.venv/bin/python -m pytest --tb=short -q tests/test_setup_download_deadline.py tests/test_setup_download.py`：GREEN 退出 0，28 passed / 0 failed / 0 skipped，日志 `download-deadline-green.log`。
- 最终 setup 组合（download/deadline/installer/manager/state_races/app_permissions 六文件）：Python 3.10 和 3.12 各退出 0、114 passed / 0 failed / 0 skipped，同 114 用例，日志 `backend-deadline-final-python{310,312}.log`。
- `.venv/bin/ruff check src/d1env/setup tests/test_setup_*.py` 退出 0；`.venv/bin/mypy src/d1env/setup` 退出 0（5 source files），日志 `backend-deadline-final-{ruff,mypy}.log`。

fake HTTP 的 read 方法故意失败，只有调用 read1 才通过；假时钟持续推进时的片段超时不晋升；字节滴答仅少量进度回调并报告完整字节数；每 MiB 回调不必等待时钟。没有把这些注入测试当成真实慢网或首次安装通过。
