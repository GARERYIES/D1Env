import json
import os
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from .models import DeploymentRequest, Mode
from .service import ApplicationService
from .web.app import create_app

app = typer.Typer(help="D1Env M0–M2：只读主机诊断与明确标识的 MOCK 演示")


def get_service() -> ApplicationService:
    root = Path(__file__).resolve().parents[2]
    state = Path(os.environ.get("D1ENV_STATE_DIR", str(root / "work/state")))
    return ApplicationService(root, state)


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
    result = get_service().preview(DeploymentRequest(profile_id=profile, mode=mode))
    output(result.model_dump(mode="json"))
    if result.plan is None:
        raise typer.Exit(1)


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
        typer.echo("去敏报告已导出（MOCK）")
    except (KeyError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None


@app.command()
def ui(demo: bool = False, no_browser: bool = False, port: int = 8765) -> None:
    """启动本地 MOCK 向导；默认独立浏览器窗口。"""
    if not demo or not 1024 <= port <= 65535:
        typer.echo("本轮只接受 ui --demo；端口须为 1024–65535", err=True)
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
    typer.echo(f"D1Env MOCK 本地向导：http://127.0.0.1:{port} （演示，未部署真机）")
    uvicorn.Server(uvicorn.Config(application, access_log=False, log_level="warning")).run(sockets=[listener])


if __name__ == "__main__":
    app()
