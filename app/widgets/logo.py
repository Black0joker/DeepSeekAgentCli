'''Logo widget for the terminal UI.'''

from textual.widgets import Static
from rich.text import Text
from app.theme import LOGO_GRADIENT


class Logo(Static):
    '''A widget that displays a terminal logo with a gradient from blue to purple.
    
    The logo is inspired by the Gemini CLI logo and uses Unicode block characters
    to create a modern, minimal, premium visual identity.
    '''
    
    def render(self) -> Text:
        '''Render the logo with a gradient from #6EA8FE to #C87AFF.'''
        # Asymmetrical arrow/ribbon design built with block characters
        # Width ranges from 3 to 8 characters, height is 7 lines
        lines = [
            f"[{LOGO_GRADIENT[0]}]   ▄▄▄[/]",
            f"[{LOGO_GRADIENT[1]}]  ▄███▄[/]",
            f"[{LOGO_GRADIENT[2]}] ▄█████▄[/]",
            f"[{LOGO_GRADIENT[3]}]███████[/]",
            f"[{LOGO_GRADIENT[4]}] ██████▀[/]",
            f"[{LOGO_GRADIENT[5]}]  ████▀[/]",
            f"[{LOGO_GRADIENT[6]}]   ██▀[/]"
        ]
        return Text.from_markup("\n".join(lines))
