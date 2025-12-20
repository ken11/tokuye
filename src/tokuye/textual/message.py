from rich.box import ROUNDED
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from tokuye.utils.config import settings


class ChatMessage:

    def __init__(self, content: str, is_user: bool = True, is_system: bool = False):
        self.content = content
        self.is_user = is_user
        self.is_system = is_system

    def to_rich(self) -> Panel:
        if self.is_system:
            title = "System"
            border_style = "violet"
        elif self.is_user:
            title = "You"
            border_style = "bright_white"
        else:
            title = "Assistant"
            if settings.name:
                title = settings.name
            border_style = "sky_blue2"

        try:
            md = Markdown(self.content)
            return Panel(
                md,
                title=title,
                title_align="left",
                border_style=border_style,
                box=ROUNDED,
                padding=(1, 2),
            )
        except Exception:
            return Panel(
                Text(self.content),
                title=title,
                title_align="left",
                border_style=border_style,
                box=ROUNDED,
                padding=(1, 2),
            )
