# sage/agent.py
"""The agent: connects the LLM to the tool system via native tool calling.

Runs a bounded reasoning loop:
  1. Send conversation + tool schemas to the model.
  2. If the model returns tool_calls, execute them and append results.
  3. Repeat until the model returns a plain text answer or the cap is hit.

This same loop supports multi-step tasks (write -> run -> observe -> fix),
since each tool round feeds results back for the model to react to.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sage.llm_client import LLMClient
from sage.prompts import SYSTEM_PROMPT
from sage.tools import TOOL_SCHEMAS, ToolRegistry


@dataclass
class TurnResult:
    """Outcome of a single high-level agent turn.

    Attributes:
        answer: The assistant's final text answer for this turn.
        tool_calls_made: How many tool calls were executed this turn.
        steps: How many model<->tool rounds occurred this turn.
        stopped_reason: Why the loop ended ("answered" or "max_steps").
    """

    answer: str
    tool_calls_made: int
    steps: int
    stopped_reason: str


@dataclass
class Agent:
    """A coding agent driving tool use over a conversation.

    Attributes:
        llm: The LLM client wrapper.
        registry: The tool dispatch registry.
        max_tool_steps: Max model<->tool rounds within a single turn.
        verbose: If True, print a trace of tool activity.
        messages: The running conversation (system prompt seeded).
    """

    llm: LLMClient
    registry: ToolRegistry
    max_tool_steps: int = 20
    verbose: bool = True
    messages: list[dict[str, Any]] = field(default_factory=list)
    mode_state: Any = None  # agent.modes.ModeState; injected by CLI

    def _messages_with_mode(self) -> list[dict[str, Any]]:
        """Return messages, injecting the plan-mode note if active.

        The note is added as an ephemeral system message at the end so
        it steers the current step without permanently polluting history.

        Returns:
            A messages list suitable for the LLM call.
        """
        if self.mode_state is None:
            return self.messages
        note = self.mode_state.policy.plan_note
        if not note:
            return self.messages
        return self.messages + [{"role": "system", "content": note}]

    def __post_init__(self) -> None:
        """Seed the system prompt if the conversation is empty."""
        if not self.messages:
            self.messages.append({"role": "system", "content": SYSTEM_PROMPT})

    # ── Public API ────────────────────────────────────────────────

    def reset(self) -> None:
        """Clear the conversation, keeping only the system prompt."""
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def run_turn(self, user_input: str) -> TurnResult:
        """Process one user message to completion (through any tool calls).

        Args:
            user_input: The user's natural-language request.

        Returns:
            A TurnResult with the final answer and metadata.

        Raises:
            LLMError: If the underlying API calls fail unrecoverably.
        """
        self.messages.append({"role": "user", "content": user_input})
        total_calls = 0

        for step in range(1, self.max_tool_steps + 1):
            message = self.llm.complete(self._messages_with_mode(), tools=TOOL_SCHEMAS)
            tool_calls = getattr(message, "tool_calls", None)

            # Record the assistant message (with any tool_calls) verbatim.
            self.messages.append(self._assistant_dict(message))

            if not tool_calls:
                answer = message.content or "(no textual answer)"
                return TurnResult(answer, total_calls, step, "answered")

            if self.verbose:
                print(f"  ── step {step}: {len(tool_calls)} tool call(s) ──")

            for call in tool_calls:
                total_calls += 1
                self._execute_and_record(call)

        # Safety cap reached.
        note = (
            "Reached the maximum number of tool steps for this turn "
            f"({self.max_tool_steps}). The task may be incomplete."
        )
        self.messages.append({"role": "assistant", "content": note})
        return TurnResult(note, total_calls, self.max_tool_steps, "max_steps")

    def run_turn_multimodal(
        self, message: dict[str, Any]
    ) -> "TurnResult":
        """Process a pre-built multimodal user message to completion.

        Args:
            message: A user message dict whose content is a list of
                text/image blocks (see agent.attachments).

        Returns:
            A TurnResult with the final answer and metadata.
        """
        self.messages.append(message)
        total_calls = 0
        for step in range(1, self.max_tool_steps + 1):
            assistant = self.llm.complete(self._messages_with_mode(), tools=TOOL_SCHEMAS)
            tool_calls = getattr(assistant, "tool_calls", None)
            self.messages.append(self._assistant_dict(assistant))
            if not tool_calls:
                answer = assistant.content or "(no textual answer)"
                return TurnResult(answer, total_calls, step, "answered")
            if self.verbose:
                print(f"  ── step {step}: {len(tool_calls)} tool call(s) ──")
            for call in tool_calls:
                total_calls += 1
                self._execute_and_record(call)
        note = (
            "Reached the maximum number of tool steps for this turn "
            f"({self.max_tool_steps}). The task may be incomplete."
        )
        self.messages.append({"role": "assistant", "content": note})
        return TurnResult(note, total_calls, self.max_tool_steps, "max_steps")
    # ── Internals ─────────────────────────────────────────────────

    def _execute_and_record(self, call: Any) -> None:
        """Execute one tool call and append its result message.

        A failing tool never raises; the error text is fed back so the
        model can attempt to recover on the next step.

        Args:
            call: A tool_call object from the model response.
        """
        name = call.function.name
        raw_args = call.function.arguments or "{}"

        try:
            args = json.loads(raw_args)
            if not isinstance(args, dict):
                raise ValueError("arguments must be a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            output = f"Error: could not parse arguments for {name}: {exc}"
            if self.verbose:
                print(f"  ⚙️  {name}(<invalid args>) → {output}")
            self._append_tool_result(call.id, output)
            return

        if self.verbose:
            print(f"  ⚙️  {name}({self._preview_args(args)})")

        result = self.registry.call(name, args)

        if self.verbose:
            status = "ok" if result.ok else "error"
            print(f"     → [{status}] {self._preview(result.output)}")

        self._append_tool_result(call.id, result.output)

    def _append_tool_result(self, tool_call_id: str, output: str) -> None:
        """Append a tool-result message to the conversation.

        Args:
            tool_call_id: The id of the tool call being answered.
            output: The tool's textual output.
        """
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": output,
            }
        )

    @staticmethod
    def _assistant_dict(message: Any) -> dict[str, Any]:
        """Convert an assistant message object into an API-ready dict.

        Preserves tool_calls so the follow-up tool messages are valid.

        Args:
            message: The assistant ChatCompletionMessage.

        Returns:
            A dict suitable for appending to the messages list.
        """
        entry: dict[str, Any] = {
            "role": "assistant",
            "content": message.content or "",
        }
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            entry["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {
                        "name": c.function.name,
                        "arguments": c.function.arguments,
                    },
                }
                for c in tool_calls
            ]
        return entry

    @staticmethod
    def _preview_args(args: dict[str, Any], limit: int = 80) -> str:
        """Render tool arguments compactly for the trace."""
        parts = []
        for key, value in args.items():
            text = str(value).replace("\n", "\\n")
            if len(text) > limit:
                text = text[:limit] + "…"
            parts.append(f"{key}={text!r}")
        return ", ".join(parts)

    @staticmethod
    def _preview(text: str, limit: int = 120) -> str:
        """Collapse and truncate tool output for the trace."""
        flat = " ".join(str(text).split())
        return flat if len(flat) <= limit else flat[: limit - 1] + "…"