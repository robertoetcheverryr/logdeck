"""Smoke tests for the deck and table primitives."""

from logdeck import dicts_to_html_table, make_section, render_report


def test_render_report_contains_all_tabs():
    tabs = [
        {"id": "tab-a", "title": "Alpha", "content": "<p>A</p>", "active": True},
        {"id": "tab-b", "title": "Beta", "content": "<p>B</p>"},
    ]
    page = render_report(
        tabs, now="2026-11-12 00:00:00", title="T", heading="H", footer="F"
    )
    assert "<title>T</title>" in page
    assert "<h1>H</h1>" in page
    assert "F • 2026-11-12 00:00:00" in page
    assert 'id="tab-a" class="tab-content active"' in page
    assert 'id="tab-b" class="tab-content"' in page
    assert "function openTab" in page  # viewer JS inlined
    # exactly one active tab-button
    assert page.count('class="tab-button active"') == 1
    assert page.count('class="tab-button"') == 1


def test_highlight_rules():
    html = dicts_to_html_table(
        [{"status": "degraded"}, {"status": "online"}],
        highlight_rules={"status": lambda s: s == "degraded"},
    )
    assert 'color:#f50505;">degraded' in html
    assert "color:#f50505;\">online" not in html


def test_escape_and_allowlist():
    html = dicts_to_html_table([{"x": "<script>alert(1)</script> <b>ok</b>"}])
    assert "<script>" not in html
    assert "<b>ok</b>" in html
    assert "&lt;script&gt;" in html


def test_make_section():
    s = make_section("Title <i>t</i>", "<p>c</p>", count=3, open=True)
    assert s.startswith("\n<details open>")
    assert "Title &lt;i&gt;t&lt;/i&gt; (3)" in s
