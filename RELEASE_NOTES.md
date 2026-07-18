# Sage v0.1.0 — first public release 🧙

Sage is a smart AI assistant that lives right in your terminal. Type what you want in plain English, and Sage helps you get it done — reading and writing files, running tasks, understanding images, and even creating them. It connects to any OpenAI-compatible API endpoint (like a LiteLLM proxy), so you can point it at whatever models your provider offers.

This is Sage's first public release, available now on PyPI.

## Highlights

- 💬 **Conversational terminal assistant** — talk to Sage in plain English instead of memorizing commands.
- 🔌 **Works with any OpenAI-compatible endpoint** — bring your own LiteLLM proxy or compatible API; Sage isn't locked to one provider.
- 📂 **File operations and task execution** — Sage can read, write, and organize files, and run tasks for you inside the folder you open it in.
- 🖼️ **Image analysis** — attach an image with `/attach` and ask Sage what's in it.
- 🎨 **Image generation** — create images from a text description with `/image`.
- 🎚️ **Safety modes** — choose how much Sage does on its own with `/mode plan`, `/mode normal` (default), `/mode auto-edits`, or `/mode auto`.
- 🧭 **First-run guided setup** — no manual config file editing required; Sage walks you through entering your endpoint URL and API key the first time you run it.
- 🤖 **Model switching** — list and switch between the AI models your endpoint offers with `/model`.

## Installation

Sage is installed with [pipx](https://pipx.pypa.io/), which keeps it in its own isolated environment.

```
python -m pip install --user pipx
python -m pipx ensurepath
```

Open a new terminal, then install Sage:

```
pipx install sagecli
```

Run it:

```
sage
```

The first time you run `sage`, it will start a short guided setup to collect your endpoint URL and API key — no manual editing needed.

**Requirements:**
- Python 3.10 or newer
- An OpenAI-compatible API endpoint URL
- An API key for that endpoint

To upgrade later: `pipx upgrade sagecli`

---

Enjoy using Sage! For full usage details, modes, and troubleshooting, see the [README](https://github.com/ikeawesom/sage-cli#readme).
