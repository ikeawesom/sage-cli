# sage/cli.py
"""Interactive terminal REPL for the coding agent.

Provides:
  - argparse flags (--mode, --auto alias, --model, --root, --no-verbose, --plain)
  - a prompt loop with slash commands (/help, /reset, /history, /mode, /attach)
  - operating modes (plan/normal/auto-edits/auto/bypass) shown in the prompt
  - persistent conversation context via a single Agent instance
  - rich-based formatting (with a plain fallback)
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from sage import __version__
from sage.agent import Agent
from sage.attachments import AttachmentError, build_multimodal_message
from sage.confirm import Confirmer
from sage.config import ConfigError, load_config
from sage.llm_client import LLMClient, LLMError
from sage.modes import Mode, ModeState
from sage.sandbox import Sandbox
from sage.tools import ToolRegistry, Tools

from rich.table import Table

from sage.models_catalog import CHAT_MODELS, find_by_id, get_by_index
from sage.persist import set_env_var
from sage.image_gen import ImageGenError, ImageGenerator, open_file


@dataclass
class CLIOptions:
    """Parsed command-line options.

    Attributes:
        mode: Initial operating mode.
        model: Optional model override.
        root: Sandbox root directory.
        verbose: Show tool-call trace.
        plain: Disable rich markdown rendering.
    """

    mode: Mode
    model: str | None
    root: str
    verbose: bool
    plain: bool


def parse_args(argv: list[str] | None = None) -> CLIOptions:
    """Parse command-line arguments into CLIOptions.

    Args:
        argv: Optional argument list (defaults to sys.argv).

    Returns:
        Parsed CLIOptions.
    """
    parser = argparse.ArgumentParser(
        prog="sage",
        description="Sage | Terminal-based AI Agent | Built by ikeawesom 2026",
    )
    parser.add_argument(
        "--mode",
        default="normal",
        help="Initial mode: plan | normal | auto-edits | auto | bypass "
        "(default: normal).",
    )
    parser.add_argument(
        "-y", "--auto", action="store_true",
        help="Alias for --mode auto (auto-approve writes + shell).",
    )
    parser.add_argument(
        "--model", default=None,
        help="Override the model ID (else uses MODEL from .env).",
    )
    parser.add_argument(
        "--root", default=".",
        help="Sandbox root directory (default: current directory).",
    )
    parser.add_argument(
        "--no-verbose", dest="verbose", action="store_false",
        help="Hide the step-by-step tool trace.",
    )
    parser.add_argument(
        "--plain", action="store_true",
        help="Disable rich markdown rendering (plain text output).",
    )
    parser.add_argument(
        "--version", action="version", version=f"Sage {__version__}",
    )
    ns = parser.parse_args(argv)

    mode_name = "auto" if ns.auto else ns.mode
    try:
        mode = Mode.from_str(mode_name)
    except ValueError as exc:
        parser.error(str(exc))

    return CLIOptions(
        mode=mode,
        model=ns.model,
        root=ns.root,
        verbose=ns.verbose,
        plain=ns.plain,
    )


class REPL:
    """The interactive read-eval-print loop."""

    def __init__(self, options: CLIOptions) -> None:
        """Initialize the REPL and its agent.

        Args:
            options: Parsed CLI options.

        Raises:
            ConfigError: If configuration is invalid.
        """
        self.options = options
        self.console = Console()

        config = load_config()
        if options.model:
            config = type(config)(
                api_key=config.api_key,
                base_url=config.base_url,
                model=options.model,
                ca_bundle=config.ca_bundle,
                verify_tls=config.verify_tls,
                image_model=config.image_model,
            )
        self.config = config

        # Shared mode state drives Confirmer + Tools + Agent.
        self.mode_state = ModeState(options.mode)

        sandbox = Sandbox(options.root)
        confirmer = Confirmer(self.mode_state, console=self.console)
        tools = Tools(sandbox, confirmer, self.mode_state)
        registry = ToolRegistry(tools)
        self._llm = LLMClient(config=config, console=self.console)

        self.agent = Agent(
            llm=self._llm,
            registry=registry,
            verbose=options.verbose,
            mode_state=self.mode_state,
        )

        self.sandbox = sandbox
        self._pending_attachments: list[str] = []
        self._image_gen = ImageGenerator(self.config, sandbox)

    # ── Rendering helpers ─────────────────────────────────────────

    def _generate_image(self, prompt: str) -> None:
        """Generate an image from a prompt, save it, and open it.

        Args:
            prompt: The text description of the image.
        """
        if not prompt:
            self.console.print("[red]Usage:[/] /image <description>")
            return

        with self.console.status("[dim]generating image…[/]", spinner="dots"):
            try:
                result = self._image_gen.generate(
                    prompt, model=self.config.image_model
                )
            except ImageGenError as exc:
                self.console.print(f"[red]Image generation failed:[/]\n{exc}")
                return

        # Show the full absolute path (forward slashes for readability).
        full_path = result.path.resolve().as_posix()
        self.console.print(
            f"[green]Image saved:[/] [cyan]{full_path}[/] "
            f"([dim]{result.model_used}[/])"
        )
        open_file(result.path)

    def _rebuild_llm(self, model_id: str) -> None:
        """Rebuild the LLM client with a new model, preserving context.

        Args:
            model_id: The model ID to switch to.
        """
        new_config = type(self.config)(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            model=model_id,
            ca_bundle=self.config.ca_bundle,
            verify_tls=self.config.verify_tls,
            image_model=self.config.image_model,
        )
        self.config = new_config
        self._llm = LLMClient(config=new_config, console=self.console)
        # Swap the client on the existing agent (keeps conversation history).
        self.agent.llm = self._llm

    def _show_models(self) -> None:
        """Display the curated model catalog as a table."""
        table = Table(title="Available Models", show_lines=False)
        table.add_column("#", justify="right", style="bold")
        table.add_column("Model", style="cyan")
        table.add_column("Category")
        table.add_column("Notes", style="dim")
        table.add_column("", justify="center")  # current marker

        for i, m in enumerate(CHAT_MODELS, 1):
            current = "◄ current" if m.model_id == self.config.model else ""
            table.add_row(
                str(i), m.label, m.category, m.note,
                f"[green]{current}[/]" if current else "",
            )
        self.console.print(table)
        self.console.print(
            "[dim]Switch with[/] [green]/model <number>[/] "
            "[dim]or[/] [green]/model <model-id>[/]"
        )

    def _switch_model(self, arg: str) -> None:
        """Show the catalog or switch to a chosen model.

        Args:
            arg: Empty to list; a number or model ID to switch.
        """
        if not arg:
            self._show_models()
            return

        info = None
        if arg.isdigit():
            info = get_by_index(int(arg))
            if info is None:
                self.console.print(
                    f"[red]No model #{arg}.[/] Use /model to list."
                )
                return
        else:
            info = find_by_id(arg)
            if info is None:
                self.console.print(
                    f"[red]Unknown model '{arg}'.[/] Use /model to list."
                )
                return

        if info.model_id == self.config.model:
            self.console.print(f"Already using [cyan]{info.label}[/].")
            return

        self._rebuild_llm(info.model_id)
        persisted = set_env_var("MODEL", info.model_id)
        suffix = "" if persisted else " [yellow](could not persist)[/]"
        self.console.print(
            f"Model → [cyan]{info.label}[/] "
            f"([dim]{info.model_id}[/]){suffix}"
        )

    def _render(self, text: str) -> None:
        """Render assistant text as markdown (or plain)."""
        if self.options.plain:
            self.console.print(text)
        else:
            self.console.print(Markdown(text))

    def _mode_tag(self) -> str:
        """Return a colored [mode] tag for the prompt/banner."""
        policy = self.mode_state.policy
        return f"[{policy.color}]{policy.label}[/]"

    def _banner(self) -> None:
        """Print the startup banner."""
        body = (
            f"model: [cyan]{self.config.model}[/]\n"
            f"root : [cyan]{self.sandbox.root}[/]\n"
            f"mode : {self._mode_tag()}\n\n"
            "Modes: [magenta]plan[/] · [green]normal[/] · [cyan]auto-edits[/] · "
            "[yellow]auto[/] · [red]bypass[/]\n"
            "Commands: [green]/help /model /mode /reset /history /attach /exit[/]"
        )
        self.console.print(
            Panel(body, title="🤖 Sage • Built by ikeawesom 2026", border_style="cyan")
        )

    def _help(self) -> None:
        """Print slash-command help."""
        self.console.print(
            Panel(
                "[green]/help[/]                [white]show this help\n"
                "[green]/model <n>[/]           [white]list models or switch\n"
                "[green]/mode <name>[/]         [white]show or switch mode\n"
                "[green]/image <prompt>[/]      [white]generate an image and open it\n"
                "[green]/reset[/]               [white]clear conversation context\n"
                "[green]/history[/]             [white]show message count + roles\n"
                "[green]/attach <path>[/]       [white]attach an image/PDF to next message\n"
                "[green]/attachments[/]         [white]list pending attachments\n"
                "[green]/exit[/]                [white]quit (also Ctrl-D / Ctrl-C)",
                title="Commands",
                border_style="green",
            )
        )

    def _mode_help(self) -> None:
        """Explain each mode briefly."""
        self.console.print(
            Panel(
                "[magenta]plan[/]        read-only; proposes a plan, no changes\n"
                "[green]normal[/]      confirm every write and shell command\n"
                "[cyan]auto-edits[/]  auto-approve writes; confirm shell\n"
                "[yellow]auto[/]        auto-approve writes + shell (deny-list ON)\n"
                "[red]bypass[/]      auto-approve everything (deny-list OFF!)",
                title="Modes",
                border_style="blue",
            )
        )

    def _history(self) -> None:
        """Show a compact summary of the conversation history."""
        counts: dict[str, int] = {}
        for msg in self.agent.messages:
            counts[msg["role"]] = counts.get(msg["role"], 0) + 1
        summary = ", ".join(f"{r}={n}" for r, n in counts.items())
        self.console.print(
            f"[dim]messages: {len(self.agent.messages)} ({summary})[/]"
        )

    # ── Command handling ──────────────────────────────────────────

    def _handle_command(self, line: str) -> bool:
        """Handle a slash command.

        Args:
            line: The user input starting with '/'.

        Returns:
            True to continue the loop, False to exit.
        """
        parts = line.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in {"/exit", "/quit", "/q"}:
            return False
        if cmd == "/help":
            self._help()
        elif cmd == "/image":
            self._generate_image(arg)
        elif cmd == "/mode":
            self._switch_mode(arg)
        elif cmd == "/model":
            self._switch_model(arg)
        elif cmd == "/reset":
            self.agent.reset()
            self._pending_attachments.clear()
            self.console.print("[yellow]Context cleared.[/]")
        elif cmd == "/history":
            self._history()
        elif cmd == "/attach":
            self._attach(arg)
        elif cmd == "/attachments":
            self._list_attachments()
        else:
            self.console.print(f"[red]Unknown command:[/] {line}")
        return True

    def _switch_mode(self, arg: str) -> None:
        """Show or change the current mode.

        Args:
            arg: Empty to show current mode + help, else a mode name.
        """
        if not arg:
            self.console.print(f"Current mode: {self._mode_tag()}")
            self._mode_help()
            return
        try:
            new_mode = Mode.from_str(arg)
        except ValueError as exc:
            self.console.print(f"[red]{exc}[/]")
            return
        self.mode_state.set(new_mode)
        self.console.print(f"Mode → {self._mode_tag()}")

    def _attach(self, path: str) -> None:
        """Queue a file to attach to the next message.

        Args:
            path: Attachment path relative to the sandbox root.
        """
        if not path:
            self.console.print("[red]Usage:[/] /attach <path>")
            return
        try:
            build_multimodal_message(self.sandbox, "probe", [path])
        except AttachmentError as exc:
            self.console.print(f"[red]Attach failed:[/] {exc}")
            return
        self._pending_attachments.append(path)
        self.console.print(
            f"[green]Attached[/] {path} "
            f"({len(self._pending_attachments)} pending)"
        )

    def _list_attachments(self) -> None:
        """Show currently pending attachments."""
        if not self._pending_attachments:
            self.console.print("[dim]No pending attachments.[/]")
            return
        for i, p in enumerate(self._pending_attachments, 1):
            self.console.print(f"  {i}. {p}")

    # ── Main loop ─────────────────────────────────────────────────

    def run(self) -> int:
        """Run the interactive loop until the user exits.

        Returns:
            Process exit code.
        """
        self._banner()
        while True:
            try:
                prompt = f"\n{self._mode_tag()} [bold blue]›[/] "
                line = self.console.input(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[dim]Goodbye.[/]")
                return 0

            if not line:
                continue
            if line.startswith("/"):
                if not self._handle_command(line):
                    self.console.print("[dim]Goodbye.[/]")
                    return 0
                continue

            try:
                self._run_request(line)
            except LLMError as exc:
                self.console.print(f"[red]LLM error:[/] {exc}")
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Interrupted this request.[/]")

    def _run_request(self, line: str) -> None:
        """Process one user request and render the answer.

        Args:
            line: The user's natural-language request.
        """

        if self.options.verbose:
            self.console.rule("[dim]working[/]")

        if self._pending_attachments:
            try:
                message = build_multimodal_message(
                    self.sandbox, line, list(self._pending_attachments)
                )
            except AttachmentError as exc:
                self.console.print(f"[red]Attachment error:[/] {exc}")
                return
            
            result = self.agent.run_turn_multimodal(message)

            self.console.print(
                f"[dim](sent {len(self._pending_attachments)} attachment(s) "
                "as visual input)[/]"
            )
            
            self._pending_attachments.clear()
        else:
            result = self.agent.run_turn(line)

        if self.options.verbose:
            self.console.rule()

        self._render(result.answer)
        self.console.print(
            f"[dim]— {result.steps} step(s), "
            f"{result.tool_calls_made} tool call(s), "
            f"{result.stopped_reason} · mode={self.mode_state.policy.label} —[/]"
        )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Optional argument list.

    Returns:
        Process exit code.
    """
    options = parse_args(argv)
    try:
        repl = REPL(options)
    except ConfigError as exc:
        print(f"[config error] {exc}", file=sys.stderr)
        return 1
    return repl.run()


if __name__ == "__main__":
    raise SystemExit(main())