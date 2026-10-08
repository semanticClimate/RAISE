"""
System Telemetry & Hardware Probing Service
===========================================
Dynamically probes host CPU, RAM, GPU, disk storage, and local AI runtime sockets.
"""

from __future__ import annotations

import platform
import socket
import shutil
from pathlib import Path
from typing import Any, Dict


def get_hardware_telemetry() -> Dict[str, Any]:
    """Dynamically probes host CPU, RAM, GPU, and local inference engine liveness."""
    import psutil

    # 1. CPU
    cpu_cores_logical = psutil.cpu_count(logical=True) or 1
    cpu_cores_physical = psutil.cpu_count(logical=False) or 1
    cpu_percent = psutil.cpu_percent(interval=0.05)

    # 2. RAM
    mem = psutil.virtual_memory()
    total_ram_gb = round(mem.total / (1024**3), 1)
    available_ram_gb = round(mem.available / (1024**3), 1)

    # 3. GPU (CUDA check)
    gpu_detected = False
    gpu_name = "None (CPU Execution)"
    vram_gb = 0.0
    try:
        import torch
        if torch.cuda.is_available():
            gpu_detected = True
            gpu_name = torch.cuda.get_device_name(0)
            _, v_tot = torch.cuda.mem_get_info()
            vram_gb = round(v_tot / (1024**3), 1)
    except Exception:
        pass

    # 4. Local AI Engine Probe (Port 11434 / 8002 / 1234)
    local_ai_running = False
    for port in (11434, 8002, 1234):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                local_ai_running = True
                break
        except Exception:
            pass

    # 5. Disk Space Probe
    disk = shutil.disk_usage(Path.cwd())
    free_disk_gb = round(disk.free / (1024**3), 1)
    total_disk_gb = round(disk.total / (1024**3), 1)

    # Recommended profile based on hardware & disk
    if total_ram_gb >= 16 or vram_gb >= 8:
        recommended_mode = "hybrid"
        recommendation_note = f"Hardware supports both Local (Llama / Qwen) and Cloud AI. ({free_disk_gb} GB disk available)"
    else:
        recommended_mode = "cloud"
        recommendation_note = "Cloud Profile (Groq / Gemini) recommended for instantaneous latency with zero disk usage."

    # Fetch dynamically from public model APIs and local engine
    from .model_catalog_service import get_dynamic_model_catalog
    local_model_catalog = get_dynamic_model_catalog(total_ram_gb)

    return {
        "platform": platform.system().lower(),
        "os_name": f"{platform.system()} {platform.release()}",
        "cpu_cores": cpu_cores_logical,
        "cpu_physical_cores": cpu_cores_physical,
        "cpu_usage_pct": cpu_percent,
        "total_ram_gb": total_ram_gb,
        "free_ram_gb": available_ram_gb,
        "total_disk_gb": total_disk_gb,
        "free_disk_gb": free_disk_gb,
        "gpu_detected": gpu_detected,
        "gpu_name": gpu_name,
        "vram_gb": vram_gb,
        "ollama_running": local_ai_running,
        "recommended_mode": recommended_mode,
        "recommendation_note": recommendation_note,
        "local_model_catalog": local_model_catalog,
    }
