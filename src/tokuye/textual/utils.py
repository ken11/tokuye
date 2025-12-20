import io
import logging
import sys

from textual.widgets import RichLog


class StdoutRedirector(io.StringIO):

    def __init__(self, rich_log: RichLog):
        super().__init__()
        self.rich_log = rich_log
        self.old_stdout = sys.stdout

    def write(self, text: str) -> int:
        self.old_stdout.write(text)

        if text.strip():
            self.rich_log.write(f"[dim cyan]>>> {text.rstrip()}[/]")
            self.rich_log.scroll_end(animate=False)

        return len(text)

    def flush(self) -> None:
        self.old_stdout.flush()


class TextualLogHandler(logging.Handler):

    def __init__(self, rich_log: RichLog, log_level: int = logging.ERROR):
        super().__init__(level=log_level)
        self.rich_log = rich_log
        self.log_level = log_level
        self.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith("tokuye"):
            msg = self.format(record)

            if record.levelno < self.log_level:
                return
            if record.levelno >= logging.ERROR:
                styled_msg = f"[bold red]{msg}[/]"
            elif record.levelno >= logging.WARNING:
                styled_msg = f"[yellow]{msg}[/]"
            elif record.levelno >= logging.INFO:
                styled_msg = f"[green]{msg}[/]"
            else:
                styled_msg = f"[dim]{msg}[/]"

            self.rich_log.write(styled_msg)
            self.rich_log.scroll_end(animate=False)


def get_log_level_from_string(log_level_str: str) -> int:
    log_levels = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }

    return log_levels.get(log_level_str.lower(), logging.ERROR)
