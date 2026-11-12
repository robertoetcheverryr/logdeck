"""Generic dict->HTML rendering primitives shared by log analyzer decks.
"""

import html as html_escape
import re
from collections.abc import Callable
from typing import Any


def escape(text: Any) -> str:
    if text is None:
        return ""
    return html_escape.escape(str(text))


def _safe_html(
    text: Any,
    column_name: str = "",
    highlight_rules: dict[str, Callable[[str], bool]] | None = None,
) -> str:
    """
    Escape text but allow safe HTML tags.
    Applies highlighting based on external per-column rules.
    """
    if text is None:
        return ""
    text_str = str(text).strip()
    escaped = html_escape.escape(text_str)

    # Allow safe tags (used by VPD -Integrated)
    allowed_tags = ["strong", "b", "em", "i", "small", "span"]
    for tag in allowed_tags:
        escaped = re.sub(f"&lt;{tag}(.*?)&gt;", f"<{tag}\\1>", escaped, flags=re.IGNORECASE)
        escaped = re.sub(f"&lt;/{tag}&gt;", f"</{tag}>", escaped, flags=re.IGNORECASE)

    # Apply highlighting if rules provided
    if highlight_rules and column_name:
        rule = highlight_rules.get(column_name.lower())
        if rule and rule(text_str.lower()):
            return f'<strong style="color:#f50505;">{escaped}</strong>'

    return escaped


def dicts_to_html_table(
    rows: list[dict[str, str]],
    columns: list[str] | None = None,
    highlight_rules: dict[str, Callable[[str], bool]] | None = None,
) -> str:
    """Render list of dicts as HTML table with configurable highlighting."""
    if not rows:
        return "<p><em>No data</em></p>"

    # Get all keys that actually exist in the data
    all_keys: set[str] = set()
    for row in rows:
        all_keys.update(row.keys())

    if columns is None:
        # Default: all keys from the first row (preserving original order)
        columns = list(rows[0].keys())
    else:
        # Intersection: only keep columns that were requested AND exist in the data
        columns = [col for col in columns if col in all_keys]

    if not columns:
        return "<p><em>No matching columns</em></p>"
    header = "".join(f"<th>{escape(col)}</th>" for col in columns)
    body_rows = []

    for row in rows:
        cells = []
        for col in columns:
            val = row.get(col)
            # Some columns might not exist in all versions
            if val is None:
                continue
            cells.append(
                f"<td>{_safe_html(val, column_name=col, highlight_rules=highlight_rules)}</td>"
            )
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    return f"""
<table class="data-table">
  <thead><tr>{header}</tr></thead>
  <tbody>
    {"".join(body_rows)}
  </tbody>
</table>
"""


def make_section(
    title: str, content_html: str, count: int | None = None, open: bool = False
) -> str:
    count_str = f" ({count})" if count is not None else ""
    open_attr = " open" if open else ""
    return f"""
<details{open_attr}>
  <summary>{escape(title)}{count_str}</summary>
  <div class="section-content">
    {content_html}
  </div>
</details>
"""
