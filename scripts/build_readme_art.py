"""Rebuild the README art in docs/assets: the banners and the architecture diagram, light and dark.

Colors are Epiphan Brand MCP tokens (get_style_tokens, colors). The logos are the official Brand MCP assets,
saved byte-identical in docs/assets/epiphan-logo*.svg; this script only nests them, never edits them.

    python3 scripts/build_readme_art.py
"""

from __future__ import annotations

import re
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "docs" / "assets"
FONT = "Söhne,-apple-system,Segoe UI,Helvetica,Arial,sans-serif"
MONO = "Söhne Mono,ui-monospace,SFMono-Regular,Menlo,monospace"

LIGHT = {
    "bg": "#f1f2f0",
    "fg": "#111111",
    "muted": "#5a5a5a",
    "box": "#ffffff",
    "line": "#e4e5ea",
    "arrow": "#4a4aaf",
    "pearl": "#0c3d34",
    "diagram_line": "#c9ccd4",
    "logo": "epiphan-logo-horizontal.svg",
}
DARK = {
    "bg": "#0d231f",
    "fg": "#ffffff",
    "muted": "#e4e5ea",
    "box": "#0c3d34",
    "line": "#316472",
    "arrow": "#d7daf9",
    "pearl": "#6651fc",
    "diagram_line": "#316472",
    "diagram_muted": "#cfd3dc",
    "logo": "epiphan-logo-horizontal-light.svg",
}


def logo_drawing(name: str) -> str:
    """The logo's drawing, without the XML declaration or its own <svg> wrapper."""
    svg = re.sub(r"<\?xml[^>]*\?>", "", (ASSETS / name).read_text(encoding="utf-8"))
    return re.sub(r"^.*?<svg[^>]*>|</svg>\s*$", "", svg.strip(), flags=re.S)


