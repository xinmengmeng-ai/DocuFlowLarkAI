from pathlib import Path


FRONTEND_HTML = Path(__file__).parent.parent / "frontend" / "index.html"


def test_stats_cards_always_follow_backend_stats():
    html = FRONTEND_HTML.read_text(encoding="utf-8")
    update_stats_block = html.split("function updateStats(processed, failed, tokens, api, duplicate = 0) {", 1)[1]
    update_stats_block = update_stats_block.split("function updateThroughputByApiCount", 1)[0]

    assert "if (!latestFileStatusList || latestFileStatusList.length === 0)" not in update_stats_block
    assert "setElementText('status-success-count', processed || 0);" in update_stats_block
    assert "setElementText('status-failed-count', failed || 0);" in update_stats_block


def test_stats_update_does_not_require_hidden_duplicate_card():
    html = FRONTEND_HTML.read_text(encoding="utf-8")
    update_stats_block = html.split("function updateStats(processed, failed, tokens, api, duplicate = 0) {", 1)[1]
    update_stats_block = update_stats_block.split("function updateThroughputByApiCount", 1)[0]
    file_status_block = html.split("function updateFileStatusSummary(fileStatus = []) {", 1)[1]
    file_status_block = file_status_block.split("function showStatusFilesModal", 1)[0]

    assert "function setElementText" in html
    assert "document.getElementById('status-duplicate-count').innerText" not in update_stats_block
    assert "document.getElementById('status-duplicate-count').innerText" not in file_status_block
    assert "setElementText('stat-tokens', (tokens || 0).toLocaleString());" in update_stats_block
    assert "setElementText('stat-api', api || 0);" in update_stats_block


def test_monitor_shows_task_elapsed_time_from_progress_messages():
    html = FRONTEND_HTML.read_text(encoding="utf-8")

    assert 'id="task-elapsed-time"' in html
    assert "function formatDuration(totalSeconds)" in html
    assert "updateElapsedTime(message.data.elapsed_seconds);" in html
    assert "updateElapsedTime(0);" in html


def test_websocket_status_message_restores_stats_cards_after_reconnect():
    html = FRONTEND_HTML.read_text(encoding="utf-8")
    status_case = html.split("case 'status':", 1)[1].split("break;", 1)[0]

    assert "message.data.stats" in status_case
    assert "updateStats(" in status_case
    assert "message.data.stats.processed" in status_case
    assert "message.data.stats.failed" in status_case
    assert "message.data.stats.tokens" in status_case
    assert "message.data.stats.api_calls" in status_case


def test_failed_file_modal_displays_user_friendly_reason():
    html = FRONTEND_HTML.read_text(encoding="utf-8")
    summary_block = html.split("function updateFileStatusSummary(fileStatus = []) {", 1)[1]
    summary_block = summary_block.split("function showStatusFilesModal", 1)[0]
    modal_block = html.split("function showStatusFilesModal(status) {", 1)[1]
    modal_block = modal_block.split("function closeStatusFilesModal", 1)[0]

    assert "normalizeStatusFileItem(item)" in summary_block
    assert "grouped.failed.push(entry)" in summary_block
    assert "getStatusFileReason" in html
    assert "失败原因" in modal_block
    assert "error_message" in modal_block
