"""
桌面启动器（无浏览器模式）

启动 FastAPI 后端并在原生窗口中加载本地页面，实现即开即用体验。
"""
from __future__ import annotations

import asyncio
import json
import socket
import sys
import threading
import time
import traceback
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

import uvicorn

from config import get_config
from utils.logger import get_logger

logger = get_logger(__name__)


def _runtime_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _boot_log(message: str) -> None:
    try:
        log_path = _runtime_base_dir() / "data" / "logs" / "desktop_boot.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{ts} | {message}\n")
    except Exception:
        # 启动诊断不应影响主流程
        pass


def _is_port_in_use(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def _backend_payload_matches_runtime(data: dict, expected_base_dir: Path) -> bool:
    if not isinstance(data, dict) or not {"status", "stats", "active_tasks"}.issubset(data.keys()):
        return False
    runtime = data.get("runtime") or {}
    existing_base_dir = runtime.get("base_dir")
    if not existing_base_dir:
        return False
    try:
        return Path(existing_base_dir).resolve() == expected_base_dir.resolve()
    except OSError:
        return False


def _run_server(host: str, port: int, debug: bool, error_holder: dict) -> None:
    try:
        from main import app as fastapi_app
        _boot_log(f"uvicorn.run start host={host} port={port} debug={debug}")
        uvicorn.run(
            fastapi_app,
            host=host,
            port=port,
            reload=False,
            log_level="info" if debug else "warning",
            log_config=None,
            access_log=False,
        )
        _boot_log("uvicorn.run returned normally")
    except BaseException:
        error_holder["traceback"] = traceback.format_exc()
        _boot_log(f"uvicorn.run crashed:\n{error_holder['traceback']}")
        raise


def _preflight_backend() -> None:
    try:
        from main import app as _app  # noqa: F401
        from models.database import init_db
        from models.template import template_manager

        asyncio.run(init_db())
        asyncio.run(template_manager.load_templates())
        _boot_log("backend preflight passed")
    except Exception:
        tb = traceback.format_exc()
        _boot_log(f"backend preflight failed:\n{tb}")
        raise RuntimeError("后端预检查失败，请查看 data/logs/desktop_boot.log")


def _wait_backend_ready(
    url: str,
    timeout_seconds: int = 30,
    expected_base_dir: Path | None = None,
) -> bool:
    attempt = 0
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        attempt += 1
        try:
            with urlopen(url, timeout=2) as response:
                payload = response.read().decode("utf-8", errors="ignore")
                data = json.loads(payload)
                if _backend_payload_matches_runtime(data, expected_base_dir or _runtime_base_dir()):
                    _boot_log(f"health check passed on attempt={attempt}")
                    return True
                if isinstance(data, dict) and {"status", "stats", "active_tasks"}.issubset(data.keys()):
                    _boot_log(
                        "health check found another DocuFlow runtime; "
                        f"expected={expected_base_dir or _runtime_base_dir()} "
                        f"actual={(data.get('runtime') or {}).get('base_dir')}"
                    )
                    return False
                if attempt % 5 == 0:
                    _boot_log(f"health check non-docuflow payload on attempt={attempt}: {payload[:120]}")
        except URLError:
            if attempt % 5 == 0:
                _boot_log(f"health check url error on attempt={attempt}")
            time.sleep(0.3)
        except Exception:
            if attempt % 5 == 0:
                _boot_log(f"health check exception on attempt={attempt}")
            time.sleep(0.3)
    _boot_log(f"health check timed out: url={url}, timeout={timeout_seconds}s")
    return False


def main() -> None:
    cfg = get_config()
    host = cfg.host or "127.0.0.1"
    port = int(cfg.port or 8000)
    status_url = f"http://{host}:{port}/api/status"
    runtime_base_dir = _runtime_base_dir()
    _boot_log(f"desktop_app main start host={host} port={port} status_url={status_url}")

    # 端口上已经是可用的 DocuFlow 后端时，直接复用
    if _wait_backend_ready(status_url, timeout_seconds=2, expected_base_dir=runtime_base_dir):
        _boot_log("reuse existing backend")
        logger.info(f"检测到已运行后端，直接复用: {status_url}")
    else:
        _preflight_backend()
        server_error: dict[str, str] = {}
        server_thread = threading.Thread(
            target=_run_server,
            kwargs={"host": host, "port": port, "debug": cfg.debug, "error_holder": server_error},
            daemon=True,
            name="docuflow-backend",
        )
        server_thread.start()
        _boot_log("backend thread started")

        if not _wait_backend_ready(status_url, expected_base_dir=runtime_base_dir):
            if server_error.get("traceback"):
                raise RuntimeError(
                    "后端线程异常退出，请查看 data/logs/desktop_boot.log 获取详细堆栈"
                )
            if not server_thread.is_alive() and _is_port_in_use(host, port):
                raise RuntimeError(
                    f"端口 {port} 已被其他程序占用，DocuFlow 无法绑定。请先释放该端口后重试。"
                )
            if not server_thread.is_alive():
                raise RuntimeError("后端进程异常退出，请查看 data/logs/desktop_boot.log")
            if _is_port_in_use(host, port):
                raise RuntimeError(
                    f"端口 {port} 已被占用，且 /api/status 不可用。请关闭占用程序后重试。"
                )
            raise RuntimeError(f"后端启动超时: {status_url}")

    try:
        import webview
    except Exception as e:
        raise RuntimeError("缺少 pywebview 依赖，无法启动桌面模式") from e

    app_url = f"http://{host}:{port}"
    _boot_log(f"create window url={app_url}")
    logger.info(f"桌面模式启动: {app_url}")
    webview.create_window(
        title=cfg.app_name,
        url=app_url,
        width=1480,
        height=920,
        min_size=(1200, 760),
        confirm_close=True,
    )
    webview.start(gui="edgechromium", debug=cfg.debug)


if __name__ == "__main__":
    main()

