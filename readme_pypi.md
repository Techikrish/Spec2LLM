# Spec2LLM

**Find the best LLMs for your hardware.**

Detects your system specs (CPU, GPU, RAM, storage, OS) and recommends compatible LLMs ranked by performance fit. Works on **Linux**, **Windows**, and **macOS** — including Apple Silicon.

```bash
pip install spec2llm
spec2llm recommend
```

## Quick Start

```bash
# See what models fit your system
spec2llm recommend

# Search for specific models
spec2llm search deepseek

# Compare two models
spec2llm compare llama-3.2-1b-q4 mistral-7b-q4

# Discover new models
spec2llm catalog update

# JSON output for scripting
spec2llm scan --json
```

## Features

- **Cross-platform hardware detection** — CPU (cores, freq), GPU (NVIDIA VRAM, AMD, Apple Silicon), RAM, storage, OS
- **Smart scoring** — VRAM headroom (40%), RAM headroom (20%), GPU compute tier (20%), CPU cores (10%), Apple Silicon bonus (10%)
- **Curated catalog** — 40+ popular models (Llama 3.x, Mistral, Gemma, Qwen, DeepSeek, Phi, and more)
- **Auto-discovery** — Fetches new models from Ollama registry with estimated requirements
- **Apple Silicon** — Detects unified memory and adjusts scoring
- **JSON output** — `--json` flag on all commands

## Commands

| Command | Description |
|---|---|
| `spec2llm scan` | Detect and display all system hardware specs |
| `spec2llm recommend` | Find and rank best-matching LLMs |
| `spec2llm search <query>` | Search the model catalog |
| `spec2llm list` | Browse all models |
| `spec2llm install <model>` | Show install commands (Ollama, HuggingFace) |
| `spec2llm compare <a> <b>` | Compare two models vs your system |
| `spec2llm catalog update` | Fetch new models from Ollama registry |

## How It Works

1. **Scan** detects your CPU, RAM, GPU, storage, and OS
2. **Match** filters models that fit your VRAM, RAM, and storage
3. **Score** (0-100): VRAM headroom (40) + RAM headroom (20) + GPU tier (20) + CPU cores (10) + Apple Silicon bonus (10)
4. **Recommend** returns a sorted table with scores

## Requirements

- Python 3.9+

### Platform Support

| Feature | Linux | Windows | macOS |
|---|---|---|---|
| CPU / RAM / Storage | ✅ | ✅ | ✅ |
| NVIDIA GPU (VRAM) | ✅ | ✅ | ❌ |
| AMD / Intel GPU | ✅ lspci | ✅ wmi | ❌ |
| Apple Silicon | N/A | N/A | ✅ |

## License

MIT
