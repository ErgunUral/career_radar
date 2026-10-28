"""XSS + URL sanitize tests (FAZ 1a) — apps/frontend/_url_utils.py içindeki sanitize_url / safe_html_anchor."""
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
ROOT = API_DIR.parent
FRONTEND_DIR = ROOT / "frontend"
if str(FRONTEND_DIR.resolve()) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR.resolve()))

from _url_utils import sanitize_url, safe_html_anchor  # noqa: E402


def test_sanitize_url_https_ok() -> None:
    u = "https://www.linkedin.com/jobs/view/4451140027"
    assert sanitize_url(u) == u


def test_sanitize_url_http_ok() -> None:
    assert sanitize_url("http://example.com/a") == "http://example.com/a"


def test_sanitize_url_javascript_blocked() -> None:
    assert sanitize_url("javascript:alert(1)") == "#"


def test_sanitize_url_data_blocked() -> None:
    assert sanitize_url("data:text/html,<h1>hi</h1>") == "#"


def test_sanitize_url_file_blocked() -> None:
    assert sanitize_url("file:///etc/passwd") == "#"


def test_sanitize_url_whitespace_blocked() -> None:
    # URL içinde space/newline gibi kontrol karakterleri varsa BLOKLA (#)
    assert sanitize_url("  https://x.com/a\n b  ") == "#"


def test_sanitize_url_empty_none() -> None:
    assert sanitize_url("") == "#"
    assert sanitize_url(None) == "#"


def test_safe_html_anchor_escapes_label_and_attribute() -> None:
    """Başlık içindeki <script> ve URL'deki " + onmouseover BLOCKLANDI (URL # oldu)."""
    label = '<script>alert("xss")</script>'
    url = 'https://x.com/a" onmouseover="alert(1)"'
    html_out = safe_html_anchor(url, label)
    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out
    # URL tehlikeli karakterler içerdiğinden # olarak blocklandı — onmouseover özellik olarak değil, string olarak hiç geçmemeli
    assert 'href="#"' in html_out
    assert "onmouseover" not in html_out
    # target blank + rel op
    assert 'target="_blank"' in html_out
    assert "noopener noreferrer" in html_out


def test_safe_html_anchor_no_class_when_empty() -> None:
    html = safe_html_anchor("https://a", "b", extra_css_class="")
    assert 'class="' not in html


def test_safe_html_anchor_no_target_when_false() -> None:
    html = safe_html_anchor("https://a", "b", target_blank=False)
    assert 'target="_blank"' not in html
