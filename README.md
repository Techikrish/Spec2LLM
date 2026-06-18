# Spec2LLM

Find the best LLMs for your hardware specs. CLI tool that detects your system (CPU, GPU, RAM, storage) and recommends compatible models ranked by performance fit.

```bash
pip install spec2llm
spec2llm recommend
```

[![GitHub](https://img.shields.io/badge/GitHub-Techikrish/Spec2LLM-blue?logo=github)](https://github.com/Techikrish/Spec2LLM)

## Features

- **Hardware Detection** — CPU, GPU (NVIDIA/AMD/Apple/Intel), RAM, storage, OS — cross-platform
- **Smart Recommendations** — Models ranked by VRAM headroom, RAM availability, GPU compute tier, and CPU cores
- **Curated Catalog** — 40+ popular models (Llama 3, Mistral, Gemma, Qwen, DeepSeek, Phi, etc.) with tested requirements
- **Auto-Discovery** — `catalog update` fetches new models from Ollama registry with estimated requirements
- **Apple Silicon Support** — Detects unified memory and adjusts scoring accordingly
- **JSON Output** — `--json` flag on all commands for scripting/automation

## Commands

```
spec2llm scan              Detect system hardware specs
spec2llm recommend         Find best LLMs for your system
spec2llm search <query>    Search model catalog
spec2llm list              Browse all models
spec2llm install <model>   Show install command (Ollama/HF)
spec2llm compare <a> <b>   Side-by-side comparison
spec2llm catalog update    Discover new models from Ollama
```

### Options

Most commands support:
- `--json` — machine-readable JSON output
- `--top N` — limit recommendations (recommend)
- `--tag` — filter by tag like `code`, `vision`, `chat`
- `--run` — execute install command directly (install)

## Examples

```bash
# Quick recommendation
spec2llm recommend

# Filter by use case
spec2llm recommend --tag code --top 5

# Search for models
spec2llm search deepseek

# Compare two models
spec2llm compare llama-3.2-1b-q4 mistral-7b-q4

# See install command
spec2llm install llama-3.1-8b-q4

# Machine-readable output
spec2llm scan --json
```

## How It Works

1. **Scan** detects your CPU cores/freq, RAM total/available, GPU model/VRAM, free storage, and OS
2. **Match** filters models that fit your VRAM, RAM, and storage
3. **Score** (0-100): 40% VRAM headroom, 20% RAM headroom, 20% GPU tier match, 10% CPU cores, 10% Apple Silicon bonus
4. **Recommend** returns sorted list with scores and details

## Installation

```bash
pip install spec2llm
```

Or from source:

```bash
git clone https://github.com/Techikrish/Spec2LLM.git
cd Spec2LLM
pip install -e .
```

Requires Python 3.9+.

## New Models

When a new model is released:

```bash
spec2llm catalog update
```

This fetches available models from Ollama's registry and estimates their hardware requirements. Run `spec2llm recommend` to see if they fit your system.

## License

MIT