def banner(t: dict[str, str]) -> str:
    bg, fg, muted, box, line, arrow, pearl = (
        t[k] for k in ("bg", "fg", "muted", "box", "line", "arrow", "pearl")
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="880" height="200" viewBox="0 0 880 200" role="img" aria-label="Epiphan pearl-episodes: Pearl recordings, packaged as robot-learning episodes">
  <rect width="880" height="200" rx="16" fill="{bg}"/>
  <svg x="30" y="14" width="180" height="50" viewBox="0 0 358.2 99.5">{logo_drawing(t["logo"])}</svg>
  <text x="48" y="122" font-family="{FONT}" font-size="46" font-weight="600" fill="{fg}">pearl-episodes</text>
  <text x="50" y="160" font-family="{FONT}" font-size="19" fill="{muted}">Pearl recordings, packaged as robot-learning episodes</text>
  <g font-family="{MONO}" font-size="12" text-anchor="middle">
    <rect x="478" y="54" width="66" height="34" rx="6" fill="{box}" stroke="{line}"/><text x="511" y="75" fill="{fg}">EC20</text>
    <rect x="478" y="112" width="66" height="34" rx="6" fill="{box}" stroke="{line}"/><text x="511" y="133" fill="{fg}">EC20</text>
    <path d="M546 71 L578 90 M546 129 L578 110" stroke="{arrow}" stroke-width="2.5" fill="none"/>
    <rect x="580" y="68" width="84" height="64" rx="8" fill="{pearl}"/><text x="622" y="105" fill="#ffffff" font-family="{FONT}" font-size="15" font-weight="600">Pearl</text>
    <path d="M666 100 L700 100" stroke="{arrow}" stroke-width="2.5"/><path d="M694 94 L702 100 L694 106" stroke="{arrow}" stroke-width="2.5" fill="none"/>
    <rect x="708" y="56" width="132" height="24" rx="5" fill="{box}" stroke="{line}"/><text x="774" y="72" fill="{fg}">manifest.json</text>
    <rect x="708" y="88" width="132" height="24" rx="5" fill="{box}" stroke="{line}"/><text x="774" y="104" fill="{fg}">LeRobot</text>
    <rect x="708" y="120" width="132" height="24" rx="5" fill="{box}" stroke="{line}"/><text x="774" y="136" fill="{fg}">RLDS</text>
  </g>
</svg>
"""


def node(x: int, y: int, w: int, h: int, title: str, sub: str, t: dict[str, str]) -> str:
    title_y = h / 2 if not sub else h / 2 - 6
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{t["box"]}" stroke="{t["line"]}"/>',
        f'<text x="{x + w / 2}" y="{y + title_y}" text-anchor="middle" dominant-baseline="middle" '
        f'font-size="14" font-weight="600" fill="{t["fg"]}">{title}</text>',
    ]
    if sub:
        parts.append(
            f'<text x="{x + w / 2}" y="{y + h / 2 + 13}" text-anchor="middle" dominant-baseline="middle" '
            f'font-size="12" fill="{t["muted"]}">{sub}</text>'
        )
    return "\n  ".join(parts)


def arrow(x1: int, y1: int, x2: int, y2: int, t: dict[str, str], label: str = "") -> str:
    out = (
        f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{t["arrow"]}" stroke-width="2" fill="none" '
        f'marker-end="url(#head)"/>'
    )
    if label:
        out += (
            f'\n  <text x="{(x1 + x2) / 2}" y="{(y1 + y2) / 2 - 9}" text-anchor="middle" font-size="11" '
            f'fill="{t["muted"]}">{label}</text>'
        )
    return out


def diagram(theme: dict[str, str]) -> str:
    t = {**theme, "line": theme["diagram_line"], "muted": theme.get("diagram_muted", theme["muted"])}
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="880" height="300" viewBox="0 0 880 300" role="img" '
        'aria-label="Claude Code drives Epiphan Edge, which starts and stops a Pearl recording two EC20 cameras; '
        'pearl-episodes pulls the files over the REST API and packages them as episodes for a notebook beside DROID" '
        f'font-family="{FONT}">',
        '<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{t["arrow"]}"/></marker></defs>',
        f'<rect width="880" height="300" rx="16" fill="{t["bg"]}"/>',
        f'<text x="30" y="38" font-size="12" font-weight="600" fill="{t["muted"]}">OPERATE</text>',
        node(30, 56, 170, 60, "Claude Code", "write guard + redaction", t),
        arrow(200, 86, 248, 86, t),
        node(250, 56, 150, 60, "Epiphan Edge", "MCP", t),
        arrow(400, 86, 508, 86, t, "start / stop, asks first"),
        f'<rect x="510" y="40" width="340" height="92" rx="10" fill="none" stroke="{t["line"]}" '
        'stroke-dasharray="5 4"/>',
        f'<text x="680" y="34" text-anchor="middle" font-size="12" font-weight="600" fill="{t["muted"]}">STATION</text>',
        node(526, 56, 130, 60, "EC20 cameras", "", t),
        arrow(656, 86, 712, 86, t, "HDMI"),
        f'<rect x="714" y="56" width="120" height="60" rx="8" fill="{t["pearl"]}"/>',
        '<text x="774" y="87" text-anchor="middle" dominant-baseline="middle" font-size="15" font-weight="600" '
        'fill="#ffffff">Pearl</text>',
        f'<path d="M774 116 L774 176 L215 176 L215 202" stroke="{t["arrow"]}" stroke-width="2" fill="none" '
        'marker-end="url(#head)"/>',
        f'<text x="494" y="168" text-anchor="middle" font-size="11" fill="{t["muted"]}">REST API: list, download</text>',
        f'<text x="30" y="196" font-size="12" font-weight="600" fill="{t["muted"]}">DATA</text>',
        node(130, 204, 170, 60, "pearl-episodes", "pull, package", t),
        arrow(300, 234, 348, 234, t),
        node(350, 204, 250, 60, "episodes/", "manifest, hashes, LeRobot, RLDS", t),
        arrow(600, 234, 648, 234, t),
        node(650, 204, 200, 60, "Notebook", "beside a DROID episode", t),
        "</svg>",
    ]
    return "\n  ".join(parts) + "\n"


def main() -> None:
    for name, theme in (("light", LIGHT), ("dark", DARK)):
        (ASSETS / f"banner-{name}.svg").write_text(banner(theme), encoding="utf-8")
        (ASSETS / f"architecture-{name}.svg").write_text(diagram(theme), encoding="utf-8")
    print(f"wrote banners and architecture diagrams in {ASSETS}")


if __name__ == "__main__":
    main()
