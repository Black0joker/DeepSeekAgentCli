# Re-export from app.command_defs for backward compatibility.
# The canonical command definitions are in app/command_defs.py.
from app.command_defs import Command, COMMANDS

__all__ = ["Command", "COMMANDS"]
