from pathlib import Path

import app as app_module


def test_root_serves_built_react_app(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text(
        "<!doctype html><title>唱片桌面</title>", encoding="utf-8"
    )
    monkeypatch.setattr(app_module, "WEB_DIST_DIR", str(tmp_path))

    response = app_module.app.test_client().get("/")

    assert response.status_code == 200
    assert "唱片桌面" in response.get_data(as_text=True)


def test_root_explains_how_to_build_when_frontend_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "WEB_DIST_DIR", str(tmp_path))

    response = app_module.app.test_client().get("/")

    assert response.status_code == 503
    assert "npm run build" in response.get_data(as_text=True)


def test_legacy_template_only_redirects_to_running_app():
    template = Path("templates/index.html").read_text(encoding="utf-8")

    assert "http://127.0.0.1:5050/" in template
    assert "/api/characters" not in template
    assert "/api/switch" not in template
    assert "/api/new" not in template


def test_search_limit_is_validated_and_clamped(monkeypatch):
    seen = []

    def fake_search(query, limit):
        seen.append((query, limit))
        return []

    monkeypatch.setattr(app_module, "qqmusic_search", fake_search)
    client = app_module.app.test_client()

    assert client.get("/api/search?q=test&limit=nope").status_code == 400
    assert client.get("/api/search?q=test&limit=999").status_code == 200
    assert seen == [("test", 30)]
