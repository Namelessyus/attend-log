from html.parser import HTMLParser
from urllib.parse import urlsplit

from attendlog import create_app


class PageAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
        self.inline_scripts = 0
        self.ids = set()
        self.anchors = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag in {"link", "script", "img", "a"}:
            url = attrs.get("src") or attrs.get("href")
            if url:
                self.urls.append(url)
                fragment = urlsplit(url).fragment
                if fragment:
                    self.anchors.append(fragment)
        if tag == "script" and "src" not in attrs:
            self.inline_scripts += 1


def client():
    return create_app({"TESTING": True, "DATABASE_URL": None}).test_client()


def test_landing_and_every_linked_asset_resolve_locally():
    browser = client()
    response = browser.get("/")
    assert response.status_code == 200
    page = PageAssets()
    page.feed(response.text)
    assert page.inline_scripts == 0
    assert set(page.anchors).issubset(page.ids)
    for url in page.urls:
        parts = urlsplit(url)
        assert not parts.netloc, f"External runtime dependency: {url}"
        if parts.path:
            asset = browser.get(url)
            if parts.path == "/login":
                assert asset.status_code == 503  # Explicit no-database preview mode.
            elif parts.path == "/dashboard":
                assert asset.status_code == 302
            else:
                assert asset.status_code == 200, url
    font_css = browser.get("/static/fonts/fonts.css").text
    import re
    for font in re.findall(r"url\(\./([^)]+)\)", font_css):
        response = browser.get("/static/fonts/" + font)
        assert response.status_code == 200
        assert len(response.data) > 1000


def test_unavailable_features_are_honest_and_have_noscript_fallbacks():
    browser = client()
    for kind, message in [
        ("attendance", "Live attendance is not available yet."),
    ]:
        response = browser.get("/?access=" + kind)
        assert response.status_code == 200
        assert message in response.text
        assert f'open data-initial-access="{kind}"' in response.text
        assert "Return to the landing page" in response.text
    assert "<dialog" in browser.get("/?access=%3Cscript%3E").text
    assert "data-initial-access=" not in browser.get("/?access=%3Cscript%3E").text
    assert "not live student data" in browser.get("/").text
    assert browser.get("/?access=login").location == "/login"
    assert browser.get("/?access=dashboard").location == "/dashboard"


def test_private_sources_are_not_served_and_errors_are_navigable():
    browser = client()
    for url in ["/.env", "/.git/config", "/assets/source/attend-log.zip", "/missing"]:
        response = browser.get(url)
        assert response.status_code == 404
        assert "Back to AttendLog" in response.text


def test_landing_security_policy_blocks_camera_and_remote_scripts():
    response = client().get("/")
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=()"
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert "'unsafe-inline'" not in response.headers["Content-Security-Policy"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
