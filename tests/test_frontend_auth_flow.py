import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def read_frontend() -> str:
    return (ROOT_DIR / "frontend" / "index.html").read_text(encoding="utf-8")


def extract_function_body(source: str, function_name: str) -> str:
    marker = f"async function {function_name}("
    start = source.index(marker)
    brace_start = source.index("{", start)
    depth = 0
    for index in range(brace_start, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[brace_start + 1:index]
    raise AssertionError(f"Could not parse function body for {function_name}")


def test_authorize_feishu_saves_current_credentials_before_auth_url_request():
    source = read_frontend()
    handle_auth_click = extract_function_body(source, "handleAuthClick")
    save_before_auth_index = handle_auth_click.index("await ensureFeishuConfigSavedBeforeAuth()")
    auth_url_index = handle_auth_click.index("apiCall('GET', '/api/auth/url")

    assert save_before_auth_index < auth_url_index

    helper_body = extract_function_body(source, "ensureFeishuConfigSavedBeforeAuth")
    assert "feishu-app-id" in helper_body
    assert "feishu-app-secret" in helper_body
    assert "apiCall('POST', '/api/config'" in helper_body
    assert re.search(r"config\s*=\s*\{\s*feishu\s*:", helper_body)
