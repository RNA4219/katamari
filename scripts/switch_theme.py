
#!/usr/bin/env python3
import pathlib
import shutil
import sys

root = pathlib.Path(__file__).resolve().parents[1]
themes = root / "themes"
public = root / "public"
name = sys.argv[1] if len(sys.argv) > 1 else ""

if not name:
    print("Usage: switch_theme.py <theme-name>")
    print("Available:")
    for p in sorted(themes.glob("*.theme.json")):
        print(" -", p.stem)
    sys.exit(1)

src = themes / f"{name}.theme.json"
dst = public / "theme.json"
if not src.exists():
    print("Theme not found:", src.name)
    sys.exit(2)

shutil.copyfile(src, dst)
print("Switched theme ->", src.name)
