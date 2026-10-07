import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from .jobs.store import TERMINAL_STATES
from .models import DeploymentRequest, Mode
from .runtime import resolve_runtime_paths
from .service import ApplicationService
from .web.app import create_app

app = typer.Typer(help="D1Env：只读主机诊断、MOCK 演示与真实 Docker/ROS 软件部署（未接真机）")


def get_service() -> ApplicationService:
    paths = resolve_runtime_paths()
    return ApplicationService(paths.assets_dir, paths.state_dir)


def output(value: object) -> None:
    typer.echo(json.dumps(value, ensure_ascii=False, indent=2))


@app.command()
def doctor() -> None:
    """只读检测当前执行电脑，不连接机器人。"""
    result = get_service().doctor(DeploymentRequest(task="diagnostics"))
    output(result)
    checks = result["checks"]
    if isinstance(checks, list) and any(c["status"] == "FAIL" for c in checks):
        raise typer.Exit(1)


@app.command()
def plan(profile: str = "demo", mode: Mode = "mock") -> None:
    """预览服务端解析的计划；真实型号未实现时返回阻塞。"""
    result = get_service().preview(DeploymentRequest(profile_id=profile, mode=mode,
        task="ros_probe" if mode == "software_test" else "demo"))
    output(result.model_dump(mode="json"))
    if result.plan is None:
        raise typer.Exit(1)


@app.command()
def deploy(plan_id: str, request_key: Annotated[str, typer.Option("--request-key")]) -> None:
    """执行已保存且再次复核通过的计划，不接受任意命令或镜像。"""
    try:
        service = get_service()
        job = service.start(plan_id, request_key)
        job = service.engine.get(job.job_id)
        try:
            while job.state not in TERMINAL_STATES:
                time.sleep(0.1)
                job = service.engine.get(job.job_id)
        except KeyboardInterrupt:
            service.engine.cancel(job.job_id)
            deadline = time.monotonic() + 30
            while job.state not in TERMINAL_STATES and time.monotonic() < deadline:
                time.sleep(0.1)
                job = service.engine.get(job.job_id)
            output(job.model_dump(mode="json"))
            raise typer.Exit(130) from None
        output(job.model_dump(mode="json"))
        if job.state != "SUCCEEDED" or (job.mode == "software_test" and job.current_software_ready is not True):
            raise typer.Exit(1)
    except (KeyError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None


@app.command()
def stop(job_id: str) -> None:
    """停止本作业拥有的软件测试服务，保留用户数据与镜像。"""
    try:
        job = get_service().stop(job_id)
        output(job.model_dump(mode="json"))
        if job.state == "FAILED":
            raise typer.Exit(1)
    except (KeyError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None


@app.command()
def import_image(bundle: Path) -> None:
    """导入随发行包提供且摘要匹配的 ROS 软件镜像，不接受任意镜像。"""
    try:
        output(get_service().import_ros_image(bundle))
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None


@app.command()
def status(job_id: str) -> None:
    """读取保存的作业状态。"""
    try:
        output(get_service().engine.get(job_id).model_dump(mode="json"))
    except KeyError:
        typer.echo("作业不存在", err=True)
        raise typer.Exit(1) from None


@app.command()
def report(job_id: str, output_path: Annotated[Path, typer.Option("--output")]) -> None:
    """去敏导出 JSON 或 Markdown。"""
    try:
        result = get_service().report(job_id)
        content = result["markdown"] if output_path.suffix.lower() == ".md" else json.dumps(result["report"], ensure_ascii=False, indent=2)
        if output_path.is_symlink() or output_path.exists():
            raise ValueError("输出路径已存在或是符号链接；不会覆盖已有数据")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("x", encoding="utf-8") as file:
            file.write(str(content))
        typer.echo("去敏报告已导出，验证范围见报告")
    except (KeyError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None


@app.command()
def ui(demo: bool = False, no_browser: bool = False, port: int = 8765) -> None:
    """启动本地向导，默认 MOCK；真实软件部署需在 UI 显式选择。"""
    if not 1024 <= port <= 65535:
        typer.echo("端口须为 1024–65535", err=True)
        raise typer.Exit(2)
    application = create_app(get_service(), port=port)
    listener = socket.socket()
    try:
        listener.bind(("127.0.0.1", port))
    except OSError:
        typer.echo("回环端口已占用，未停止其他程序。请显式选择另一个端口。", err=True)
        listener.close()
        raise typer.Exit(1) from None
    listener.listen(128)
    if not no_browser:
        token = application.state.security.bootstrap_token
        url = f"http://127.0.0.1:{port}/#bootstrap={token}"
        if os.uname().sysname == "Darwin":
            subprocess.Popen(["open", "-na", "Google Chrome", "--args", "--new-window", url],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            chrome = shutil.which("google-chrome") or shutil.which("chromium")
            if chrome is None:
                typer.echo("缺少可新开独立窗口的 Chrome/Chromium；服务未启动。", err=True)
                listener.close()
                raise typer.Exit(1)
            subprocess.Popen([chrome, "--new-window", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    typer.echo(f"D1Env 本地向导：http://127.0.0.1:{port} （默认 MOCK；未连接真机）")
    uvicorn.Server(uvicorn.Config(application, access_log=False, log_level="warning")).run(sockets=[listener])


if __name__ == "__main__":
    app()
