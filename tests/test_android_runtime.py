"""升级旧手机配置时停用远端执行，保留原账号配置。"""

import json

import pytest

from app.core.android_runtime import AndroidRuntime
from app.core.state import state
from app.models.config import AccountData, SavedState
from app.services.network import network


@pytest.mark.asyncio
async def test_android_legacy_remote_flags_are_disabled_and_saved(monkeypatch):
    original = SavedState()
    original.accounts["fixture-account"] = AccountData()
    original.settings.OnboardingDismissed = True
    original.settings.CloudMode = True
    original.settings.RelayEnabled = True
    original.settings.CloudBaseUrl = "https://fixture.example.invalid"
    writes = []

    async def native_call(operation, payload):
        if operation == "state.read":
            return json.dumps({"state": original.model_dump_json()})
        if operation == "state.write":
            writes.append(json.loads(payload)["state"])
            return '{"saved":true}'
        if operation == "wiki.read":
            return '{"content":null}'
        raise AssertionError(f"unexpected native operation: {operation}")

    monkeypatch.setattr(state, "data", original)
    monkeypatch.setattr(state, "storage", None)
    monkeypatch.setattr(state, "revision", state.revision)
    monkeypatch.setattr(network, "transport_factory", None)
    monkeypatch.setattr(network, "local_connections", True)
    monkeypatch.setattr(network, "proxy", None)
    runtime = AndroidRuntime(native_call)
    try:
        await runtime.initialize(run_startup=False)
        assert len(writes) == 1
        restored = SavedState.model_validate_json(writes[0])
        assert not restored.settings.CloudMode
        assert not restored.settings.RelayEnabled
        assert restored.settings.CloudBaseUrl == original.settings.CloudBaseUrl
        assert restored.accounts == original.accounts
        assert restored.settings.OnboardingDismissed
        assert runtime.client is not None
        session = (await runtime.client.get("/api/session")).json()
        runtime.client.headers["x-community-session"] = session["key"]
        assert (await runtime.client.get("/api/mas/snapshot")).status_code == 404
    finally:
        if runtime.client is not None:
            await runtime.client.aclose()
