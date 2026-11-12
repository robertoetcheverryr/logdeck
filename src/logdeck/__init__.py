"""logdeck — log analyzer frontend: shared HTML report deck.

Applications supply tab contents built with the
table/section primitives; logdeck owns the page shell,
tab mechanics and viewer JavaScript.
"""

from logdeck.report import Tab, build_tabs_html, render_report
from logdeck.tables import dicts_to_html_table, escape, make_section

__version__ = "0.1.0"

__all__ = [
    "Tab",
    "build_tabs_html",
    "dicts_to_html_table",
    "escape",
    "make_section",
    "render_report",
]
