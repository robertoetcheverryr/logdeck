function expandAll() {
    document.querySelectorAll('details').forEach(d => d.open = true);
}

function collapseAll() {
    document.querySelectorAll('details').forEach(d => d.open = false);
}

function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function copyVisibleAsHTML(btn) {
    // Only care about the tab that is currently visible on screen
    const activeTab = document.querySelector('.tab-content.active');

    if (!activeTab) {
        return;
    }

    // Only the open sections inside the active tab
    const openDetails = Array.from(activeTab.querySelectorAll('details[open]'));

    if (openDetails.length === 0) {
        if (btn) {
            const originalText = btn.textContent;
            btn.textContent = "Nothing expanded!";
            setTimeout(() => { btn.textContent = originalText; }, 1800);
        }
        return;
    }

    // Build self-contained HTML suitable for pasting into Salesforce / rich-text editors
    let htmlParts = [];

    htmlParts.push(`<h1 style="color:#0d6efd; font-size:1.5rem; margin-bottom:4px;">SVC / Storwize / FlashSystem SNAP Analysis</h1>`);

    // Embedded styles – most rich-text editors keep a limited <style> block
    htmlParts.push(`
<style>
    table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 0.92rem; }
    th, td { border: 1px solid #adb5bd; padding: 6px 9px; text-align: left; vertical-align: top; }
    th { background-color: #f1f3f5; font-weight: 600; }
    tr:nth-child(even) { background-color: #f8f9fa; }
    h2 { color: #0d6efd; font-size: 1.25rem; margin: 22px 0 8px 0; border-bottom: 2px solid #e9ecef; padding-bottom: 4px; }
    h3 { color: #495057; margin: 16px 0 6px; }
    strong[style*="color:#f50505"] { color: #dc3545 !important; font-weight: 700; }
    hr { border: none; border-top: 1px solid #dee2e6; margin: 18px 0; }
    details { margin-bottom: 10px; }
    summary { font-weight: 600; cursor: default; }
</style>
`);

    openDetails.forEach((details, index) => {
        const summaryEl = details.querySelector('summary');
        let title = summaryEl ? summaryEl.textContent.trim() : ("Section " + (index + 1));

        // Remove the ▶ marker that CSS injects into the summary text
        title = title.replace(/^▶\s*/, '').trim();

        const contentDiv = details.querySelector('.section-content');
        let contentHTML;

        if (contentDiv) {
            contentHTML = contentDiv.innerHTML;
        } else {
            // Fallback for any section that does not use the .section-content wrapper
            contentHTML = details.innerHTML.replace(/<summary[\s\S]*?<\/summary>/i, '');
        }

        const safeTitle = escapeHtml(title);
        htmlParts.push(`<h2>${safeTitle}</h2>`);
        htmlParts.push(contentHTML);

        if (index < openDetails.length - 1) {
            htmlParts.push('<hr>');
        }
    });

    const finalHTML = htmlParts.join('\n');
    const htmlBlob = new Blob([finalHTML], { type: 'text/html' });

    // Pitfall notes (modern browsers only):
    // - navigator.clipboard.write requires a secure context (HTTPS or localhost)
    // - Must be called from a user gesture (button click is fine)
    // - Some corporate policies / older embedded WebViews may still block ClipboardItem
    navigator.clipboard.write([
        new ClipboardItem({ 'text/html': htmlBlob })
    ]).then(() => {
        if (btn) {
            const originalText = btn.textContent;
            btn.textContent = "✓ Copied HTML!";
            setTimeout(() => { btn.textContent = originalText; }, 2200);
        }
    });
}

// Tab functionality
function openTab(evt, tabName) {
    const tabContents = document.getElementsByClassName("tab-content");
    for (let content of tabContents) {
        content.classList.remove("active");
    }
    const tabButtons = document.getElementsByClassName("tab-button");
    for (let btn of tabButtons) {
        btn.classList.remove("active");
    }
    document.getElementById(tabName).classList.add("active");
    evt.currentTarget.classList.add("active");
}

// Selected implementation columns, shared by both copy actions
function selectedImplIndices() {
    return Array.from(document.querySelectorAll('.impl-col:checked')).map(cb => parseInt(cb.value));
}

function implHeaderTsv(table, selectedIndices) {
    const headerCells = Array.from(table.querySelectorAll('thead th'));
    return selectedIndices.map(i => headerCells[i].textContent.trim()).join('\t');
}

function implRowsTsv(table, selectedIndices) {
    const lines = [];
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    rows.forEach(row => {
        const cells = Array.from(row.querySelectorAll('td'));
        const selected = selectedIndices.map(i => cells[i] ? cells[i].textContent.trim().replace(/\n/g, ' ') : '');
        lines.push(selected.join('\t'));
    });
    return lines;
}

// Copy selected columns for Excel implementation
function copySelectedImplColumns() {
    const activeTab = document.querySelector('#tab-implementation');
    if (!activeTab) return;

    const tables = activeTab.querySelectorAll('table');
    if (tables.length === 0) {
        alert("No tables found");
        return;
    }

    const selectedIndices = selectedImplIndices();

    if (selectedIndices.length === 0) {
        alert("Please select at least one column");
        return;
    }

    let tsv = [];

    // Use first table headers, then rows of every table
    tsv.push(implHeaderTsv(tables[0], selectedIndices));
    tables.forEach(table => {
        tsv.push(...implRowsTsv(table, selectedIndices));
    });

    navigator.clipboard.writeText(tsv.join('\n')).then(() => {
        alert("✅ All selected columns copied! Paste into Excel.");
    });
}

function copyThisEnclosure(btn) {
    const section = btn.closest('details');
    if (!section) return;

    const table = section.querySelector('table');
    if (!table) return;

    const selectedIndices = selectedImplIndices();

    if (selectedIndices.length === 0) {
        alert("Select at least one column first");
        return;
    }

    let tsv = [implHeaderTsv(table, selectedIndices), ...implRowsTsv(table, selectedIndices)];

    navigator.clipboard.writeText(tsv.join('\n')).then(() => {
        btn.textContent = "✓ Copied!";
        setTimeout(() => { btn.textContent = "📋 Copy this enclosure only"; }, 1800);
    });
}

function selectAllImplCols(select) {
    document.querySelectorAll('.impl-col').forEach(cb => {
        cb.checked = select;
    });
}

// Exposed for the inline onclick handlers in the generated report
window.expandAll = expandAll;
window.collapseAll = collapseAll;
window.copyVisibleAsHTML = copyVisibleAsHTML;
window.openTab = openTab;
window.copySelectedImplColumns = copySelectedImplColumns;
window.copyThisEnclosure = copyThisEnclosure;
window.selectAllImplCols = selectAllImplCols;
