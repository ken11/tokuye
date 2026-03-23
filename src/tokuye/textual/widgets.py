from tokuye.utils.token_tracker import token_tracker

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.events import Key
from textual.widget import Widget
from textual.widgets import Button, Markdown, RichLog, TextArea


class MessageInput(TextArea):

    @on(Key)
    def on_key(self, event: Key) -> None:
        text_area = self.app.query_one("#message-input", TextArea)
        if text_area.has_focus:
            if event.key == "ctrl+d":
                event.prevent_default()
                event.stop()
                self.app.action_send_message()
            elif event.key == "enter":
                event.prevent_default()
                event.stop()
                self.insert(self.document.newline, self.cursor_location)


class UnifiedSidePanelDisplay(Vertical):

    def __init__(self, id: str):
        super().__init__(id=id)
        self.cost_display = RichLog(id="cost-display", highlight=True, markup=True)

        self.system_log = RichLog(
            id="system-log", highlight=True, markup=True, wrap=True
        )

        self.token_log = RichLog(id="token-log", highlight=True, markup=True, wrap=True)

    def compose(self) -> None:
        yield self.cost_display
        yield self.system_log
        yield self.token_log

    def update_usage(self, usage_text: str) -> None:
        total_cost_text = token_tracker.format_total_cost_jpy()

        self.cost_display.clear()
        self.cost_display.write(total_cost_text)

        self.token_log.clear()
        self.token_log.write("[bold yellow]Token Usage Log[/]")
        self.token_log.write(usage_text)
        self.token_log.write(token_tracker.format_usage_history())


class ChatMessageWidget(Widget):
    """1件のチャットメッセージを表すウィジェット。"""

    def __init__(self, content: str, is_user: bool = True, is_system: bool = False):
        super().__init__()
        self.content = content
        self.is_user = is_user
        self.is_system = is_system

    def compose(self) -> ComposeResult:
        yield Markdown(self.content)
        yield Button("⎘", classes="copy-btn")

    def on_mount(self) -> None:
        if self.is_system:
            self.border_title = "System"
            self.styles.border = ("round", "violet")
        elif self.is_user:
            self.border_title = "You"
            self.styles.border = ("round", "bright_white")
        else:
            from tokuye.utils.config import settings
            self.border_title = settings.name if settings.name else "Assistant"
            self.styles.border = ("round", "sky_blue2")

    @on(Button.Pressed, ".copy-btn")
    def handle_copy(self, event: Button.Pressed) -> None:
        event.stop()
        self.app.copy_to_clipboard(self.content)
        self.notify("Copied!", timeout=1.5)
