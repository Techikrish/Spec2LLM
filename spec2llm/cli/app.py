import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich import box

from spec2llm.core.system_detector import detect_all
from spec2llm.core.gpu_detector import detect_gpus
from spec2llm.core.model_catalog import (
    load_catalog,
    search_catalog,
    get_model,
    update_from_ollama,
    save_catalog,
    list_by_tags,
)
from spec2llm.core.matcher import match_models

app = typer.Typer(
    name="spec2llm",
    help="Find the best LLMs for your hardware specs",
    rich_markup_mode="rich",
)
console = Console()
err_console = Console(stderr=True)


def _build_system_specs():
    specs = detect_all()
    gpus = detect_gpus()
    specs["gpu"] = gpus or []
    return specs


def _format_size_gb(size_gb):
    if size_gb >= 1024:
        return f"{size_gb / 1024:.1f} TB"
    return f"{size_gb:.1f} GB"


@app.command()
def scan(
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON"
    ),
):
    """Detect your system hardware specs"""
    with console.status("Scanning system hardware...", spinner="dots"):
        specs = _build_system_specs()

    if json_output:
        console.print(json.dumps(specs, indent=2, default=str))
        return

    cpu = specs["cpu"]
    ram = specs["ram"]
    storage = specs["storage"]
    os_info = specs["os"]
    gpus = specs["gpu"]

    table = Table(title="System Specifications", box=box.ROUNDED)
    table.add_column("Component", style="cyan")
    table.add_column("Detail", style="white")

    cpu_model = cpu.get("model", "Unknown")
    cpu_cores = f'{cpu.get("physical_cores", "?")} physical / {cpu.get("logical_cores", "?")} logical'
    cpu_freq = cpu.get("max_freq_mhz", None)
    cpu_line = f"{cpu_model}\n  Cores: {cpu_cores}"
    if cpu_freq:
        cpu_line += f"\n  Max Freq: {cpu_freq:.0f} MHz"
    table.add_row("CPU", cpu_line)

    ram_total = ram.get("total_gb", 0)
    ram_avail = ram.get("available_gb", 0)
    ram_used = ram.get("used_gb", 0)
    table.add_row(
        "RAM",
        f"Total: {_format_size_gb(ram_total)}\n"
        f"Available: {_format_size_gb(ram_avail)}\n"
        f"Used: {_format_size_gb(ram_used)} ({ram.get('percent_used', 0):.0f}%)",
    )

    storage_total = storage.get("total_gb", 0)
    storage_free = storage.get("free_gb", 0)
    table.add_row(
        "Storage (Home)",
        f"Total: {_format_size_gb(storage_total)}\n"
        f"Free: {_format_size_gb(storage_free)}",
    )

    if gpus:
        for i, gpu in enumerate(gpus):
            gpu_name = gpu.get("name", "Unknown GPU")
            gpu_vram = gpu.get("vram_total_mb", 0)
            gpu_vram_free = gpu.get("vram_free_mb", 0)
            gpu_vendor = gpu.get("vendor", "unknown")
            gpu_mem_type = gpu.get("memory_type", "unknown")
            gpu_driver = gpu.get("driver_version", None)

            lines = [gpu_name]
            if gpu_vram:
                lines.append(f"VRAM: {_format_size_gb(gpu_vram / 1024)}")
            if gpu_vram_free:
                lines.append(f"VRAM Free: {_format_size_gb(gpu_vram_free / 1024)}")
            if gpu_vendor != "unknown":
                lines.append(f"Vendor: {gpu_vendor.capitalize()}")
            lines.append(f"Memory: {gpu_mem_type}")
            if gpu_driver:
                lines.append(f"Driver: {gpu_driver}")
            if "unified_ram_total_gb" in gpu:
                lines.append(
                    f"Unified RAM: {_format_size_gb(gpu['unified_ram_total_gb'])}"
                )

            table.add_row(f"GPU {i + 1}", "\n".join(lines))
    else:
        table.add_row("GPU", "[yellow]No GPU detected (CPU-only mode)[/yellow]")

    table.add_row(
        "OS",
        f"{os_info.get('system', '')} {os_info.get('release', '')}\n"
        f"Machine: {os_info.get('machine', '')}",
    )
    if os_info.get("is_apple_silicon"):
        table.add_row("Architecture", "[green]Apple Silicon (ARM64)[/green]")

    console.print(table)


