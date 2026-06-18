import os
import platform
import shutil
import subprocess
import sys

import psutil


def detect_cpu():
    info = {}
    try:
        info["physical_cores"] = psutil.cpu_count(logical=False) or 0
    except Exception:
        info["physical_cores"] = 0
    try:
        info["logical_cores"] = psutil.cpu_count(logical=True) or 0
    except Exception:
        info["logical_cores"] = 0

    info["architecture"] = platform.machine()

    if sys.platform == "linux":
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        info["model"] = line.split(":")[1].strip()
                        break
        except Exception:
            info["model"] = platform.processor() or "Unknown"
    elif sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=5
            )
            info["model"] = result.stdout.strip()
        except Exception:
            info["model"] = platform.processor() or "Apple Silicon"
    elif sys.platform == "win32":
        try:
            result = subprocess.run(
                ["wmic", "cpu", "get", "name"],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.strip().splitlines()
            if len(lines) >= 2:
                info["model"] = lines[1].strip()
        except Exception:
            info["model"] = platform.processor() or "Unknown"
    else:
        info["model"] = platform.processor() or "Unknown"

    try:
        freq = psutil.cpu_freq()
        if freq:
            info["max_freq_mhz"] = round(freq.max, 0)
            info["current_freq_mhz"] = round(freq.current, 0)
    except Exception:
        pass

    return info


def detect_ram():
    mem = psutil.virtual_memory()
    info = {
        "total_gb": round(mem.total / (1024**3), 1),
        "available_gb": round(mem.available / (1024**3), 1),
        "used_gb": round(mem.used / (1024**3), 1),
        "percent_used": mem.percent,
    }
    try:
        swap = psutil.swap_memory()
        info["swap_total_gb"] = round(swap.total / (1024**3), 1)
    except Exception:
        pass
    return info


def detect_storage():
    home = os.path.expanduser("~")
    usage = shutil.disk_usage(home)
    return {
        "total_gb": round(usage.total / (1024**3), 1),
        "free_gb": round(usage.free / (1024**3), 1),
        "used_gb": round(usage.used / (1024**3), 1),
    }


def detect_os():
    uname = platform.uname()
    info = {
        "system": uname.system,
        "release": uname.release,
        "version": uname.version,
        "machine": uname.machine,
        "hostname": uname.node,
    }
    if sys.platform == "linux":
        try:
            result = subprocess.run(
                ["lsb_release", "-d", "-s"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                info["distro"] = result.stdout.strip()
        except Exception:
            pass
        try:
            with open("/proc/version") as f:
                info["kernel"] = f.read().strip()
        except Exception:
            info["kernel"] = uname.version
    elif sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["sw_vers", "-productVersion"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                info["macos_version"] = result.stdout.strip()
        except Exception:
            pass
    elif sys.platform == "win32":
        info["windows_version"] = f"{uname.release} (build {uname.version})"

    info["is_apple_silicon"] = (
        sys.platform == "darwin" and platform.machine() == "arm64"
    )
    return info


def detect_all():
    return {
        "cpu": detect_cpu(),
        "ram": detect_ram(),
        "storage": detect_storage(),
        "os": detect_os(),
    }
