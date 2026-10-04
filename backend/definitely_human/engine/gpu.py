"""NVIDIA driver check and the "update driver" helper.

The app's PyTorch is built for CUDA 12.8, which needs an NVIDIA driver of at
least 570.65 on Windows (570.26 on Linux). nvidia-smi ships with every NVIDIA
driver, so it tells us the installed version even when CUDA itself fails.
Updating is left to NVIDIA's own tools: we only open NVIDIA App (or the
official download page) for the user.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

MIN_DRIVER = (570, 65) if sys.platform == "win32" else (570, 26)
DRIVER_PAGE = "https://www.nvidia.com/en-us/drivers/"
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0  # don't flash a console under pythonw


def parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.strip().split(".") if p.isdigit())


def parse_smi(out: str) -> list[dict]:
    """Parse `nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader,nounits`."""
    gpus = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2 and parts[1]:
            g = {"name": parts[0], "driver": parts[1]}
            if len(parts) >= 3 and parts[2].isdigit():
                g["vram_gb"] = round(int(parts[2]) / 1024, 1)
            gpus.append(g)
    return gpus


def query_nvidia() -> list[dict]:
    """GPUs reported by the NVIDIA driver; [] if there's no NVIDIA driver or GPU."""
    fake = os.environ.get("DH_FAKE_NVIDIA_SMI")  # testing the UI on machines without NVIDIA
    if fake:
        return parse_smi(fake)
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total",
                            "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10, creationflags=_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_smi(r.stdout) if r.returncode == 0 else []


def driver_status(cuda_works: bool, gpus: list[dict]) -> dict:
    """Summarise the driver situation for the UI.

    status: ok | outdated | cuda_error | no_nvidia
    """
    need = ".".join(map(str, MIN_DRIVER))
    if not gpus:
        return {"status": "ok" if cuda_works else "no_nvidia", "driver_min": need}
    g = gpus[0]
    info = {"driver": g["driver"], "driver_min": need, "nvidia_gpu": g["name"]}
    if parse_version(g["driver"]) < MIN_DRIVER:
        return {**info, "status": "outdated"}
    return {**info, "status": "ok" if cuda_works else "cuda_error"}


def _nvidia_app() -> Path | None:
    roots = [Path(r"C:\Program Files\NVIDIA Corporation\NVIDIA app"),
             Path(r"C:\Program Files\NVIDIA Corporation\NVIDIA GeForce Experience")]
    for root in roots:
        if root.is_dir():
            for exe in sorted(root.rglob("*.exe")):
                n = exe.name.lower()
                if n in ("nvidia app.exe", "nvidia geforce experience.exe"):
                    return exe
    return None


def open_driver_update() -> str:
    """Open NVIDIA App / GeForce Experience if installed, else the official driver page."""
    import webbrowser

    if sys.platform == "win32":
        exe = _nvidia_app()
        if exe is not None:
            import os

            os.startfile(str(exe))  # noqa: S606 - a fixed, installed NVIDIA executable
            return "nvidia-app"
    webbrowser.open(DRIVER_PAGE)
    return "web"