@app.command()
def recommend(
    top_k: int = typer.Option(
        10, "--top", "-t", help="Number of top recommendations to show"
    ),
    min_score: float = typer.Option(
        0, "--min-score", "-m", help="Minimum score filter (0-100)"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON"
    ),
    tag: str = typer.Option(
        None, "--tag", help="Filter by tag (e.g. code, vision, chat)"
    ),
):
    """Find best LLMs for your system"""
    with console.status("Scanning system...", spinner="dots"):
        specs = _build_system_specs()

    catalog = load_catalog()
    if tag:
        catalog = list_by_tags([tag], catalog)

    if not catalog:
        err_console.print("[red]No models found in catalog.[/red]")
        raise typer.Exit(1)

    with console.status("Matching models to your system...", spinner="dots"):
        results = match_models(specs, catalog)

    results = [r for r in results if r["score"] >= min_score]
    results = results[:top_k]

    if not results:
        console.print(
            "[yellow]No compatible models found for your system.[/yellow]"
        )
        console.print("Try models with lower VRAM/RAM requirements.")
        return

    if json_output:
        console.print(json.dumps(results, indent=2, default=str))
        return

    gpus = specs.get("gpu", [])
    if gpus:
        gpu_info = f"{gpus[0].get('name', 'Unknown')}"
        if gpus[0].get("vram_total_mb"):
            gpu_info += f" ({_format_size_gb(gpus[0]['vram_total_mb'] / 1024)} VRAM)"
    else:
        gpu_info = "CPU-only"
    ram_info = _format_size_gb(specs["ram"]["total_gb"])

    console.print(
        f"[bold]System:[/bold] {gpu_info} | {ram_info} RAM | "
        f"{specs['cpu'].get('logical_cores', '?')} cores"
    )
    console.print()

    table = Table(box=box.ROUNDED)
    table.add_column("#", style="dim", width=3)
    table.add_column("Model", style="cyan", no_wrap=True)
    table.add_column("Params", style="white")
    table.add_column("Quant", style="blue")
    table.add_column("VRAM", justify="right")
    table.add_column("RAM", justify="right")
    table.add_column("Score", justify="right", style="green")

    for i, r in enumerate(results, 1):
        m = r["model"]
        table.add_row(
            str(i),
            m["name"],
            m.get("params", "?"),
            m.get("quant", "?"),
            _format_size_gb(m.get("vram_gb", 0)),
            _format_size_gb(m.get("ram_gb", 0)),
            f"{r['score']:.0f}/100",
        )

    console.print(table)
    console.print()
    console.print("[dim]Run [bold]spec2llm install <model>[/bold] to see install command[/dim]")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON"
    ),
):
    """Search model catalog"""
    catalog = load_catalog()
    results = search_catalog(query, catalog)

    if not results:
        console.print(f"[yellow]No models found matching '{query}'[/yellow]")
        return

    if json_output:
        console.print(json.dumps(results, indent=2, default=str))
        return

    table = Table(title=f"Models matching '{query}'", box=box.ROUNDED)
    table.add_column("Model", style="cyan", no_wrap=True)
    table.add_column("Params", style="white")
    table.add_column("Quant", style="blue")
    table.add_column("VRAM", justify="right")
    table.add_column("RAM", justify="right")
    table.add_column("Tags")
    table.add_column("Source")

    for m in results:
        table.add_row(
            m["name"],
            m.get("params", "?"),
            m.get("quant", "?"),
            _format_size_gb(m.get("vram_gb", 0)),
            _format_size_gb(m.get("ram_gb", 0)),
            ", ".join(m.get("tags", [])),
            m.get("source", "?"),
        )

    console.print(table)


