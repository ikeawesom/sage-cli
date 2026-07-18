# 🧙 Sage — Your AI Assistant in the Terminal

Sage is a smart AI helper that lives in your computer's terminal. You type
what you want in plain English, and Sage helps you get it done — reading and
writing files, running tasks, understanding images, and even creating images.

Think of it as a helpful assistant you can chat with, right in your terminal.

Sage connects to any **OpenAI-compatible API endpoint** (such as a
[LiteLLM](https://github.com/BerriAI/litellm) proxy), so you can point it at
whatever models your provider offers.

---

## ⚠️ Before You Start

You need **three things** for Sage to work:

1. **Python installed** on your computer (version 3.10 or newer). If you
   don't have it, download it from https://www.python.org/downloads/ and
   during installation, **tick the box that says "Add python.exe to PATH"**.
2. **An API endpoint URL** — the address of your OpenAI-compatible / LiteLLM
   server (for example, `https://your-litellm-server.com`).
3. **An API key** for that endpoint.

*(If you don't have the endpoint URL or key, ask whoever set up your AI
gateway.)*

---

## 📥 How to Install (One Time)

Sage is installed with [pipx](https://pipx.pypa.io/), a tool that installs
Python command-line apps in their own isolated environment so they don't
clash with anything else on your machine.

1. **Install pipx** (skip if you already have it) — open a terminal and run:
   ```
   python -m pip install --user pipx
   python -m pipx ensurepath
   ```

2. **Close that terminal and open a new one.**
   (Search for "Command Prompt" or "Terminal" in the Windows Start menu.)
   This step is needed so your terminal picks up the updated PATH.

3. **Install Sage:**
   ```
   pipx install sagecli
   ```

4. **Test it** — type this and press Enter:
   ```
   sage --version
   ```
   If you see a version number, you're ready! 🎉

You only do this once. To upgrade later, run `pipx upgrade sagecli`.

---

## ⚙️ Your Settings

Sage reads its settings from a file at:

```
C:\Users\<your-name>\.sage\.env
```

This file doesn't exist yet after a fresh `pipx install` — you need to
create it yourself, once. Sage checks for it every time it starts; if the
required settings aren't there, it won't run and will tell you what's
missing.

**To create it:**

1. Create a folder called `.sage` in your user folder (`C:\Users\<your-name>\.sage`).
2. Inside it, create a text file named `.env` (make sure it's not saved as
   `.env.txt` — in Notepad, choose "All Files" as the type when saving).
3. Add your settings, one per line, like this:
   ```
   API_KEY=your-api-key-here
   BASE_URL=https://your-litellm-server.com
   MODEL=claude-opus-4-8
   IMAGE_MODEL=gemini-3-pro-image
   VERIFY_TLS=true
   ```

You can edit this file anytime to change your endpoint, key, or preferred
model. The available settings are:

| Setting       | What it is                                  |
|---------------|----------------------------------------------|
| `API_KEY`     | Your API key                                |
| `BASE_URL`    | Your endpoint URL                           |
| `MODEL`       | The default AI model to chat with           |
| `IMAGE_MODEL` | The model used for creating images          |
| `VERIFY_TLS`  | Set to `false` if your server uses a private certificate |

`API_KEY` and `BASE_URL` are required — Sage won't start without them.
`MODEL`, `IMAGE_MODEL`, and `VERIFY_TLS` are optional and fall back to
sensible defaults if you leave them out.

---

## 🚀 How to Use Sage

1. Open a terminal **in the folder you want to work in**.
   *(Tip: in File Explorer, type `cmd` in the address bar and press Enter to
   open a terminal in that folder.)*

2. Type:
   ```
   sage
   ```

3. Now just **talk to it** in plain English. For example:
   ```
   › summarize what the files in this folder are about
   › create a to-do list file with 5 example tasks
   › what does this spreadsheet contain?
   ```

4. When you're done, type `/exit` or press `Ctrl + C`.

---

## 🎨 Fun & Useful Things Sage Can Do

### Look at an image and describe it
```
› /attach photo.png
› what's in this picture?
```
*(Replace `photo.png` with your image's name. It must be in the same folder.)*

### Create an image from words
```
› /image a cute cartoon airplane flying over clouds
```
Sage will create the image, save it in your folder, and open it for you.

### Ask it to do a task and check its own work
```
› create a file called notes.txt with today's date, then show me it worked
```

---

## 🎚️ Modes — Controlling How Much Sage Does on Its Own

Sage asks for your permission before making changes. You can change how
cautious it is by typing `/mode` followed by a name:

| Type this          | What it does                                        |
|---------------------|-----------------------------------------------------|
| `/mode plan`        | Only looks and suggests — **changes nothing**       |
| `/mode normal`      | Asks you before every change *(this is the default)*|
| `/mode auto-edits`  | Edits files automatically, asks before running tasks|
| `/mode auto`        | Does everything automatically (still safe)          |

**Tip for beginners:** stay in **normal** mode. It always asks first, so
nothing happens without your OK.

---

## 💬 Handy Commands

Type these at any time:

| Command            | What it does                                |
|---------------------|---------------------------------------------|
| `/help`             | Shows the list of commands                  |
| `/mode`             | Shows or changes how cautious Sage is       |
| `/model`            | Shows the AI models you can pick from       |
| `/image <words>`    | Creates a picture from your description     |
| `/attach <file>`    | Adds an image so Sage can look at it        |
| `/reset`            | Starts a fresh conversation                 |
| `/exit`             | Closes Sage                                 |

---

## 🤖 Choosing a Different AI Model

Different AI models are better at different things. To see and switch:

```
› /model
```
You'll see a numbered list. To switch, type `/model` and a number:
```
› /model 2
```
Sage remembers your choice for next time.

> **Note:** The models Sage can use depend on what your API endpoint
> provides. If you pick a model your endpoint doesn't offer, Sage will let
> you know.

---

## 🔒 Is It Safe?

Yes — Sage is built to be careful:

- It only works inside the folder you open it in. It **can't touch the rest
  of your computer**.
- It **asks before making changes** (in normal mode).
- It **refuses dangerous commands** (like deleting everything).
- Before editing a file, it **shows you exactly what will change**.

---

## 📤 Sharing Sage With Someone Else

Want to give Sage to a colleague? There's no package to build or file to
send — Sage is published on PyPI, so anyone can install it the same way you
did.

Just point them at this same guide, or tell them:

1. Install pipx (if they don't have it):
   ```
   python -m pip install --user pipx
   python -m pipx ensurepath
   ```
2. Open a new terminal, then install Sage:
   ```
   pipx install sagecli
   ```
3. Create their own `C:\Users\<their-name>\.sage\.env` file with **their
   own** endpoint URL and API key (see "Your Settings" above).
4. Type `sage` to start.

Each person uses their own API key in their own `.env` file, so nobody's
credentials are shared.

*(They'll need Python 3.10+ installed, plus their own endpoint URL and API
key.)*

---

## ❓ Something Went Wrong?

**"sage is not recognized"**
Close the terminal and open a brand-new one — pipx needs a fresh terminal to
pick up the PATH changes. If it still doesn't work, run
`python -m pipx ensurepath` again, then open another new terminal.

**"Connection error"**
Sage can't reach your endpoint. Check that the `BASE_URL` in your settings is
correct and that you can reach the server (e.g. you're on the right network
or VPN if it's a private endpoint).

**"[config error] Missing API_KEY" or "Missing BASE_URL"**
Your settings file is missing a value, or doesn't exist yet. Create or edit
`C:\Users\<your-name>\.sage\.env` and fill in `API_KEY` and `BASE_URL` (see
"Your Settings" above).

**"team not allowed to access model" / model error**
The selected model isn't available on your endpoint. Use `/model` to pick a
different one.

**Sage can't see my image**
Make sure the image is in the same folder you opened Sage in, and that you
typed `/attach` with the correct file name first. Also make sure your chosen
model supports image analysis.

---

## 📝 Quick Reference Card

```
Install:           pipx install sagecli
Start Sage:        sage
Ask something:     just type it and press Enter
Look at an image:  /attach picture.png   then ask about it
Make an image:     /image a sunset over the ocean
Change caution:    /mode plan | normal | auto-edits | auto
Pick a model:      /model   then   /model <number>
Get help:          /help
Quit:              /exit
```

Enjoy using Sage! 🧙✨
