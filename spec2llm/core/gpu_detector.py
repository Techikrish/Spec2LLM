import os
import platform
import re
import shutil
import subprocess
import sys


def _try_nvidia():
    try:
        import pynvml
        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        gpus = []
        for i in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            cuda_cores = None
            try:
                cuda_cores = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
                cuda_cores = f"{cuda_cores[0]}.{cuda_cores[1]}"
            except Exception:
                pass
            try:
                driver = pynvml.nvmlSystemGetDriverVersion()
            except Exception:
                driver = None
            gpus.append({
                "name": name.decode() if isinstance(name, bytes) else name,
                "vram_total_mb": round(mem.total / 1024**2, 0),
                "vram_free_mb": round(mem.free / 1024**2, 0),
                "vram_used_mb": round(mem.used / 1024**2, 0),
                "compute_capability": cuda_cores,
                "driver_version": driver.decode() if isinstance(driver, bytes) else driver,
                "vendor": "nvidia",
                "memory_type": "dedicated",
            })
        pynvml.nvmlShutdown()
        if gpus:
            return gpus
    except Exception:
        pass
    return None


def _try_nvidia_gputil():
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            results = []
            for gpu in gpus:
                results.append({
                    "name": gpu.name,
                    "vram_total_mb": round(gpu.memoryTotal, 0),
                    "vram_free_mb": round(gpu.memoryFree, 0),
                    "vram_used_mb": round(gpu.memoryUsed, 0),
                    "driver_version": gpu.driver,
                    "vendor": "nvidia",
                    "memory_type": "dedicated",
                })
            return results
    except Exception:
        pass
    return None


def _try_windows_wmi():
    try:
        import subprocess
        result = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "Name,AdapterRAM,DriverVersion"],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().splitlines()
        if len(lines) < 2:
            return None
        gpus = []
        header = [h.strip().lower() for h in lines[0].split() if h.strip()]
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split("  ") if p.strip()]
            if len(parts) >= 1:
                gpu = {"vendor": "unknown", "memory_type": "dedicated"}
                gpu["name"] = parts[0]
                if len(parts) >= 2 and parts[1].isdigit():
                    gpu["vram_total_mb"] = round(int(parts[1]) / 1024**2, 0)
                if len(parts) >= 3:
                    gpu["driver_version"] = parts[2]
                gpu["vram_free_mb"] = 0
                gpu["vram_used_mb"] = 0
                gpus.append(gpu)
        if gpus:
            return gpus
    except Exception:
        pass
    return None


def _try_linux_lspci():
    try:
        result = subprocess.run(
            ["lspci"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return None
        gpus = []
        for line in result.stdout.splitlines():
            if "VGA" in line or "3D" in line or "Display" in line:
                name = line.split(":")[-1].strip() if ":" in line else line.strip()
                vendor = "unknown"
                if "NVIDIA" in name or "nvidia" in name:
                    vendor = "nvidia"
                elif "AMD" in name or "Advanced Micro Devices" in name:
                    vendor = "amd"
                elif "Intel" in name:
                    vendor = "intel"
                gpus.append({
                    "name": name,
                    "vram_total_mb": 0,
                    "vram_free_mb": 0,
                    "vram_used_mb": 0,
                    "vendor": vendor,
                    "memory_type": "dedicated",
                })
        if gpus:
            return gpus
    except Exception:
        pass
    return None


def _try_macos_system_profiler():
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return None
        gpus = []
        current_gpu = {}
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("Chipset Model:"):
                if current_gpu:
                    gpus.append(current_gpu)
                current_gpu = {"vendor": "apple" if "Apple" in stripped else "unknown", "memory_type": "unified"}
                current_gpu["name"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("VRAM") or stripped.startswith("Video Memory"):
                parts = stripped.split(":", 1)
                if len(parts) == 2:
                    val = parts[1].strip().lower()
                    match = re.search(r"(\d+\.?\d*)", val)
                    if match:
                        current_gpu["vram_total_mb"] = round(float(match.group(1)) * 1024, 0)
            elif stripped.startswith("Metal") and current_gpu:
                current_gpu["metal_support"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("Vendor"):
                current_gpu["vendor"] = stripped.split(":", 1)[1].strip().lower()

        if current_gpu:
            gpus.append(current_gpu)

        if not gpus:
            return None

        for gpu in gpus:
            gpu.setdefault("vram_total_mb", 0)
            gpu.setdefault("vram_free_mb", 0)
            gpu.setdefault("vram_used_mb", 0)
            gpu.setdefault("memory_type", "unified")

        return gpus
    except Exception:
        pass
    return None


def _try_macos_apple_silicon_default():
    if sys.platform == "darwin" and platform.machine() == "arm64":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5
            )
            total_ram_b = int(result.stdout.strip())
            total_ram_gb = total_ram_b / (1024**3)
            return [{
                "name": "Apple Silicon (Unified GPU)",
                "vram_total_mb": round(total_ram_b / (1024**2) * 0.5, 0),
                "vram_free_mb": round(total_ram_b / (1024**2) * 0.3, 0),
                "vram_used_mb": 0,
                "vendor": "apple",
                "memory_type": "unified",
                "unified_ram_total_gb": round(total_ram_gb, 1),
            }]
        except Exception:
            pass
    return None


def detect_gpus():
    methods = [
        ("nvidia_nvml", _try_nvidia),
        ("nvidia_gputil", _try_nvidia_gputil),
        ("windows_wmi", _try_windows_wmi),
        ("linux_lspci", _try_linux_lspci),
        ("macos_profiler", _try_macos_system_profiler),
        ("macos_default", _try_macos_apple_silicon_default),
    ]

    for name, method in methods:
        if sys.platform == "win32" and name not in ("windows_wmi", "nvidia_nvml", "nvidia_gputil"):
            continue
        if sys.platform == "darwin" and name not in ("macos_profiler", "macos_default", "nvidia_nvml", "nvidia_gputil"):
            continue
        if sys.platform == "linux" and name not in ("linux_lspci", "nvidia_nvml", "nvidia_gputil"):
            continue

        result = method()
        if result:
            return result

    return None
