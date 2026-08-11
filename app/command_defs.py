from dataclasses import dataclass

@dataclass
class Command:
    name: str
    description: str
    requires_arguments: bool = False

COMMANDS = [
    Command("/clear", "Clear the conversation"),
    Command("/help", "Show available commands"),
    Command("/new", "Start a new conversation"),
    Command("/settings", "Display current settings"),
    Command("/quit", "Exit the application"),
    Command("/mode", "Set operation mode (auto/permission)"),
    Command("/set_workspace", "Set the workspace directory", requires_arguments=True),
    Command("/change_chat", "Switch to a chat session by number (use /chats first)", requires_arguments=True),
    Command("/chats", "List all chat sessions with their IDs and titles"),
]
