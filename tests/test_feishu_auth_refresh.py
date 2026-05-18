import asyncio
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeAsyncClient:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        return self.response


def make_auth(tmp_path):
    from core.feishu.auth import FeishuOAuth

    auth = FeishuOAuth()
    auth._token_file = tmp_path / "user_token.json"
    auth._user_access_token = None
    auth._token_expire_time = 0
    auth._refresh_token = None
    auth._refresh_token_expire_time = 0
    return auth


@pytest.mark.asyncio
async def test_refresh_access_token_accepts_top_level_feishu_v2_token_payload(tmp_path):
    import core.feishu.auth as auth_module

    auth = make_auth(tmp_path)
    auth._refresh_token = "old-refresh"
    auth._refresh_token_expire_time = time.time() + 3600
    response = FakeResponse(
        200,
        {
            "code": 0,
            "access_token": "new-access",
            "expires_in": 7200,
            "refresh_token": "new-refresh",
            "refresh_token_expires_in": 604800,
        },
    )

    with patch.object(
        auth_module.httpx,
        "AsyncClient",
        side_effect=lambda timeout=30: FakeAsyncClient(response),
    ):
        token_data = await auth.refresh_access_token()

    saved = json.loads(auth._token_file.read_text(encoding="utf-8"))
    assert token_data["access_token"] == "new-access"
    assert auth._user_access_token == "new-access"
    assert saved["access_token"] == "new-access"
    assert auth._refresh_token == "new-refresh"


@pytest.mark.asyncio
async def test_concurrent_get_user_access_token_refreshes_only_once(tmp_path):
    auth = make_auth(tmp_path)
    auth._user_access_token = "expired-access"
    auth._token_expire_time = time.time() - 1
    auth._refresh_token = "refresh-token"
    auth._refresh_token_expire_time = time.time() + 3600
    refresh_calls = 0

    async def fake_refresh_access_token():
        nonlocal refresh_calls
        refresh_calls += 1
        await asyncio.sleep(0.01)
        auth._user_access_token = "new-access"
        auth._token_expire_time = time.time() + 3600
        return {"access_token": "new-access"}

    auth.refresh_access_token = fake_refresh_access_token

    tokens = await asyncio.gather(
        *(auth.get_user_access_token() for _ in range(5))
    )

    assert refresh_calls == 1
    assert tokens == ["new-access"] * 5


def test_token_info_does_not_report_remaining_access_time_without_access_token(tmp_path):
    auth = make_auth(tmp_path)
    auth._user_access_token = None
    auth._token_expire_time = time.time() + 3600
    auth._refresh_token = "refresh-token"
    auth._refresh_token_expire_time = time.time() + 3600

    token_info = auth.get_token_info()

    assert token_info["has_access_token"] is False
    assert token_info["access_token_valid"] is False
    assert token_info["access_token_remaining"] == 0


def test_token_file_uses_configured_runtime_data_dir():
    from config import DATA_DIR
    from core.feishu.auth import FeishuOAuth

    auth = FeishuOAuth()

    assert auth._token_file == DATA_DIR / "user_token.json"


def test_load_token_marks_future_expiry_without_access_token_as_unusable(tmp_path):
    auth = make_auth(tmp_path)
    auth._token_file.write_text(
        json.dumps(
            {
                "access_token": None,
                "expires_at": time.time() + 3600,
                "refresh_token": "stale-refresh",
                "refresh_expires_at": time.time() + 7200,
            }
        ),
        encoding="utf-8",
    )

    auth._load_token()
    token_info = auth.get_token_info()

    assert token_info["status"] == "refresh_expired"
    assert token_info["access_token_remaining"] == 0
    assert token_info["refresh_token_valid"] is False


@pytest.mark.asyncio
async def test_refresh_failure_marks_refresh_token_unusable_for_status(tmp_path):
    auth = make_auth(tmp_path)
    auth._user_access_token = "expired-access"
    auth._token_expire_time = time.time() - 1
    auth._refresh_token = "refresh-token"
    auth._refresh_token_expire_time = time.time() + 3600
    refresh_calls = 0

    async def fake_refresh_access_token():
        nonlocal refresh_calls
        refresh_calls += 1
        raise Exception("status=400, code=20064, msg=invalid refresh_token")

    auth.refresh_access_token = fake_refresh_access_token

    with pytest.raises(Exception):
        await auth.get_user_access_token()
    with pytest.raises(Exception):
        await auth.get_user_access_token()

    token_info = auth.get_token_info()
    assert refresh_calls == 1
    assert token_info["status"] == "refresh_expired"
    assert token_info["refresh_token_valid"] is False
    assert token_info["refresh_token_remaining"] == 0


@pytest.mark.asyncio
async def test_transient_refresh_failure_keeps_refresh_token_retryable(tmp_path):
    auth = make_auth(tmp_path)
    auth._user_access_token = "expired-access"
    auth._token_expire_time = time.time() - 1
    auth._refresh_token = "refresh-token"
    auth._refresh_token_expire_time = time.time() + 3600
    refresh_calls = 0

    async def fake_refresh_access_token():
        nonlocal refresh_calls
        refresh_calls += 1
        raise Exception("status=503, msg=temporary upstream unavailable")

    auth.refresh_access_token = fake_refresh_access_token

    with pytest.raises(Exception):
        await auth.get_user_access_token()
    with pytest.raises(Exception):
        await auth.get_user_access_token()

    token_info = auth.get_token_info()
    assert refresh_calls == 2
    assert token_info["status"] == "expired_refreshable"
    assert token_info["refresh_token_valid"] is True
    assert token_info["refresh_token_remaining"] > 0
