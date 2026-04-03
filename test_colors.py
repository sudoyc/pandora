from rich.console import Console
from rich.text import Text

c = Console()
t = Text()
t.append("[NON-H] ", style="bold blue reverse")
t.append("[DOUJINSHI] ", style="bold red reverse")
t.append("[MISC] ", style="bold grey74 reverse")
c.print(t)
