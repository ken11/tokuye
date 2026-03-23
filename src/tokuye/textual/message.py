from tokuye.textual.widgets import ChatMessageWidget


class ChatMessage:

    def __init__(self, content: str, is_user: bool = True, is_system: bool = False):
        self.content = content
        self.is_user = is_user
        self.is_system = is_system

    def to_widget(self) -> ChatMessageWidget:
        return ChatMessageWidget(
            content=self.content,
            is_user=self.is_user,
            is_system=self.is_system,
        )
