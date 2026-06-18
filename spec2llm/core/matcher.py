import re


def _parse_params(params_str):
    params_str = str(params_str).upper().replace("B", "").strip()
    try:
        return float(params_str)
    except ValueError:
        return 0


def _get_gpu_tier_score(gpu_info, model_gpu_tier):
    tier_map = {
        "consumer": 1,
        "prosumer": 2,
        "datacenter": 3,
    }
    tier = model_gpu_tier
    if not gpu_info:
        return 0

    if isinstance(gpu_info, list):
        if not gpu_info:
            return 0
        gpu_info = gpu_info[0]

    vendor = gpu_info.get("vendor", "")
    vram = gpu_info.get("vram_total_mb", 0) or 0

    if vendor == "nvidia":
        cc = gpu_info.get("compute_capability", "")
        if cc:
            try:
                major = int(str(cc).split(".")[0])
                if major >= 8:
                    system_tier = "datacenter"
                elif major >= 7:
                    system_tier = "prosumer"
                else:
                    system_tier = "consumer"
            except (ValueError, IndexError):
                system_tier = "consumer" if vram < 8000 else "prosumer" if vram < 24000 else "datacenter"
        else:
            system_tier = "consumer" if vram < 8000 else "prosumer" if vram < 24000 else "datacenter"
    elif vendor == "apple":
        system_tier = "prosumer"
    elif vendor == "amd":
        system_tier = "prosumer" if vram >= 16000 else "consumer"
    elif vendor == "intel":
        system_tier = "consumer"
    else:
        system_tier = "consumer"

    model_level = tier_map.get(tier, 1)
    system_level = tier_map.get(system_tier, 1)

    if system_level >= model_level:
        return 20
    elif system_level + 1 >= model_level:
        return 10
    else:
        return 0


def match_models(system_specs, catalog):
    system = system_specs
    cpu = system.get("cpu", {})
    ram = system.get("ram", {})
    gpus = system.get("gpu", [])
    storage = system.get("storage", {})
    os_info = system.get("os", {})
    total_ram = ram.get("total_gb", 0) or 0
    free_storage = storage.get("free_gb", 0) or 0
    cpu_cores = cpu.get("logical_cores", 0) or 0

    is_apple_silicon = os_info.get("is_apple_silicon", False)

    if gpus:
        effective_vram = max((g.get("vram_total_mb", 0) or 0) for g in gpus) / 1024
    else:
        effective_vram = 0

    if is_apple_silicon or (gpus and gpus[0].get("memory_type") == "unified"):
        effective_vram = total_ram * 0.5

    results = []
    for model in catalog:
        model_vram = model.get("vram_gb", 0) or 0
        model_ram = model.get("ram_gb", 0) or 0
        model_storage = model.get("storage_gb", 0) or 0

        if model_vram > effective_vram:
            continue
        if model_ram > total_ram:
            continue
        if model_storage > free_storage:
            continue

        vram_headroom = max(0, effective_vram - model_vram)
        vram_score = min(40, (vram_headroom / max(effective_vram, 1)) * 40)

        ram_headroom = max(0, total_ram - model_ram)
        ram_score = min(20, (ram_headroom / max(total_ram, 1)) * 20)

        gpu_tier_score = _get_gpu_tier_score(gpus, model.get("gpu_tier", "consumer"))

        cpu_score = min(10, (cpu_cores / 16) * 10)

        apple_bonus = 10 if (is_apple_silicon or (gpus and gpus[0].get("memory_type") == "unified")) and _parse_params(model.get("params", "0")) < 13 else 0

        total_score = round(min(100, vram_score + ram_score + gpu_tier_score + cpu_score + apple_bonus), 1)

        results.append({
            "model": model,
            "score": total_score,
            "details": {
                "vram_score": round(vram_score, 1),
                "ram_score": round(ram_score, 1),
                "gpu_score": gpu_tier_score,
                "cpu_score": round(cpu_score, 1),
                "apple_bonus": apple_bonus,
                "vram_headroom_gb": round(vram_headroom, 1),
                "ram_headroom_gb": round(ram_headroom, 1),
                "vram_required_gb": model_vram,
                "ram_required_gb": model_ram,
                "effective_vram_gb": round(effective_vram, 1),
                "total_ram_gb": total_ram,
            },
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results
