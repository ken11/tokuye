import logging
import os
import signal
import sys
import uuid
from pathlib import Path
from typing import Callable, List, Optional

from strands.types.exceptions import (ContextWindowOverflowException,
                                      MaxTokensReachedException,
                                      ModelThrottledException)
from tokuye.agent.strands_agent import MaxStepsException, StrandsAgent
from tokuye.tui.message import ChatMessage
from tokuye.tui.utils import (StdoutRedirector, TextualLogHandler,
                               get_log_level_from_string)
from tokuye.tui.widgets import MessageInput, UnifiedSidePanelDisplay
from tokuye.utils.config import settings
from tokuye.utils.token_tracker import token_tracker

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Button, Footer, Header, Label, TextArea

logger = logging.getLogger(__name__)


class ChatInterface(App):

    CSS_PATH = Path(__file__).parent / "chat_interface.css"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("enter", "noop", "New line", show=True, id="newline"),
        Binding("ctrl+d", "no", "Send", show=True, priority=True, id="send"),
    ]

    def __init__(
        self,
        project_root: str,
        system_message: Optional[str] = None,
        title: str = "AI Dev Agent",
        exit_callback: Optional[Callable[[], None]] = None,
        log_level: str = "error",
        max_steps: int = 100,
    ):
        super().__init__()
        self.initial_max_steps = max_steps
        self.current_max_steps = self.initial_max_steps
        self.thread_id = str(uuid.uuid4())
        self.agent = StrandsAgent(
            thread_id=self.thread_id,
            max_steps=self.current_max_steps,
            add_ai_message=lambda msg: self.call_later(self.add_ai_message, msg),
            add_system_message=lambda msg: self.call_later(
                self.add_system_message, msg
            ),
            set_thinking=lambda flg: self.call_later(self.set_thinking, flg),
            update_token_usage=lambda txt: self.call_later(
                self.update_token_usage, txt
            ),
        )
        self.system_message = system_message
        self.title = title
        self.thinking = False
        self.messages: List[ChatMessage] = []
        self.exit_callback = exit_callback
        self.stdout_redirector = None
        self.log_level = get_log_level_from_string(log_level)

        self.project_root = project_root

        self.waiting_for_resume: bool = False
        self.waiting_for_recursion: bool = False

    def compose(self) -> ComposeResult:
        yield Header(name=self.title, show_clock=True)

        with Horizontal(id="main-container"):
            with Container(id="chat-panel"):
                with Container(id="chat-container"):
                    yield VerticalScroll(id="chat-log")
                    yield Label("thinking...", id="thinking-label", classes="hidden")

                    with Horizontal(id="input-container"):
                        yield MessageInput(id="message-input")
                        with Vertical(id="button-container"):
                            yield Button("Send", id="send-button", variant="primary")
                            yield Button("Reset", id="reset-button", variant="error")
                            yield Button(
                                "Recall Issue",
                                id="recall-issue-button",
                                variant="success",
                            )

            with Container(id="side-panel"):
                yield UnifiedSidePanelDisplay(id="unified-panel")

        yield Footer()

    def on_mount(self) -> None:
        self.theme = settings.theme
        chat_log = self.query_one("#chat-log", VerticalScroll)
        unified_panel = self.query_one("#unified-panel", UnifiedSidePanelDisplay)

        root_logger = logging.getLogger()
        old_handlers = root_logger.handlers.copy()
        for handler in old_handlers:
            root_logger.removeHandler(handler)
        handler = TextualLogHandler(unified_panel.system_log, self.log_level)
        root_logger.addHandler(handler)
        root_logger.setLevel(self.log_level)

        self.stdout_redirector = StdoutRedirector(unified_panel.system_log)
        sys.stdout = self.stdout_redirector

        for message in self.messages:
            chat_log.mount(message.to_widget())

        self.query_one("#message-input", TextArea).focus()

        signal.signal(signal.SIGINT, self._handle_sigint)

        unified_panel.system_log.write(
            f"[bold magenta]✨ Logs and debug information will be displayed here (Level: {logging.getLevelName(self.log_level)}) ✨[/]"
        )
        unified_panel.system_log.write(
            f"[bold blue]🧵 Conversation Thread ID: {self.thread_id}[/]"
        )

        self.update_token_usage("")

    def on_unmount(self) -> None:
        if self.stdout_redirector:
            sys.stdout = self.stdout_redirector.old_stdout

    def _handle_sigint(self, sig, frame):
        self.exit()

    def action_quit(self) -> None:
        self.exit()

    def on_exit(self):
        print("\nExiting application...")

    async def on_unmount(self) -> None:
        # Clean up MCP connections when the app is torn down
        if hasattr(self, 'agent') and self.agent:
            await self.agent.cleanup()
        sys.exit(0)

    def exit(self) -> None:
        if self.stdout_redirector:
            sys.stdout = self.stdout_redirector.old_stdout
        self.on_exit()
        super().exit()

    def action_send_message(self) -> None:
        input_widget = self.query_one("#message-input", TextArea)
        message = input_widget.text.strip()

        if not message:
            return

        input_widget.load_text("")

        self.add_user_message(message)
        self.on_message(message)

    @work
    async def action_reset_conversation(self) -> None:
        chat_log = self.query_one("#chat-log", VerticalScroll)
        for child in list(chat_log.children):
            child.remove()

        system_message = None
        for msg in self.messages:
            if msg.is_system:
                system_message = msg
                break

        self.messages.clear()

        # Clean up old agent's MCP connections before creating new one
        await self.agent.cleanup()

        if system_message:
            self.messages.append(system_message)
            chat_log.mount(system_message.to_widget())

        self.thread_id = str(uuid.uuid4())
        self.agent = StrandsAgent(
            thread_id=self.thread_id,
            max_steps=self.current_max_steps,
            add_ai_message=lambda msg: self.call_later(self.add_ai_message, msg),
            add_system_message=lambda msg: self.call_later(
                self.add_system_message, msg
            ),
            set_thinking=lambda flg: self.call_later(self.set_thinking, flg),
            update_token_usage=lambda txt: self.call_later(
                self.update_token_usage, txt
            ),
        )

        self.waiting_for_resume = False
        t = self.query_one("#message-input", TextArea)
        t.disabled = False
        t.focus()

        unified_panel = self.query_one("#unified-panel", UnifiedSidePanelDisplay)
        unified_panel.system_log.write(
            "[bold green]🔄 Conversation history has been reset[/]"
        )
        unified_panel.system_log.write(
            f"[bold blue]🧵 New conversation thread ID: {self.thread_id}[/]"
        )

    def get_thread_id(self) -> str:
        return self.thread_id

    @work
    async def on_message(self, message: str):

        if self.waiting_for_resume:
            if message.strip().lower().startswith("y"):
                self.waiting_for_resume = False
                message = None
            else:
                self.add_system_message("Process interrupted")
                self.waiting_for_resume = False
                return

        if self.waiting_for_recursion:
            if message.strip().lower().startswith("y"):
                self.waiting_for_recursion = False
                message = None
                self.current_max_steps += self.initial_max_steps
                self.agent.max_steps += self.current_max_steps
            else:
                self.add_system_message("Process interrupted")
                self.waiting_for_recursion = False
                return

        if token_tracker:
            token_tracker.reset_turn()

        if message is not None and message.strip().startswith("# Issue"):
            tokuye_dir = os.path.join(self.project_root, ".tokuye")
            issue_file_path = os.path.join(tokuye_dir, "current_issue.md")
            with open(issue_file_path, "w", encoding="utf-8") as f:
                f.write(message)
            self.add_system_message(f"Issue saved: {issue_file_path}")

        try:
            _ = await self.agent(message)
        except ContextWindowOverflowException as e:
            logger.info(e)
            self.add_system_message(
                "Input is too long. Please shorten the input. Press the Reset button to try again."
            )
            self.disable_input()
        except ModelThrottledException as e:
            logger.info(e)
            self.add_system_message(
                f"An error occurred in Bedrock ({e}). Do you want to retry? (y/n)"
            )
            self.waiting_for_resume = True
        except MaxTokensReachedException as e:
            logger.info(e)
            self.add_system_message(
                "The maximum output length of the model has been exceeded. Press the Reset button to try again."
            )
            self.disable_input()
        except MaxStepsException as e:
            logger.info(e)
            self.add_system_message(
                "Maximum number of steps reached. Do you want to continue? (y/n)"
            )
            self.waiting_for_recursion = True
        except Exception as e:
            logger.error(e)
            self.add_system_message(
                f"An unexpected error occurred. ({e}) Press the Reset button to try again."
            )
            self.disable_input()

    @on(Button.Pressed, "#send-button")
    def handle_send_button_pressed(self) -> None:
        self.action_send_message()

    @on(Button.Pressed, "#reset-button")
    def handle_reset_button_pressed(self) -> None:
        self.action_reset_conversation()

    @on(Button.Pressed, "#recall-issue-button")
    def handle_recall_issue_button_pressed(self) -> None:
        input_widget = self.query_one("#message-input", TextArea)

        # Only allow recall if input is empty
        if input_widget.text.strip():
            return

        issue_file_path = os.path.join(self.project_root, ".tokuye", "current_issue.md")

        if not os.path.exists(issue_file_path):
            self.add_system_message(
                "No saved issue found. Please create an issue first by starting your message with '# Issue'."
            )
            return

        with open(issue_file_path, "r", encoding="utf-8") as f:
            issue_content = f.read()

        input_widget.load_text(issue_content)

    def add_user_message(self, content: str) -> None:
        message = ChatMessage(content, is_user=True)
        self.messages.append(message)

        chat_log = self.query_one("#chat-log", VerticalScroll)
        chat_log.mount(message.to_widget())

        chat_log.scroll_end(animate=False)

    def add_ai_message(self, content: str) -> None:
        message = ChatMessage(content, is_user=False)
        self.messages.append(message)

        chat_log = self.query_one("#chat-log", VerticalScroll)
        chat_log.mount(message.to_widget())

        chat_log.scroll_end(animate=False)

    def add_system_message(self, content: str) -> None:
        message = ChatMessage(content, is_user=False, is_system=True)
        self.messages.append(message)

        chat_log = self.query_one("#chat-log", VerticalScroll)
        chat_log.mount(message.to_widget())

        chat_log.scroll_end(animate=False)

    def set_thinking(self, thinking: bool) -> None:
        self.thinking = thinking
        try:
            thinking_label = self.query_one("#thinking-label", Label)
            if thinking:
                thinking_label.remove_class("hidden")
                t = self.query_one("#message-input", TextArea)
                t.disabled = True
            else:
                thinking_label.add_class("hidden")
                t = self.query_one("#message-input", TextArea)
                t.disabled = False
                t.focus()
        except NoMatches:
            pass

    def update_token_usage(self, usage_text: str) -> None:
        try:
            unified_panel = self.query_one("#unified-panel", UnifiedSidePanelDisplay)
            unified_panel.update_usage(usage_text)
        except NoMatches:
            pass

    def disable_input(self) -> None:
        t = self.query_one("#message-input", TextArea)
        t.disabled = True
