"""Run in Blender (Scripting > Open > Run Script). Builds compact LEFT and RIGHT shells into stl/."""
import re
from pathlib import Path
here = Path(__file__).resolve().parent
src = (here / "earbud_shell_compact.py").read_text()
for side in (1, -1):
    s = re.sub(r"^SIDE = -?1", f"SIDE = {side}", src, flags=re.M)
    exec(compile(s, "earbud_shell_compact.py", "exec"), {"__file__": str(here / "earbud_shell_compact.py"), "__name__": "__main__"})
