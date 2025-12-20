from tokuye.utils.token_tracker import token_tracker

from textual import on
from textual.containers import Vertical
from textual.events import Key
from textual.widgets import RichLog, TextArea


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
