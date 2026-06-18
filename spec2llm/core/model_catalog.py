import json
import os
import re
from pathlib import Path


def _get_data_path():
    return Path(__file__).resolve().parent.parent / "data" / "models.json"


def _estimate_requirements(params_b, quant):
    base = params_b * 2
    multipliers = {"q4": 0.25, "q4_k_m": 0.25, "q5": 0.3125, "q8": 0.5, "fp16": 1.0, "f32": 2.0}
    mul = 0.25
    for key, value in multipliers.items():
        if key in quant.lower().replace("_", ""):
            mul = value
            break
    model_gb = round(base * mul, 1)
    overhead = 1.0 + (0.5 if params_b > 30 else 0)
    return {
        "vram_gb": round(model_gb + overhead, 1),
        "ram_gb": round(model_gb + overhead + 1, 1),
        "storage_gb": model_gb,
    }


def _parse_params(params_str):
    params_str = str(params_str).upper().replace("B", "").strip()
    try:
        return float(params_str)
    except ValueError:
        return 0


def load_catalog():
    path = _get_data_path()
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def search_catalog(query, catalog=None):
    if catalog is None:
        catalog = load_catalog()
    query = query.lower().strip()
    results = []
    for model in catalog:
        searchable = f"{model['name']} {' '.join(model['tags'])} {model['id']}"
        if query in searchable.lower():
            results.append(model)
    return results


def get_model(name, catalog=None):
    if catalog is None:
        catalog = load_catalog()
    for model in catalog:
        if model["id"] == name or model["name"].lower() == name.lower():
            return model
    return None


def list_by_tags(tags, catalog=None):
    if catalog is None:
        catalog = load_catalog()
    return [m for m in catalog if any(t in m.get("tags", []) for t in tags)]


def add_estimated_model(catalog, name, params_b, quant="Q4_K_M", source="auto"):
    existing = get_model(name, catalog)
    if existing:
        return catalog
    reqs = _estimate_requirements(params_b, quant)
    entry = {
        "id": name.lower().replace(" ", "-").replace(":", "-"),
        "name": name,
        "params": f"{params_b}B" if params_b >= 1 else f"{int(params_b * 1000)}M",
        "quant": quant.upper(),
        "vram_gb": reqs["vram_gb"],
        "ram_gb": reqs["ram_gb"],
        "storage_gb": reqs["storage_gb"],
        "gpu_tier": "consumer" if reqs["vram_gb"] <= 24 else "prosumer" if reqs["vram_gb"] <= 48 else "datacenter",
        "source": source,
        "tags": ["auto-discovered"],
    }
    catalog.append(entry)
    return catalog


def _fetch_ollama_registry():
    import httpx
    try:
        resp = httpx.get("https://registry.ollama.ai/v2/_catalog", timeout=30)
        if resp.status_code != 200:
            return []
        data = resp.json()
        repos = data.get("repositories", [])
        models = []
        for repo in repos:
            tags_resp = httpx.get(
                f"https://registry.ollama.ai/v2/{repo}/tags", timeout=15
            )
            if tags_resp.status_code == 200:
                tags_data = tags_resp.json()
                for tag_entry in tags_data.get("tags", []):
                    tag_name = tag_entry.get("tag", "latest")
                    models.append({"repo": repo, "tag": tag_name})
        return models
    except Exception:
        return []


def update_from_ollama(catalog):
    new_models = []
    remote_models = _fetch_ollama_registry()
    existing_ids = {m["id"] for m in catalog}
    existing_ollama_tags = {m.get("ollama_tag", "").replace(":", ":latest").split(":")[0] for m in catalog}

    for rm in remote_models:
        full_name = f"{rm['repo']}:{rm['tag']}"
        repo_base = rm["repo"]
        if repo_base in existing_ollama_tags:
            continue
        model_id = repo_base.lower().replace("/", "-")
        if model_id in existing_ids:
            continue
        params = _infer_params_from_name(rm["repo"])
        if params > 0:
            entry = {
                "id": model_id,
                "name": rm["repo"],
                "params": f"{params}B" if params >= 1 else f"{int(params * 1000)}M",
                "quant": "Q4_K_M",
                "ollama_tag": f"{rm['repo']}:{rm['tag']}",
                "source": "ollama_auto",
                "tags": ["auto-discovered"],
            }
            reqs = _estimate_requirements(params, "Q4_K_M")
            entry.update(reqs)
            entry["gpu_tier"] = (
                "consumer" if entry["vram_gb"] <= 24
                else "prosumer" if entry["vram_gb"] <= 48
                else "datacenter"
            )
            new_models.append(entry)
            existing_ids.add(model_id)

    catalog.extend(new_models)
    return catalog, new_models


def _infer_params_from_name(name):
    parts = name.lower().replace("-", " ").replace("_", " ").split()
    for i, part in enumerate(parts):
        match = re.match(r"(\d+\.?\d*)(b|m)", part)
        if match:
            val = float(match.group(1))
            unit = match.group(2)
            return val if unit == "b" else val / 1000
    for i, part in enumerate(parts):
        if part.isdigit() and i + 1 < len(parts) and parts[i + 1] in ("b", "bn", "billion"):
            return float(part)
    return 7


def save_catalog(catalog):
    path = _get_data_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(catalog, f, indent=2)
