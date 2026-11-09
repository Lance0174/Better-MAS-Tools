"""引导跳过状态随服务重启保留，并防止旧设置草稿将其恢复。"""

from fastapi.testclient import TestClient

from app.main import create_app


def test_dismissal_survives_restart_and_stale_settings(tmp_path):
    app = create_app(data_dir=tmp_path, start_scheduler=False)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        client.headers["x-community-session"] = app.state.session_key
        original = client.get("/api/settings").json()["data"]
        assert original["OnboardingDismissed"] is False
        assert (
            client.put(
                "/api/settings",
                json={
                    **original,
                    "OnboardingDismissed": True,
                },
            ).status_code
            == 200
        )
        # 旧窗口保存其它设置时携带的 false 不得重新开启自动引导。
        original["Theme"] = "dark"
        assert client.put("/api/settings", json=original).status_code == 200

    restarted = create_app(data_dir=tmp_path, start_scheduler=False)
    with TestClient(restarted, base_url="http://127.0.0.1:39876") as client:
        client.headers["x-community-session"] = restarted.state.session_key
        data = client.get("/api/settings").json()["data"]
        assert data["OnboardingDismissed"] is True
        assert data["Theme"] == "dark"
