"""The deck: one self-contained HTML page carrying a list of tabs.

`render_report` assembles tab buttons + content panes into the bundled page
template. Applications build their tab contents with `logdeck.tables` and
pass them in.

Tab spec: {"id": str, "title": str, "content": str, "active": bool}
`title`/`content` are inserted raw (authored by the calling application).
"""

from pathlib import Path
from typing import TypedDict

_TEMPLATE = Path(__file__).parent / "templates" / "report.html"
_SCRIPT = Path(__file__).parent / "templates" / "report.js"


class Tab(TypedDict, total=False):
    id: str
    title: str
    content: str
    active: bool


def build_tabs_html(tabs: list[Tab]) -> str:
    """Wrap tab specs in the deck markup"""
    lines: list[str] = [
        "",
        '        <div class="top-tabs">',
        '            <div class="tab-buttons">',
    ]
    for t in tabs:
        cls = "tab-button active" if t.get("active") else "tab-button"
        btn = (
            f'                <button class="{cls}" '
            f"onclick=\"openTab(event, '{t['id']}')\">{t['title']}</button>"
        )
        lines.append(btn)
    lines.append("            </div>")
    lines.append("")
    last = len(tabs) - 1
    for i, t in enumerate(tabs):
        cls = "tab-content active" if t.get("active") else "tab-content"
        lines.append(f"""            <div id="{t['id']}" class="{cls}">""")
        lines.append(f"""                {t["content"]}""")
        lines.append("            </div>")
        if i != last:
            lines.append("")
    lines.append("        </div>")
    lines.append("        ")
    return "\n".join(lines)


def render_report(
    tabs: list[Tab],
    now: str,
    title: str,
    heading: str,
    footer: str,
) -> str:
    """Render the complete standalone HTML document as a string."""
    template = _TEMPLATE.read_text(encoding="utf-8")
    script = _SCRIPT.read_text(encoding="utf-8")
    return template.format(
        sections=build_tabs_html(tabs), now=now, script=script,
        title=title, heading=heading, footer=footer,
    )
