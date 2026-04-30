"""
EpicWorkerAgent for v3 Epic Mode.

Handles one task at a time.  Each task gets its own session (FileSessionManager
with a task-scoped session_id).  The agent does NOT interact with the user
directly; it is invoked as a Strands tool (run_epic_worker) and returns a
structured YAML string to EpicManagerAgent.

Usage
-----
    worker = EpicWorkerAgent(
        epic_id="auth-cognito-migration",
        task_id="T001",
        repo_root=Path("/path/to/target/repo"),
    )
    result_yaml = worker(task_instruction)

Tool sandboxing
---------------
All tools given to the Worker are sandboxed to *repo_root* via
``make_epic_worker_tools(repo_root)``.  The Worker cannot read or write
files outside that directory, and all git / GitHub CLI operations target
that repository.  This is intentional: each Worker is responsible for
exactly one repository.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from strands import Agent
from strands.agent.conversation_manager import SummarizingConversationManager
from strands.handlers.callback_handler import null_callback_handler
from strands.models import BedrockModel
from strands.session.file_session_manager import FileSessionManager

from tokuye.prompts.prompt_loader import load_prompt, load_prompt_if_exists
from tokuye.tools.strands_tools.epic_tools.worker_tools import make_epic_worker_tools
from tokuye.utils.config import settings
from tokuye.utils.token_tracker import token_tracker

logger = logging.getLogger(__name__)


def _supports_prompt_cache(model_identifier: str) -> bool:
    return model_identifier in ("sonnet-4-6", "haiku-4-5", "opus-4-6", "nova-pro")


def _supports_tool_cache(model_identifier: str) -> bool:
    return model_identifier in ("sonnet-4-6", "haiku-4-5", "opus-4-6")


class EpicWorkerAgent:
    """Single-task agent for Epic Mode.

    One instance = one task session.
    Create a new instance for each task (or reuse for the same task to continue
    the session).

    Invoked as a Strands tool (run_epic_worker); no TUI callbacks needed.
    Returns a YAML string as the task result.

    Args:
        epic_id: Epic identifier (e.g. 'auth-cognito-migration').
        task_id: Task identifier within the epic (e.g. 'T001').
        repo_root: Absolute path to the target repository.  All tools are
            sandboxed to this directory — the Worker cannot touch anything
            outside it.
    """

    def __init__(
        self,
        epic_id: str,
        task_id: str,
        repo_root: Path,
    ) -> None:
        self.epic_id = epic_id
        self.task_id = task_id
        self.repo_root = repo_root.resolve()

        # System prompt (language-aware)
        if settings.language == "ja":
            self.system_prompt = load_prompt("system_prompt_epic_worker.md")
        else:
            self.system_prompt = load_prompt("system_prompt_epic_worker_en.md")

        # Summary prompt for conversation manager
        if settings.language == "ja":
            self.summary_prompt = load_prompt_if_exists("summary_prompt.md")
        else:
            self.summary_prompt = load_prompt_if_exists("summary_prompt_en.md")

        # Model — use the primary execution model
        _exec_cache = _supports_prompt_cache(settings.model_identifier)
        _exec_tool_cache = _supports_tool_cache(settings.model_identifier)
        self.model = BedrockModel(
            **({"cache_prompt": "default"} if _exec_cache else {}),
            **({"cache_tools": "default"} if _exec_tool_cache else {}),
            model_id=settings.bedrock_model_id,
            temperature=settings.model_temperature,
        )

        # Session: scoped to epic_id + task_id so each task has isolated history
        session_dir = settings.strands_session_dir
        if not session_dir:
            session_dir = os.path.join(
                settings.project_root, ".tokuye", "sessions"
            )
        os.makedirs(session_dir, exist_ok=True)
        session_id = f"epic-{epic_id}-{task_id}"
        self.session_manager = FileSessionManager(
            session_id=session_id, storage_dir=session_dir
        )

        # Build sandboxed tool set — all operations restricted to repo_root
        worker_tools = make_epic_worker_tools(self.repo_root)
        logger.info(
            "EpicWorkerAgent: sandboxed to %s (%d tools)",
            self.repo_root,
            len(worker_tools),
        )

        # Build agent (no MCP for worker — keeps it lightweight)
        self.agent = Agent(
            model=self.model,
            tools=worker_tools,
            system_prompt=self.system_prompt,
            session_manager=self.session_manager,
            conversation_manager=SummarizingConversationManager(
                summarization_system_prompt=self.summary_prompt
            ),
            callback_handler=null_callback_handler,
        )

    def __call__(self, instruction: str) -> str:
        """Run the worker with *instruction* and return the raw response text.

        Args:
            instruction: Full task instruction from EpicManagerAgent.

        Returns:
            Raw response string (expected to be YAML by the system prompt).
        """
        result = self.agent(instruction)
        # Merge Worker token usage into the shared token_tracker so that
        # EpicManagerAgent's TUI display reflects the full cost of the turn.
        self._merge_token_usage(result)
        # Extract text content from AgentResult
        if hasattr(result, "message") and result.message:
            content = result.message.get("content", [])
            if isinstance(content, list):
                texts = [
                    c.get("text", "") for c in content if isinstance(c, dict)
                ]
                return "\n".join(t for t in texts if t)
            if isinstance(content, str):
                return content
        return str(result)

    def _merge_token_usage(self, result) -> None:
        """Merge EpicWorkerAgent token usage into the global token_tracker.

        Called after each ``self.agent(instruction)`` invocation so that the
        Worker's token consumption is visible in the TUI cost display alongside
        the Manager's own usage.

        Uses ``latest_agent_invocation.usage`` which accumulates all event-loop
        cycles within a single ``__call__``.  Falls back silently on any error
        so that a Strands API change never breaks the Worker's core behaviour.
        """
        try:
            from strands.agent import AgentResult
            if not isinstance(result, AgentResult):
                return
            latest = result.metrics.latest_agent_invocation
            if latest is None:
                return
            token_tracker.add_usage(
                latest.usage,
                model_identifier=settings.model_identifier,
            )
            logger.debug(
                "EpicWorkerAgent[%s/%s]: merged token usage into tracker",
                self.epic_id,
                self.task_id,
            )
        except Exception as e:
            logger.debug("EpicWorkerAgent token usage merge failed: %s", e)
