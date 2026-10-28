#!/usr/bin/env python3
"""Render the starter with tokens from the installed diagram-design style guide."""

import argparse
import re
from pathlib import Path


def render(style_guide, template, theme, offline):
    roles = style_guide.split("### Semantic roles", 1)[1].split("### Contrast", 1)[0]
    colors = {}
    for line in roles.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 4 or not cells[0].startswith("`"):
            continue
        name = cells[0].strip("`")
        value = cells[2 if theme == "light" else 3].split(" (")[0].strip("`")
        if not re.fullmatch(r"#[0-9a-fA-F]{3,8}|rgba?\([\d., %]+\)", value):
            raise ValueError("unsupported color token: " + name)
        colors[name] = value
    required = {"paper", "paper-2", "ink", "muted", "accent", "accent-tint"}
    if not required <= colors.keys():
        raise ValueError("missing required semantic colors")
    typography = style_guide.split("## Typography", 1)[1].split("### Font stack", 1)[0]
    families = {}
    for role, variable, fallback in [("title", "serif", "serif"),
                                     ("node-name", "sans", "system-ui, sans-serif"),
                                     ("sublabel", "mono", "ui-monospace, monospace")]:
        match = re.search(r"\| `" + role + r"` \| ([^|]+)\|", typography)
        if not match:
            raise ValueError("missing typography role: " + role)
        family = re.sub(r"\s*\([^)]*\)", "", match[1]).strip().strip("` *")
        if not re.fullmatch(r"[\w -]+", family):
            raise ValueError("unsupported font family: " + family)
        families[variable] = "'" + family + "', " + fallback
    font_link = ""
    if not offline and "Font source: `system`" not in style_guide:
        match = re.search(r'<link\s+href="https://fonts.googleapis.com/[^"<>]+"\s+rel="stylesheet"\s*/?>', style_guide)
        if not match:
            raise ValueError("web font source selected but font link is missing")
        font_link = match[0]
    css = ["--" + name + ": " + value + ";" for name, value in colors.items()]
    css += ["--font-" + name + ": " + value + ";" for name, value in families.items()]
    return template.replace("{{THEME}}", "\n    ".join(css)).replace("{{FONT_LINK}}", font_link)


def main():
    skill = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--theme", choices=["light", "dark"], default="light")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--style-guide", type=Path,
                        default=skill.parent / "diagram-design/references/style-guide.md")
    args = parser.parse_args()
    try:
        result = render(args.style_guide.read_text(),
                        (skill / "assets/template.html").read_text(), args.theme, args.offline)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as destination:
            destination.write(result)
    except (OSError, ValueError, IndexError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