@app.command()
def install(
    model_name: str = typer.Argument(..., help="Model name or ID"),
    run: bool = typer.Option(False, "--run", help="Execute the install command"),
):
    """Show how to install/run a model"""
    catalog = load_catalog()
    model = get_model(model_name, catalog)

    if not model:
        models = search_catalog(model_name, catalog)
        if not models:
            err_console.print(
                f"[red]Model '{model_name}' not found in catalog.[/red]"
            )
            err_console.print("Try [bold]spec2llm search[/bold] to find models.")
            raise typer.Exit(1)
        model = models[0]

    console.print(f"[bold]{model['name']}[/bold]")
    console.print()

    specs_table = Table(box=box.SIMPLE)
    specs_table.add_column("Requirement")
    specs_table.add_column("Value")
    specs_table.add_row("VRAM", _format_size_gb(model.get("vram_gb", 0)))
    specs_table.add_row("RAM", _format_size_gb(model.get("ram_gb", 0)))
    specs_table.add_row("Storage", _format_size_gb(model.get("storage_gb", 0)))
    specs_table.add_row("Parameters", model.get("params", "?"))
    specs_table.add_row("Quantization", model.get("quant", "?"))
    console.print(specs_table)
    console.print()

    ollama_tag = model.get("ollama_tag")
    hf_id = model.get("hf_id")

    console.print("[bold]Install commands:[/bold]")

    if ollama_tag:
        console.print(f"  [green]Ollama:[/green] ollama pull {ollama_tag}")
    if hf_id:
        console.print(f"  [green]HuggingFace:[/green] huggingface-cli download {hf_id}")

    console.print()
    console.print("[yellow]llama.cpp:[/yellow]  Download GGUF files from HuggingFace for this model")

    if run and ollama_tag:
        import subprocess
        with console.status(f"Running ollama pull {ollama_tag}..."):
            result = subprocess.run(
                ["ollama", "pull", ollama_tag],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                console.print("[green]Done! Run: ollama run {ollama_tag}[/green]")
            else:
                err_console.print(f"[red]Failed: {result.stderr}[/red]")


@app.command(name="list")
def list_models(
    source: str = typer.Option(
        None, "--source", "-s", help="Filter by source (ollama, auto, etc.)"
    ),
    tag: str = typer.Option(
        None, "--tag", "-t", help="Filter by tag"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON"
    ),
):
    """List all models in the catalog"""
    catalog = load_catalog()

    if source:
        catalog = [m for m in catalog if m.get("source") == source]
    if tag:
        catalog = [m for m in catalog if tag in m.get("tags", [])]

    if not catalog:
        console.print("[yellow]No models match the filters.[/yellow]")
        return

    if json_output:
        console.print(json.dumps(catalog, indent=2, default=str))
        return

    table = Table(title=f"Model Catalog ({len(catalog)} models)", box=box.ROUNDED)
    table.add_column("Model", style="cyan", no_wrap=True)
    table.add_column("Params", style="white")
    table.add_column("Quant", style="blue")
    table.add_column("VRAM", justify="right")
    table.add_column("RAM", justify="right")
    table.add_column("Tags")
    table.add_column("Source")

    for m in sorted(catalog, key=lambda x: x.get("vram_gb", 0)):
        table.add_row(
            m["name"],
            m.get("params", "?"),
            m.get("quant", "?"),
            _format_size_gb(m.get("vram_gb", 0)),
            _format_size_gb(m.get("ram_gb", 0)),
            ", ".join(m.get("tags", [])),
            m.get("source", "?"),
        )

    console.print(table)


@app.command()
def compare(
    model_a: str = typer.Argument(..., help="First model name"),
    model_b: str = typer.Argument(..., help="Second model name"),
):
    """Compare two models' requirements vs your system"""
    catalog = load_catalog()

    a = get_model(model_a, catalog)
    if not a:
        err_console.print(f"[red]Model '{model_a}' not found[/red]")
        raise typer.Exit(1)
    b = get_model(model_b, catalog)
    if not b:
        err_console.print(f"[red]Model '{model_b}' not found[/red]")
        raise typer.Exit(1)

    with console.status("Scanning system..."):
        specs = _build_system_specs()

    results = match_models(specs, [a, b])
    score_map = {r["model"]["id"]: r for r in results}

    table = Table(title="Model Comparison", box=box.ROUNDED)
    table.add_column("")
    table.add_column(a["name"], style="cyan")
    table.add_column(b["name"], style="cyan")

    table.add_row("Parameters", a.get("params", "?"), b.get("params", "?"))
    table.add_row("Quantization", a.get("quant", "?"), b.get("quant", "?"))
    table.add_row("VRAM Required", _format_size_gb(a.get("vram_gb", 0)), _format_size_gb(b.get("vram_gb", 0)))
    table.add_row("RAM Required", _format_size_gb(a.get("ram_gb", 0)), _format_size_gb(b.get("ram_gb", 0)))
    table.add_row("Storage Required", _format_size_gb(a.get("storage_gb", 0)), _format_size_gb(b.get("storage_gb", 0)))

    a_score = score_map.get(a["id"], {}).get("score", 0)
    b_score = score_map.get(b["id"], {}).get("score", 0)
    table.add_row(
        "Compatibility Score",
        f"[green]{a_score:.0f}/100[/green]" if a_score > 0 else "[red]Incompatible[/red]",
        f"[green]{b_score:.0f}/100[/green]" if b_score > 0 else "[red]Incompatible[/red]",
    )

    table.add_row("Tags", ", ".join(a.get("tags", [])), ", ".join(b.get("tags", [])))
    table.add_row("Source", a.get("source", "?"), b.get("source", "?"))

    console.print(table)


@app.command()
def catalog(
    action: str = typer.Argument(
        "list", help="Action: list, search, update, show"
    ),
    query: str = typer.Option(
        None, "--query", "-q", help="Search query (for search/show)"
    ),
):
    """Manage model catalog"""
    if action == "update":
        with console.status("Fetching new models from Ollama registry...", spinner="dots"):
            catalog = load_catalog()
            updated_catalog, new_models = update_from_ollama(catalog)
            save_catalog(updated_catalog)
        if new_models:
            console.print(
                f"[green]Added {len(new_models)} new model(s) from Ollama:[/green]"
            )
            for m in new_models:
                console.print(
                    f"  [cyan]{m['name']}[/cyan] "
                    f"({m['params']}, {m['vram_gb']} GB VRAM, "
                    f"[yellow]estimated[/yellow])"
                )
        else:
            console.print("[green]Catalog is already up to date.[/green]")
    elif action == "show":
        catalog = load_catalog()
        if not query:
            err_console.print("[red]--query required for 'show' action[/red]")
            raise typer.Exit(1)
        model = get_model(query, catalog)
        if not model:
            err_console.print(f"[red]Model '{query}' not found[/red]")
        else:
            console.print(json.dumps(model, indent=2))
    else:
        list_models()


def main():
    if len(sys.argv) > 1:
        app()
    else:
        scan()


if __name__ == "__main__":
    main()
