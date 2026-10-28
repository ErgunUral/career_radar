from __future__ import annotations

import json
import logging
import re
import time
import xml.etree.ElementTree as ET
import zlib
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

try:  # opsiyonel: BROTLI sıkıştırma decode (bazı siteler br gönderir)
    import brotli  # type: ignore

    _HAS_BROTLI = True
except Exception:
    _HAS_BROTLI = False
    brotli = None  # type: ignore

try:  # opsiyonel: Cloudflare Akamai TLS bypass
    import cloudscraper  # type: ignore

    _HAS_CLOUDSCRAPER = True
except Exception:
    _HAS_CLOUDSCRAPER = False
    cloudscraper = None  # type: ignore

try:  # opsiyonel: gerçek tarayıcı ile JS render + bot koruması bypass (son çare)
    from playwright.sync_api import (
        TimeoutError as PlaywrightTimeoutError,
    )
    from playwright.sync_api import (
        sync_playwright,
    )  # type: ignore

    _HAS_PLAYWRIGHT = True
except Exception:
    _HAS_PLAYWRIGHT = False
    sync_playwright = None  # type: ignore
    PlaywrightTimeoutError = Exception  # type: ignore

from ..jobs.schemas import JobSourcePlatform
from ..matching.schemas import WorkMode
from .schemas import DiscoveredJobInput, DiscoverySourceReport


class LiveJobDiscoveryService:
    DEFAULT_UA = "CareerRadarAI/0.1 (+live-discovery)"
    CHROME_UA = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
    _UA_POOL = [
        CHROME_UA,
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4; rv:128.0) Gecko/20100101 Firefox/128.0",
    ]

    _BOT_HTTP_STATUSES = {403, 429, 999, 503, 451}
    _BOT_TEXT_HINTS = (
        "cloudflare",
        "akamai",
        "perimeterx",
        "captcha",
        "bot protection",
        "tarayıcı doğrulaması",
        "güvenlik doğrulaması",
        "just a moment",
        "hız sınırı",
        "rate limit",
        "lütfen doğrulayın",
    )
    _PW_CHROMIUM_ARGS = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-web-security",
        "--disable-features=IsolateOrigins,site-per-process",
        "--start-maximized",
    ]

    def __init__(
        self,
        timeout_seconds: float = 10.0,
        *,
        debug_mode: bool = False,
        storage_state_path: str | None = None,
        slow_mo_ms: int = 0,
        pw_headless_override: bool | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.debug_mode = bool(debug_mode)
        self.storage_state_path = storage_state_path
        self.slow_mo_ms = max(0, int(slow_mo_ms or 0))
        self.pw_headless_override = pw_headless_override
        # Playwright HAVUZ (pooling): TEK launch + TEK context — HER URL için yeni page
        self._pw: Any | None = (
            None  # sync_playwright() yöneticisi (None = henüz başlatılmadı)
        )
        self._pw_browser: Any | None = None  # Tek chromium tarayıcı nesnesi
        self._pw_context: Any | None = None  # Tek cookie/localStorage paylaşan context
        self._pw_ua: str | None = None  # Havuz başlatıldığında kullanılan User-Agent
        # default storage state path (bir kez manuel giriş yapılınca sonraki oturumlarda hatırlamak için)
        if not self.storage_state_path:
            try:
                import os

                # __file__ = .../apps/api/app/domains/watchers/discovery.py
                # 3 seviye yukarı → .../apps/api/app/ altında storage/ dizin
                here = os.path.abspath(__file__)
                app_root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
                default_dir = os.path.join(app_root, "storage")
                os.makedirs(default_dir, exist_ok=True)
                self.storage_state_path = os.path.join(
                    default_dir, "playwright_state.json"
                )
            except Exception:
                self.storage_state_path = None

    def close_playwright_pool(self) -> None:
        """Playwright HAVUZU kapatır — storage state'i TEK seferde kaydeder (SONDA)."""
        if self._pw_context is not None:
            try:
                # 🔒 TEK SEFER storage_state kaydet (EN SONDA tüm URL'den sonra)
                if self.storage_state_path:
                    try:
                        self._pw_context.storage_state(path=self.storage_state_path)
                    except Exception:
                        logging.exception("BLE001 discovery suppressed inner exception")
                self._pw_context.close()
            except Exception:
                logging.exception("BLE001 discovery suppressed mid exception")
            self._pw_context = None
        if self._pw_browser is not None:
            try:
                self._pw_browser.close()
            except Exception:
                logging.exception("BLE001 discovery suppressed mid exception")
            self._pw_browser = None
        self._pw = None
        self._pw_ua = None

    def _ensure_playwright_pool(self, pw_mgr, ua: str, lang: str, headless: bool):
        """Eğer havuz yoksa: 1 KERE chromium + context AÇ (4-6sn tek seferlik masraf). pw_mgr = with sync_playwright() as pw_mgr."""
        import os as _os

        if self._pw_browser is None or self._pw_context is None:
            if not _HAS_PLAYWRIGHT or pw_mgr is None:
                raise RuntimeError("playwright yüklü değil / yöneticisi yok")
            state_exists = self.storage_state_path and _os.path.isfile(
                self.storage_state_path
            )
            # Browser LAUNCH (1 kere, 4-6sn)
            browser_kwargs = {
                "headless": headless,
                "args": list(self._PW_CHROMIUM_ARGS),
            }
            if self.slow_mo_ms:
                browser_kwargs["slow_mo"] = self.slow_mo_ms
            self._pw_browser = pw_mgr.chromium.launch(**browser_kwargs)
            # Context (1 kere)
            ctx_kwargs = dict(
                user_agent=ua,
                locale=lang[:5],
                accept_downloads=False,
                viewport={"width": 1440, "height": 900},
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
                ignore_https_errors=True,
                extra_http_headers={"Accept-Language": lang},
            )
            if self.storage_state_path and state_exists:
                ctx_kwargs["storage_state"] = self.storage_state_path
            assert self._pw_browser is not None, (
                "Chromium launch başarısız (_pw_browser None)"
            )
            self._pw_context = self._pw_browser.new_context(**ctx_kwargs)
            self._pw_ua = ua
            self._pw = pw_mgr  # parent manager referans (lifecycle ile yönetiliyor)

    def _headers_for(self, url: str) -> dict[str, str]:
        host = urlparse(url).netloc.casefold()
        base = {
            "User-Agent": self.DEFAULT_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        if "kariyer.net" in host:
            base.update(
                {
                    "User-Agent": self.CHROME_UA,
                    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Referer": "https://www.kariyer.net/",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                }
            )
        elif "linkedin." in host:
            # LinkedIn Public job search: Referer + Sec-Fetch-Site=same-origin kombinasyonu
            #   LI bot-korumasını tetikliyor → HTTP 999 authwall döndürüyor.
            # Buna karşılık, **yalnızca UA + Accept (minimal)** gönderildiğinde → HTTP 200 OK 60+ job.
            # Public `/jobs/search?keywords=...` için:
            path_and_q = (urlparse(url).path or "") + "?" + (urlparse(url).query or "")
            if "/jobs/search" in path_and_q.casefold():
                base.update(
                    {
                        "User-Agent": self.CHROME_UA,
                        "Accept-Language": "en-US,en;q=0.9,tr;q=0.7",
                    }
                )
            else:
                base.update(
                    {
                        "User-Agent": self.CHROME_UA,
                        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                        "Referer": "https://www.linkedin.com/",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "same-origin",
                        "Upgrade-Insecure-Requests": "1",
                    }
                )
        elif "greenhouse.io" in host or "greenhouse" in host:
            base["Accept"] = (
                "application/json,text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"
            )
            base["Accept-Language"] = "en-US,en;q=0.9,tr-TR;q=0.7,tr;q=0.6"
        elif "lever.co" in host:
            base["Accept"] = "application/json,text/html;q=0.9,*/*;q=0.8"
            base["Accept-Language"] = "en-US,en;q=0.9"
        return base

    def _rotate_user_agent(self) -> str:
        import random as _r

        return (
            self._UA_POOL[_r.randrange(len(self._UA_POOL))]
            if self._UA_POOL
            else self.CHROME_UA
        )

    @staticmethod
    def _decode_body_bytes(raw: bytes, ce_hint: str | None = None) -> str:
        """httpx/cs text decode başarısız olursa (brotli, gzip, deflate) MANUEL bytes decode et."""
        if not raw:
            return ""
        data: bytes = raw
        ce = (ce_hint or "").casefold().strip()
        # 1) Content-Encoding'e göre sıkıştırmayı aç
        for _ in range(2):
            try:
                if "br" in ce and _HAS_BROTLI and brotli is not None:
                    data = brotli.decompress(data)
                    break
                if "gzip" in ce:
                    data = zlib.decompress(data, 16 + zlib.MAX_WBITS)
                    break
                if "deflate" in ce:
                    try:
                        data = zlib.decompress(data)
                    except zlib.error:
                        data = zlib.decompress(data, -zlib.MAX_WBITS)
                    break
            except Exception:
                logging.exception("BLE001 discovery suppressed mid exception")
            # 2) Content-Encoding yanlış/eksikse — MAGIC BYTES ile tahmin et (br/gzip)
            if len(data) >= 2:
                if data[:2] == b"\x1f\x8b":  # gzip magic
                    try:
                        data = zlib.decompress(data, 16 + zlib.MAX_WBITS)
                        break
                    except Exception:
                        logging.exception("BLE001 discovery suppressed inner exception")
                if _HAS_BROTLI and brotli is not None and len(data) >= 4:
                    try:
                        candidate = brotli.decompress(data)
                        if len(candidate) > len(data) // 2:
                            data = candidate
                            break
                    except Exception:
                        logging.exception("BLE001 discovery suppressed inner exception")
            break
        # 3) String'e çevir (utf-8 önce, sonra windows-1254 (TR), sonra replace)
        for enc in ("utf-8", "cp1254", "iso-8859-9", "latin-1"):
            try:
                return data.decode(enc)
            except Exception:
                continue
        return data.decode("utf-8", errors="replace")

    @staticmethod
    def _body_looks_garbage(text: str) -> bool:
        """Decode başarısız text (binary garbage) — non-printable > %35 ise."""
        if not text or len(text) < 200:
            return False
        import string

        printable = set(string.printable)
        bad = sum(1 for ch in text[:4000] if ch not in printable and not ch.isspace())
        return bad / min(len(text), 4000) > 0.35

    def _looks_like_bot_blocked(self, status_code: int, body: str) -> bool:
        if status_code in self._BOT_HTTP_STATUSES:
            return True
        if not body:
            return False
        lowered = body.casefold()
        return any(hint in lowered for hint in self._BOT_TEXT_HINTS)

    # Bot koruması YÜKSEK olan domainler: HTTPX denemeden DIREKT 3.katman Playwright kullan
    #   kariyer.net    → IP tabanlı 403 (0.6sn sleep + UA rotate yetmiyor)
    #   yenibiris.com  → Aynı ağ (KN grubu) — bot koruması çok sıkı
    #   linkedin.com   → 999 auth response, storage_state cookie + tarayıcı RENDER ŞART
    #   eleman.net     → SPA (React/Next) — HTML'de job kartı yok, JS ile doldurulur (HTTPX 0 iş)
    _DOMAINS_FORCE_PLAYWRIGHT = {
        "kariyer.net",
        "www.kariyer.net",
        "m.kariyer.net",
        "yenibiris.com",
        "www.yenibiris.com",
        "linkedin.com",
        "www.linkedin.com",
        "tr.linkedin.com",
        "eleman.net",
        "www.eleman.net",
    }

    def _should_force_playwright(self, url: str) -> bool:
        """URL'deki domain bot koruması yüksek domainler listesindeyse → Playwright atla (Katman 1/2 NOPE).

        Exception: LinkedIn Public `/jobs/search?keywords=` URL'leri httpx ile 200 OK + 60+ iş ilanı HTML veriyor.
        Bu özel URL'lerde LI Playwright zorlaması KAPATILIR (Playwright 999 bot reddi verir).
        """
        try:
            host = urlparse(url).netloc.casefold().strip()
            path_and_q = (urlparse(url).path or "") + "?" + (urlparse(url).query or "")
            # LinkedIn public unauth job search: httpx çalışır, Playwright 999 verir → bypass
            if ("linkedin.com" in host) and ("/jobs/search" in path_and_q.casefold()):
                return False
            if host in self._DOMAINS_FORCE_PLAYWRIGHT:
                return True
            # Parent domain eşleşmesi (x.kariyer.net → kariyer.net)
            parts = host.split(".")
            if len(parts) >= 2:
                parent = ".".join(parts[-2:])
                if parent in self._DOMAINS_FORCE_PLAYWRIGHT:
                    # Tekrar LI public search kontrolü (parent match case'inde)
                    if parent == "linkedin.com" and "/jobs/search" in path_and_q.casefold():
                        return False
                    return True
        except Exception:
            logging.exception("BLE001 discovery suppressed outer exception")
        return False

    def _fetch_html_with_fallback(
        self, url: str, allow_playwright: bool = True
    ) -> tuple[int, str, str, str]:
        """
        Üç katmanlı akıllı scraper fallback:
          1. httpx.get (standart, hızlı)  ←  _DOMAINS_FORCE_PLAYWRIGHT listesinde ATLANIR
          2. cloudscraper (opsiyonel — Cloudflare/Akamai TLS handshake taklidi)  ←  aynı şekilde atlanır
          3. Playwright headless Chromium (opsiyonel — en ağır, tam JS render + bot gizleme)
        Dönüş: (status_code, body_text, content_type, fetch_method: 'httpx'|'cloudscraper'|'playwright'|'error')
        """
        headers = dict(self._headers_for(url))
        timeout = float(self.timeout_seconds)
        last_error: str | None = None

        # ── BOT KORUMASI YÜKSEK SİTELER: Direkt Playwright (Katman 1+2'ye GİTME) ──
        # Bu sayede: (KN 403 / LI 999 / Eleman SPA 0 job) sorunları BAŞTAN ÖNLENİR
        if allow_playwright and self._should_force_playwright(url):
            try:
                pw_status, pw_body, pw_ct = self._playwright_fetch_page(
                    url, timeout, slow_mo_ms=self.slow_mo_ms
                )
                return (
                    int(pw_status or 200),
                    pw_body or "",
                    pw_ct or "",
                    "playwright (forced)",
                )
            except Exception as pw_e:
                # Fallback: Playwright da patlarsa normal katmanlara devam et (son şans)
                last_error = f"pw_force: {type(pw_e).__name__}: {str(pw_e)[:160]}"

        fetch_method = "httpx"
        status: int = 0
        content_type: str = ""
        body_text: str = ""
        try:
            response = httpx.get(
                url, timeout=timeout, follow_redirects=True, headers=headers
            )
            status = int(response.status_code or 0)
            content_type = response.headers.get("content-type", "") or ""
            body_text = response.text or ""
            ce = response.headers.get("content-encoding", "") or ""
            # Garbage check (BROTLI vb. yanlış decode) → bytes'tan manuel decode et
            if body_text and self._body_looks_garbage(body_text):
                body_text = self._decode_body_bytes(response.content or b"", ce_hint=ce)
            if status < 400 and not self._looks_like_bot_blocked(status, body_text):
                return status, body_text, content_type, fetch_method
        except Exception as e:
            last_error = f"httpx: {type(e).__name__}: {str(e)[:160]}"

        # --- Katman 2: cloudscraper (opsiyonel) ---
        if _HAS_CLOUDSCRAPER and (
            last_error or self._looks_like_bot_blocked(status, body_text)
        ):
            fetch_method = "cloudscraper"
            try:
                scraper = cloudscraper.create_scraper(
                    browser={"browser": "chrome", "platform": "osx", "desktop": True}
                )
                cs_headers = dict(headers)
                cs_headers["User-Agent"] = self._rotate_user_agent()
                cs_resp = scraper.get(
                    url, headers=cs_headers, timeout=max(timeout, 15.0)
                )
                status = int(cs_resp.status_code or 0)
                content_type = cs_resp.headers.get("content-type", "") or ""
                body_text = cs_resp.text or ""
                cs_ce = cs_resp.headers.get("content-encoding", "") or ""
                if body_text and self._body_looks_garbage(body_text):
                    try:
                        body_text = self._decode_body_bytes(
                            cs_resp.content or b"", ce_hint=cs_ce
                        )
                    except Exception:
                        logging.exception("BLE001 discovery suppressed inner exception")
                if status < 400 and not self._looks_like_bot_blocked(status, body_text):
                    return status, body_text, content_type, fetch_method
            except Exception as e:
                last_error = f"cloudscraper: {type(e).__name__}: {str(e)[:160]}"

        # --- Katman 3: Playwright (son çare) — allow_playwright False ise atla ---
        if (
            allow_playwright
            and _HAS_PLAYWRIGHT
            and (last_error or self._looks_like_bot_blocked(status, body_text))
        ):
            fetch_method = "playwright"
            try:
                status, body_text, content_type = self._playwright_fetch_page(
                    url, timeout=max(timeout, 25.0)
                )
                if (
                    status
                    and status < 400
                    and not self._looks_like_bot_blocked(status, body_text)
                ):
                    return status, body_text, content_type, fetch_method
            except Exception as e:
                last_error = f"playwright: {type(e).__name__}: {str(e)[:160]}"

        if last_error and not body_text:
            raise RuntimeError(last_error)
        return status, body_text, content_type, fetch_method

    def _playwright_fetch_page(
        self, url: str, timeout: float, slow_mo_ms: int = 0
    ) -> tuple[int, str, str]:
        """Playwright HAVUZ (pooling): TEK launch+context üzerinden HER URL için YENİ page açar — %50-70 hızlanma."""
        _ = slow_mo_ms  # type: ignore[no-redef,unused-ignore]  # Slow-mo, opsiyonel debug
        if not _HAS_PLAYWRIGHT or sync_playwright is None:
            raise RuntimeError("playwright yüklü değil")
        ua = self._rotate_user_agent()
        host = urlparse(url).netloc.casefold()
        lang = (
            "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
            if ("kariyer.net" in host or "linkedin." in host or "turk" in host)
            else "en-US,en;q=0.9"
        )
        status = 0
        body_text = ""
        content_type = ""
        # Headed / headless seçimi:
        #   pw_headless_override ayarlanmışsa onu kullan
        #   debug_mode=True ise headless=False (görünür pencere)
        #   aksi halde True (arkaplanda)
        if self.pw_headless_override is None:
            headless = False if self.debug_mode else True
        else:
            headless = bool(self.pw_headless_override)

        # 🌟 HAVUZ (Pool) — TEK launch + TEK context (İLK URL'DE 1 KERE AÇILIR, SONRAKİ URL'LER AYNISINDAN PAGE AÇAR)
        self._ensure_playwright_pool(
            pw_mgr=self._pw, ua=ua, lang=lang, headless=headless
        )
        assert self._pw_context is not None, (
            "Havuz başlatıldı ama context None — beklenmedik durum"
        )

        # 🌟 HER URL için YENİ PAGE (context'ten türetilmiş — cookie ve localStorage paylaşılır)
        page = self._pw_context.new_page()
        try:

            def capture_response(resp):
                nonlocal status, content_type
                if resp.url.rstrip("/") == url.rstrip("/") or not status:
                    try:
                        status = max(status, int(resp.status or 0))
                        ct = resp.headers.get("content-type") or ""
                        if ct:
                            content_type = ct
                    except Exception:
                        logging.exception("BLE001 discovery suppressed inner exception")

            page.on("response", capture_response)
            goto_timeout_ms = max(int(timeout * 1000), 15000)
            if self.debug_mode:
                goto_timeout_ms = max(
                    goto_timeout_ms, 60000
                )  # debugda daha uzun — manuel giriş için
            page.goto(url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
            try:
                page.wait_for_load_state(
                    "networkidle", timeout=8000 if not self.debug_mode else 30000
                )
            except PlaywrightTimeoutError:
                pass
            try:
                page.mouse.move(100, 100)
                page.wait_for_timeout(500 if not self.debug_mode else 1500)
            except Exception:
                logging.exception("BLE001 discovery suppressed mid exception")
            # Debug / görünür modda: sayfa açıldıktan sonra kullanıcı manuel giriş yapabilmesi için bekle
            if self.debug_mode:
                try:
                    _wait_msg = (
                        "⚠️  DEBUG MOD — Tarayıcı penceresini kontrol edin.\n"
                        "   Giriş / captcha / doğrulama yapın, devam etmek için bu terminal penceresinde ENTER'a basın.\n"
                        "   (LinkedIn/Kariyer.net'e giriş yaparsanız sonraki çalıştırmalarda otomatik hatırlanacaktır.)\n"
                    )
                    print(_wait_msg, flush=True)
                    try:
                        # input() — çalışmazsa timeout geçsin
                        import select
                        import sys

                        ri, _, _ = select.select([sys.stdin], [], [], 180)
                        if ri:
                            try:
                                sys.stdin.readline()
                            except Exception:
                                logging.exception("BLE001 discovery suppressed deepest exception")
                    except Exception:
                        page.wait_for_timeout(30000)
                except Exception:
                    page.wait_for_timeout(30000)
            if not status:
                status = 200
            body_text = page.content() or ""
        finally:
            # 🌟 HER URL sonunda SADECE PAGE kapat — browser & context AÇIK kalsın (SONRAKİ URL'ler kullanır!)
            # Storage state kaydetme ARTIK BURADA DEĞİL — close_playwright_pool()'da TEK SEFER (son URL'den sonra)
            try:
                page.close(timeout=5000)
            except Exception:
                logging.exception("BLE001 discovery suppressed mid exception")
        return status, body_text, content_type

    def discover(
        self,
        source_urls: list[str],
        max_jobs: int = 10,
    ) -> tuple[list[DiscoveredJobInput], list[DiscoverySourceReport]]:
        discovered: list[DiscoveredJobInput] = []
        reports: list[DiscoverySourceReport] = []
        seen_keys: set[tuple[str, str, str]] = set()

        # 🌟 TEK SEFER Playwright YÖNETİCİSİ (tüm URL'ler boyunca AÇIK KALSIN — lifecycle with bloğu tarafından yönetilir)
        # Eğer hiç playwright URL'e gerek kalmazsa (hepsi httpx geçerse), 0 launch masrafı olur
        pw_ctx: Any | None = None
        if _HAS_PLAYWRIGHT:
            # Context manager'ı elle __enter__/__exit__ — finally'de __exit__ garantisi
            pw_ctx = sync_playwright() if sync_playwright is not None else None
            if pw_ctx is not None:
                self._pw = pw_ctx.__enter__()
        try:
            for _idx, source_url in enumerate(source_urls):
                # KN/LI bot koruma — 2. URL'den itibaren 0.6sn bekle + UA rotate her turda
                if _idx > 0:
                    time.sleep(0.6)
                source_platform = self._infer_source_platform(source_url)
                fetch_method = "httpx"
                status_code = 0
                extra_note: str = ""
                try:
                    status_code, body_text, content_type, fetch_method = (
                        self._fetch_html_with_fallback(source_url)
                    )
                    if status_code and status_code >= 400:
                        raise httpx.HTTPStatusError(
                            f"HTTP {status_code}",
                            request=httpx.Request("GET", source_url),
                            response=httpx.Response(status_code=status_code),
                        )
                    jobs = self._extract_jobs(
                        source_url=source_url,
                        content_type=content_type,
                        body=body_text,
                    )
                    unique_jobs: list[DiscoveredJobInput] = []
                    for job in jobs:
                        canonical_url = self._canonicalize_url(job.source_url)
                        key = (
                            job.title.casefold(),
                            job.company_name.casefold(),
                            canonical_url,
                        )
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        # fetch yöntemini kaydedelim (debug için)
                        md = dict(job.metadata or {})
                        md["_fetch_method"] = fetch_method
                        md["_fetch_status"] = status_code or None
                        object.__setattr__(job, "metadata", md)
                        unique_jobs.append(job)
                        discovered.append(job)
                        if len(discovered) >= max_jobs:
                            break
                    base_note = self._build_verification_note(
                        source_platform, len(unique_jobs)
                    )
                    if fetch_method != "httpx":
                        extra_note = f" [fetch={fetch_method}]"
                    reports.append(
                        DiscoverySourceReport(
                            source_url=source_url,
                            source_platform=source_platform,
                            fetched_jobs=len(unique_jobs),
                            verification_note=f"{base_note}{extra_note}",
                        )
                    )
                except Exception as exc:
                    if fetch_method != "httpx":
                        extra_note = f" [fetch={fetch_method}]"
                    reports.append(
                        DiscoverySourceReport(
                            source_url=source_url,
                            source_platform=source_platform,
                            status="failed",
                            verification_note=self._build_verification_note(
                                source_platform, 0
                            )
                            + extra_note,
                            error_message=str(exc)
                            + (
                                f" [http={status_code}]"
                                if status_code and status_code >= 400
                                else ""
                            ),
                        )
                    )
                if len(discovered) >= max_jobs:
                    break
        finally:
            # 🔒 HAVUZ KAPAT: storage_state TEK SEFER kaydet, browser/context kapat, pw manager __exit__
            self.close_playwright_pool()
            if pw_ctx is not None:
                try:
                    pw_ctx.__exit__(None, None, None)
                except Exception:
                    logging.exception("BLE001 discovery suppressed deep exception")
            self._pw = None

        return discovered[:max_jobs], reports

    def _extract_jobs(
        self, source_url: str, content_type: str, body: str
    ) -> list[DiscoveredJobInput]:
        normalized_content_type = content_type.casefold()
        body_stripped = body.lstrip()

        if "json" in normalized_content_type or body_stripped.startswith(("{", "[")):
            parsed = json.loads(body)
            return self._extract_from_json(parsed, source_url)
        if any(
            marker in normalized_content_type for marker in ("xml", "rss", "atom")
        ) or body_stripped.startswith("<"):
            rss_jobs = self._extract_from_feed(body, source_url)
            if rss_jobs:
                return rss_jobs
            html_jobs = self._extract_from_json_ld(body, source_url)
            if html_jobs:
                return html_jobs
        return self._extract_from_html(body, source_url)

    def _extract_from_feed(
        self, body: str, source_url: str
    ) -> list[DiscoveredJobInput]:
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            return []

        items = root.findall(".//item")
        if not items:
            items = root.findall(".//{*}entry")

        jobs: list[DiscoveredJobInput] = []
        for item in items:
            title = self._find_xml_text(item, ["title"])
            link = self._find_xml_text(item, ["link"])
            if not link:
                link = self._find_xml_attribute(item, "link", "href")
            description = self._find_xml_text(
                item, ["description", "summary", "content"]
            )
            if not title or not link:
                continue
            jobs.append(
                self._build_job(
                    title=title,
                    company_name=self._guess_company_name(source_url),
                    source_url=link,
                    location="",
                    raw_text=description or title,
                    metadata={
                        "discovery_source_url": source_url,
                        "published_at": self._coerce_optional_datetime(
                            self._find_xml_text(
                                item, ["pubDate", "published", "updated"]
                            )
                        ),
                        "is_active": True,
                    },
                )
            )
        return jobs

    def _extract_from_json(
        self, payload: object, source_url: str
    ) -> list[DiscoveredJobInput]:
        if isinstance(payload, dict):
            if isinstance(payload.get("jobs"), list):
                return self._extract_greenhouse_jobs(payload["jobs"], source_url)
            if isinstance(payload.get("items"), list):
                return self._extract_lever_jobs(payload["items"], source_url)
            if isinstance(payload.get("results"), list):
                return self._extract_generic_json_jobs(payload["results"], source_url)
        if isinstance(payload, list):
            return self._extract_lever_jobs(payload, source_url)
        return []

    def _extract_greenhouse_jobs(
        self, jobs: list[object], source_url: str
    ) -> list[DiscoveredJobInput]:
        records: list[DiscoveredJobInput] = []
        for item in jobs:
            if not isinstance(item, dict):
                continue
            title = self._coerce_text(item.get("title"))
            source_link = self._coerce_text(item.get("absolute_url") or item.get("url"))
            location = self._coerce_text((item.get("location") or {}).get("name"))
            content = self._coerce_text(item.get("content"))
            if not title or not source_link:
                continue
            records.append(
                self._build_job(
                    title=title,
                    company_name=self._guess_company_name(source_url),
                    source_url=source_link,
                    location=location,
                    raw_text=content or title,
                    source_platform=self._infer_source_platform(
                        source_link or source_url
                    ),
                    metadata={
                        "discovery_source_url": source_url,
                        "position_type": "full-time",
                        "published_at": self._coerce_optional_datetime(
                            item.get("updated_at")
                        ),
                        "is_active": True,
                    },
                )
            )
        return records

    def _extract_lever_jobs(
        self, jobs: list[object], source_url: str
    ) -> list[DiscoveredJobInput]:
        records: list[DiscoveredJobInput] = []
        for _raw_item in jobs:
            if not isinstance(_raw_item, dict):
                continue
            item: dict[str, Any] = _raw_item
            title = self._coerce_text(item.get("text") or item.get("title"))
            source_link = self._coerce_text(
                item.get("hostedUrl") or item.get("applyUrl") or item.get("url")
            )
            categories: dict[str, Any] = (
                item.get("categories")  # type: ignore[assignment]
                if isinstance(item.get("categories"), dict)
                else {}
            )
            location = self._coerce_text(
                categories.get("location") or item.get("location")
            )
            description = self._coerce_text(
                item.get("descriptionPlain") or item.get("description")
            )
            if not title or not source_link:
                continue
            records.append(
                self._build_job(
                    title=title,
                    company_name=self._guess_company_name(source_url),
                    source_url=source_link,
                    location=location,
                    raw_text=description or title,
                    source_platform=self._infer_source_platform(
                        source_link or source_url
                    ),
                    metadata={
                        "discovery_source_url": source_url,
                        "position_type": self._coerce_text(categories.get("commitment"))
                        or "full-time",
                        "published_at": self._coerce_optional_datetime(
                            item.get("createdAt")
                        ),
                        "is_active": True,
                    },
                )
            )
        return records

    def _extract_generic_json_jobs(
        self, jobs: list[object], source_url: str
    ) -> list[DiscoveredJobInput]:
        records: list[DiscoveredJobInput] = []
        for item in jobs:
            if not isinstance(item, dict):
                continue
            title = self._coerce_text(item.get("title") or item.get("name"))
            source_link = self._coerce_text(item.get("url") or item.get("link"))
            location = self._coerce_text(item.get("location"))
            description = self._coerce_text(
                item.get("description") or item.get("summary")
            )
            if not title or not source_link:
                continue
            records.append(
                self._build_job(
                    title=title,
                    company_name=self._coerce_text(item.get("company_name"))
                    or self._guess_company_name(source_url),
                    source_url=source_link,
                    location=location,
                    raw_text=description or title,
                    source_platform=self._infer_source_platform(
                        source_link or source_url
                    ),
                    metadata={
                        "discovery_source_url": source_url,
                        "published_at": self._coerce_optional_datetime(
                            item.get("published_at")
                            or item.get("date_posted")
                            or item.get("created_at")
                        ),
                        "is_active": bool(item.get("active", True)),
                    },
                )
            )
        return records

    def _extract_from_json_ld(
        self, body: str, source_url: str
    ) -> list[DiscoveredJobInput]:
        pattern = re.compile(
            r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(?P<body>.*?)</script>",
            re.IGNORECASE | re.DOTALL,
        )
        records: list[DiscoveredJobInput] = []
        for match in pattern.finditer(body):
            script_body = unescape(match.group("body")).strip()
            if not script_body:
                continue
            try:
                payload = json.loads(script_body)
            except json.JSONDecodeError:
                continue
            for _raw_item in self._flatten_json_ld(payload):
                if not isinstance(_raw_item, dict):
                    continue
                item: dict[str, Any] = _raw_item
                item_type = self._coerce_text(item.get("@type"))
                if item_type.casefold() != "jobposting":
                    continue
                title = self._coerce_text(item.get("title"))
                description = self._coerce_text(item.get("description"))
                hiring_org: dict[str, Any] = (
                    item.get("hiringOrganization")  # type: ignore[assignment]
                    if isinstance(item.get("hiringOrganization"), dict)
                    else {}
                )
                company_name = self._coerce_text(
                    hiring_org.get("name")
                ) or self._guess_company_name(source_url)
                job_location: dict[str, Any] = (
                    item.get("jobLocation")  # type: ignore[assignment]
                    if isinstance(item.get("jobLocation"), dict)
                    else {}
                )
                _jla = job_location.get("address")
                address: dict[str, Any] = _jla if isinstance(_jla, dict) else {}
                location = self._coerce_text(
                    address.get("addressLocality") or address.get("addressCountry")
                )
                source_link = self._coerce_text(item.get("url")) or source_url
                if not title:
                    continue
                published_at = self._coerce_optional_datetime(item.get("datePosted"))
                expires_at = self._coerce_optional_datetime(item.get("validThrough"))
                records.append(
                    self._build_job(
                        title=title,
                        company_name=company_name,
                        source_url=source_link,
                        location=location,
                        raw_text=description or title,
                        source_platform=self._infer_source_platform(
                            source_link or source_url
                        ),
                        metadata={
                            "discovery_source_url": source_url,
                            "published_at": published_at,
                            "expires_at": expires_at,
                            "position_type": self._coerce_text(
                                item.get("employmentType")
                            )
                            or "full-time",
                            "is_active": (expires_at is None)
                            or (
                                isinstance(expires_at, datetime)
                                and expires_at >= datetime.now(timezone.utc)
                            ),
                        },
                    )
                )
        return records

    def _extract_from_html(
        self, body: str, source_url: str
    ) -> list[DiscoveredJobInput]:
        host = urlparse(source_url).netloc.casefold()
        if "linkedin." in host:
            return self._extract_linkedin_jobs(body, source_url)
        if "kariyer.net" in host:
            return self._extract_kariyernet_jobs(body, source_url)
        if "eleman.net" in host:
            return self._extract_elemannet_jobs(body, source_url)
        if "secrethr." in host:
            return self._extract_secrethr_jobs(body, source_url)
        if "yenibiris." in host:
            return self._extract_yenibiris_jobs(body, source_url)
        if "jobturk." in host or "jobturkiye" in host:
            return self._extract_jobturk_jobs(body, source_url)
        return self._extract_generic_jobs(body, source_url)

    def _extract_generic_jobs(
        self, body: str, source_url: str
    ) -> list[DiscoveredJobInput]:
        """Fallback: 4 yaygın kart formatından herhangi birini dene (3. parti siteler için)."""
        for fn in (
            self._extract_elemannet_jobs,
            self._extract_secrethr_jobs,
            self._extract_yenibiris_jobs,
            self._extract_jobturk_jobs,
            self._extract_linkedin_jobs,
        ):
            try:
                results = fn(body, source_url)
                if results:
                    # platform override: company_page (bilinmiyor)
                    for job in results:
                        object.__setattr__(
                            job, "source_platform", JobSourcePlatform.company_page
                        )
                    return results
            except Exception:
                continue
        return []

    # ===== Eleman.net =====
    def _extract_elemannet_jobs(
        self, body: str, source_url: str
    ) -> list[DiscoveredJobInput]:
        records: list[DiscoveredJobInput] = []
        # Yaygın eleman.net kart kalıpları: li.card, .job-item, .list-item, data-* attr
        pats = [
            re.compile(
                r'<li[^>]*class="[^"]*(?:job-item|list-item|jobCard|card-item)[^"]*"[^>]*>(?P<card>.*?)</li>',
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r'<div[^>]*class="[^"]*(?:job-card|card|jobListItem)[^"]*"[^>]*>(?P<card>.*?)</div>',
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r'<article[^>]*class="[^"]*(?:card|job)[^"]*"[^>]*>(?P<card>.*?)</article>',
                re.IGNORECASE | re.DOTALL,
            ),
        ]
        seen: set[Any] = set()
        for pat in pats:
            for m in pat.finditer(body):
                card = m.group("card")
                href = self._match_first(
                    card, r'href="(?P<value>https?://[^"]+)"'
                ) or self._match_first(card, r'href="(?P<value>/[^"]+)"')
                title = self._strip_html(
                    self._match_first(
                        card,
                        r'(?:class|data-title)="[^"]*(?:title|jobTitle|position)[^"]*"[^>]*>(?P<value>.*?)</',
                    )
                    or self._match_first(card, r"<h[1-5][^>]*>(?P<value>.*?)</h[1-5]>")
                    or self._match_first(card, r'title="(?P<value>[^"]{5,100})"')
                )
                company_name = self._strip_html(
                    self._match_first(
                        card,
                        r'(?:class|data-company)="[^"]*(?:companyName|company|firma)[^"]*"[^>]*>(?P<value>.*?)</',
                    )
                    or self._match_first(
                        card,
                        r'<(?:span|div|p)[^>]*class="[^"]*(?:company|firma)[^"]*"[^>]*>(?P<value>.*?)</',
                    )
                )
                location = self._strip_html(
                    self._match_first(
                        card,
                        r'(?:class|data-location)="[^"]*(?:location|sehir|konum|lokasyon)[^"]*"[^>]*>(?P<value>.*?)</',
                    )
                    or self._match_first(
                        card,
                        r'<(?:span|div)[^>]*class="[^"]*(?:location|city|konum|yer)[^"]*"[^>]*>(?P<value>.*?)</',
                    )
                )
                if not title or len(title) < 3:
                    continue
                if href and href.startswith("/"):
                    href = f"https://{urlparse(source_url).netloc}{href}"
                key = (
                    title[:80].casefold(),
                    (company_name or "")[:50].casefold(),
                    href or "",
                )
                if key in seen:
                    continue
                seen.add(key)
                published_label = self._strip_html(
                    self._match_first(
                        card,
                        r'<(?:span|time)[^>]*class="[^"]*(?:date|tarih|published|time)[^"]*"[^>]*>(?P<value>.*?)</',
                    )
                )
                records.append(
                    self._build_job(
                        title=title,
                        company_name=company_name
                        or self._guess_company_name(href or source_url),
                        source_url=href or source_url,
                        location=location or "",
                        raw_text=f"{title}\n{company_name}\n{location}",
                        source_platform=JobSourcePlatform.eleman_net,
                        metadata={
                            "discovery_source_url": source_url,
                            "published_label": published_label or None,
                        },
                    )
                )
            if records:
                break
        return records

    # ===== SecretHR =====
    def _extract_secrethr_jobs(
        self, body: str, source_url: str
    ) -> list[DiscoveredJobInput]:
        records: list[DiscoveredJobInput] = []
        pats = [
            re.compile(
                r'<(?:div|li|article)[^>]*class="[^"]*(?:vacancy|job|position|ilan)[^"]*"[^>]*>(?P<card>.*?)</(?:div|li|article)>',
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(r"<tr[^>]*>(?P<card>.*?)</tr>", re.IGNORECASE | re.DOTALL),
        ]
        seen: set[Any] = set()
        for pat in pats:
            for m in pat.finditer(body):
                card = m.group("card")
                href = self._match_first(
                    card, r'href="(?P<value>https?://[^"]+)"'
                ) or self._match_first(card, r'href="(?P<value>/[^"]+)"')
                title = self._strip_html(
                    self._match_first(
                        card,
                        r"<(?:h[1-5]|a)[^>]*>(?P<value>[^<]{5,160})</(?:h[1-5]|a)>",
                    )
                    or self._match_first(card, r'title="(?P<value>[^"]{5,120})"')
                )
                company_name = self._strip_html(
                    self._match_first(
                        card,
                        r'<(?:td|span|div)[^>]*class="[^"]*(?:company|firma)[^"]*"[^>]*>(?P<value>.*?)</',
                    )
                )
                _loc_m = re.search(
                    r"(?:İstanbul|Ankara|İzmir|Bursa|Antalya|Adana|Konya|Kocaeli|Samsun|Türkiye|Remote|Hibrit|Yarı Zamanlı|Tam Zamanlı)",
                    card or "",
                )
                _loc_fallback = _loc_m.group(0) if _loc_m is not None else ""
                location = self._strip_html(
                    self._match_first(
                        card,
                        r'<(?:td|span|div)[^>]*class="[^"]*(?:location|konum|city|yer|sehir)[^"]*"[^>]*>(?P<value>.*?)</',
                    )
                    or _loc_fallback
                )
                if not title or len(title) < 5:
                    continue
                if href and href.startswith("/"):
                    href = f"https://{urlparse(source_url).netloc}{href}"
                key = (
                    title[:80].casefold(),
                    (company_name or "")[:50].casefold(),
                    href or "",
                )
                if key in seen:
                    continue
                seen.add(key)
                # Gereksiz HTML/bozuk metinlerden kaç
                if len(title) > 150 or "<" in title:
                    continue
                records.append(
                    self._build_job(
                        title=title,
                        company_name=company_name
                        or self._guess_company_name(href or source_url),
                        source_url=href or source_url,
                        location=location or "",
                        raw_text=f"{title}\n{company_name}\n{location}",
                        source_platform=JobSourcePlatform.secrethr,
                        metadata={"discovery_source_url": source_url},
                    )
                )
            if records:
                break
        return records

    # ===== Yenibiris =====
    def _extract_yenibiris_jobs(
        self, body: str, source_url: str
    ) -> list[DiscoveredJobInput]:
        records: list[DiscoveredJobInput] = []
        pats = [
            re.compile(
                r'<(?:div|article)[^>]*class="[^"]*(?:job-detail|job-list|list-item|ilan-item|card)[^"]*"[^>]*>(?P<card>.*?)</(?:div|article)>',
                re.IGNORECASE | re.DOTALL,
            ),
        ]
        seen: set[Any] = set()
        for pat in pats:
            for m in pat.finditer(body):
                card = m.group("card")
                href = self._match_first(
                    card, r'href="(?P<value>https?://[^"]+)"'
                ) or self._match_first(card, r'href="(?P<value>/[^"]+)"')
                title = self._strip_html(
                    self._match_first(
                        card,
                        r"<(?:h[1-5]|a)[^>]*>(?P<value>[^<]{4,160})</(?:h[1-5]|a)>",
                    )
                    or self._match_first(
                        card, r'data-job-title="(?P<value>[^"]{4,120})"'
                    )
                )
                company_name = self._strip_html(
                    self._match_first(
                        card, r'(?:data-company|data-firma)="(?P<value>[^"]{3,80})"'
                    )
                    or self._match_first(
                        card,
                        r'<(?:span|div)[^>]*class="[^"]*(?:company|firma|kurum)[^"]*"[^>]*>(?P<value>.*?)</',
                    )
                )
                location = self._strip_html(
                    self._match_first(
                        card,
                        r'(?:data-location|data-lokasyon|data-konum)="(?P<value>[^"]{2,60})"',
                    )
                    or self._match_first(
                        card,
                        r'<(?:span|div)[^>]*class="[^"]*(?:location|konum|city|yer)[^"]*"[^>]*>(?P<value>.*?)</',
                    )
                )
                if not title or len(title) < 4:
                    continue
                if href and href.startswith("/"):
                    href = f"https://{urlparse(source_url).netloc}{href}"
                key = (
                    title[:80].casefold(),
                    (company_name or "")[:50].casefold(),
                    href or "",
                )
                if key in seen:
                    continue
                if len(title) > 150 or "<" in title:
                    continue
                seen.add(key)
                records.append(
                    self._build_job(
                        title=title,
                        company_name=company_name
                        or self._guess_company_name(href or source_url),
                        source_url=href or source_url,
                        location=location or "",
                        raw_text=f"{title}\n{company_name}\n{location}",
                        source_platform=JobSourcePlatform.yenibiris,
                        metadata={"discovery_source_url": source_url},
                    )
                )
            if records:
                break
        return records

    # ===== JobTürk =====
    def _extract_jobturk_jobs(
        self, body: str, source_url: str
    ) -> list[DiscoveredJobInput]:
        records: list[DiscoveredJobInput] = []
        # Yaygın tablo + grid format
        [
            re.compile(
                r"<(?:tr|li|div)[^>]*[^>]*>(?P<card>.*?)</(?:tr|li|div)>",
                re.IGNORECASE | re.DOTALL,
            ),
        ]
        seen: set[Any] = set()
        # 1. Önce anchor pattern: ilan linklerinden çek (daha güvenilir)
        for am in re.finditer(
            r'<a[^>]*href="(?P<href>(?:https?://[^"]+)?(?:/is|/ilan|/job)[^"]*)"[^>]*>(?P<txt>.*?)</a>',
            body,
            re.IGNORECASE | re.DOTALL,
        ):
            href = am.group("href")
            txt = self._strip_html(am.group("txt"))
            if not txt or len(txt) < 5:
                continue
            if href.startswith("/"):
                href = f"https://{urlparse(source_url).netloc}{href}"
            # Kart 200-1500 char çevresi → şirket+konum ara
            s = max(0, am.start() - 800)
            e = min(len(body), am.end() + 800)
            surrounding = body[s:e]
            company = self._strip_html(
                self._match_first(
                    surrounding,
                    r'<(?:td|span|div)[^>]*class="[^"]*(?:company|firma|kurum)[^"]*"[^>]*>(?P<value>.*?)</',
                )
            )
            loc = self._strip_html(
                self._match_first(
                    surrounding,
                    r'<(?:td|span|div)[^>]*class="[^"]*(?:location|konum|city|yer|sehir)[^"]*"[^>]*>(?P<value>.*?)</',
                )
            )
            key = (txt[:80].casefold(), (company or "")[:50].casefold(), href)
            if key in seen or len(txt) > 150:
                continue
            seen.add(key)
            records.append(
                self._build_job(
                    title=txt,
                    company_name=company or self._guess_company_name(href),
                    source_url=href,
                    location=loc or "",
                    raw_text=f"{txt}\n{company}\n{loc}",
                    source_platform=JobSourcePlatform.jobturk,
                    metadata={"discovery_source_url": source_url},
                )
            )
            if len(records) >= 30:
                break
        return records

    def _extract_linkedin_jobs(
        self, body: str, source_url: str
    ) -> list[DiscoveredJobInput]:
        records: list[DiscoveredJobInput] = []
        # STRATEJİ 2025 LinkedIn Public Search güncellemesi:
        #   - İş URL'leri HTML'de YOK (client-side JS data-entity-urn'den yaratıyor)
        #   - 60x `data-entity-urn="urn:li:jobPosting:<ID>"` match; her match'in 12KB ötesinde
        #     title / company / location class'ları var
        #   - URL MANUAL: `https://www.linkedin.com/jobs/view/{job_id}` şeklinde inşa edilir.
        urn_pat = re.compile(
            r'data-entity-urn="urn:li:jobPosting:(?P<jid>\d{6,})"',
            re.IGNORECASE,
        )
        for match in urn_pat.finditer(body):
            job_id = match.group("jid")
            start = max(0, match.start())
            end = min(len(body), match.end() + 15000)
            neighborhood = body[start:end]
            title = self._strip_html(
                self._match_first(
                    neighborhood,
                    r"base-search-card__title[^>]*>(?P<value>.*?)</",
                )
            )
            company_name = self._strip_html(
                self._match_first(
                    neighborhood,
                    r"hidden-nested-link[^>]*>(?P<value>.*?)</",
                )
                or self._match_first(
                    neighborhood,
                    r"base-search-card__subtitle[^>]*>(?P<value>.*?)</",
                )
            )
            location = self._strip_html(
                self._match_first(
                    neighborhood,
                    r"job-search-card__location[^>]*>(?P<value>.*?)</",
                )
                or self._match_first(
                    neighborhood,
                    r"search-entity-lockup__metadata[^>]*>(?P<value>.*?)</",
                )
            )
            published_at = self._coerce_optional_datetime(
                self._match_first(
                    neighborhood,
                    r"<time[^>]*datetime=\"(?P<value>[^\"]+)\"",
                )
            )
            published_label = self._strip_html(
                self._match_first(
                    neighborhood,
                    r"<time[^>]*>(?P<value>.*?)</time>",
                )
            )
            if not title:
                continue
            source_link = f"https://www.linkedin.com/jobs/view/{job_id}"
            records.append(
                self._build_job(
                    title=title,
                    company_name=company_name or self._guess_company_name(source_link),
                    source_url=source_link,
                    location=location,
                    raw_text=f"{title}\n{company_name}\n{location}",
                    source_platform=JobSourcePlatform.linkedin,
                    metadata={
                        "discovery_source_url": source_url,
                        "published_at": published_at,
                        "published_label": published_label or None,
                        "is_active": True,
                        "linkedin_job_id": job_id,
                    },
                )
            )
            if len(records) >= 120:
                break
        return records

    def _extract_kariyernet_jobs(
        self, body: str, source_url: str
    ) -> list[DiscoveredJobInput]:
        if "/is-ilani/" in urlparse(source_url).path:
            job = self._extract_kariyernet_detail_page(body, source_url)
            return [job] if job else []

        paths = re.findall(r'href="(?P<href>/is-ilani/[^"]+)"', body, re.IGNORECASE)
        links: list[str] = []
        for path in paths:
            absolute_url = urljoin(source_url, path)
            if absolute_url not in links:
                links.append(absolute_url)
        records: list[DiscoveredJobInput] = []
        for detail_url in links[:12]:
            try:
                detail_status, detail_body, _, _detail_fetch = (
                    self._fetch_html_with_fallback(detail_url)
                )
                if detail_status and detail_status >= 400:
                    continue
            except Exception:
                continue
            job = self._extract_kariyernet_detail_page(detail_body, detail_url)
            if job is not None:
                records.append(job)
        return records

    def _extract_kariyernet_detail_page(
        self, body: str, source_url: str
    ) -> DiscoveredJobInput | None:
        title = self._strip_html(
            self._match_first(body, r"<h1[^>]*>(?P<value>.*?)</h1>")
        )
        company_name = self._strip_html(
            self._match_first(
                body,
                r'<a[^>]+href="https://www\.kariyer\.net/firma-profil/[^"]+"[^>]*>(?P<value>.*?)</a>',
            )
        )
        raw_location = self._strip_html(
            self._match_first(body, r"</h1>\s*(?P<value>.*?)\s+İş Yerinde")
            or self._match_first(body, r"</h1>\s*(?P<value>.*?)\s+Hybrid")
        )
        location = self._clean_kariyernet_location(raw_location)
        active = "başvuruları artık kabul etmiyor" not in body.casefold()
        published_label = self._strip_html(
            self._match_first(body, r"(\d+\s+gün önce güncellendi|Yeni)")
        )
        published_at = self._parse_relative_date(published_label)
        description_block = self._match_first(
            body,
            r"##\s+İş İlanı Hakkında(?P<value>.*?)(##\s+Aday Kriterleri|###\s+Şirket Hakkında)",
        )
        raw_text = self._strip_html(description_block or body)
        if not title:
            return None
        return self._build_job(
            title=title,
            company_name=company_name or self._guess_company_name(source_url),
            source_url=source_url,
            location=location,
            raw_text=raw_text,
            source_platform=JobSourcePlatform.kariyernet,
            metadata={
                "discovery_source_url": source_url,
                "published_at": published_at,
                "published_label": published_label or None,
                "is_active": active,
            },
        )

    def _flatten_json_ld(self, payload: object) -> list[object]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("@graph"), list):
            return payload["@graph"]
        return [payload]

    def _build_job(
        self,
        *,
        title: str,
        company_name: str,
        source_url: str,
        location: str,
        raw_text: str,
        source_platform: JobSourcePlatform = JobSourcePlatform.company_page,
        metadata: dict[str, object] | None = None,
    ) -> DiscoveredJobInput:
        normalized_raw_text = self._strip_html(raw_text)
        return DiscoveredJobInput(
            title=title.strip(),
            company_name=company_name.strip() or self._guess_company_name(source_url),
            source_platform=source_platform,
            source_url=self._canonicalize_url(source_url),
            location=location.strip(),
            work_mode=self._infer_work_mode(f"{title}\n{normalized_raw_text}"),
            raw_text=normalized_raw_text[:4000],
            metadata={
                "is_active": True,
                **dict(metadata or {}),
            },
        )

    def _guess_company_name(self, url: str) -> str:
        host = urlparse(url).netloc.casefold()
        host = host.removeprefix("www.")
        if host.startswith("boards-api.greenhouse.io"):
            parts = [part for part in urlparse(url).path.split("/") if part]
            if "boards" in parts:
                board_index = parts.index("boards")
                if len(parts) > board_index + 1:
                    return parts[board_index + 1].replace("-", " ").title()
        if host.endswith("lever.co"):
            parts = [part for part in urlparse(url).path.split("/") if part]
            if parts:
                return parts[0].replace("-", " ").title()
        return host.split(".")[0].replace("-", " ").title() or "Bilinmiyor"

    def _infer_work_mode(self, text: str) -> WorkMode:
        normalized = text.casefold()
        if "remote" in normalized or "uzaktan" in normalized:
            return WorkMode.remote
        if "onsite" in normalized or "office" in normalized or "ofis" in normalized:
            return WorkMode.onsite
        return WorkMode.hybrid

    def _strip_html(self, value: str) -> str:
        no_tags = re.sub(r"<[^>]+>", " ", value)
        return re.sub(r"\s+", " ", unescape(no_tags)).strip()

    _KARIYERNET_LOCATION_NOISE = re.compile(
        r"\b(ios_share|share|Kaydet|Favorilere|Favori|Ekle|Başvur|Başvuruyu|Bildir|Paylaş|Yazdır|"
        r"Gönder|Kopyala|Yorum|Beğen|Takip|Detay|Ayrıntı|İlan|Geri|İleri|Menü|Ekran|Al|Çık|Giriş|"
        r"Yardım|Destek|Hakkında|Şirket|Kurumsal|İrtibat|İletişim)\b",
        re.IGNORECASE,
    )

    def _clean_kariyernet_location(self, raw_value: str) -> str:
        if not raw_value:
            return ""
        cleaned = self._KARIYERNET_LOCATION_NOISE.sub(" ", raw_value)
        cleaned = re.sub(r"\([^)]*\)", "", cleaned)
        cleaned = re.sub(r"[•·|/\\,]+", " ", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        tokens = [t for t in cleaned.split() if len(t) >= 2 and not t.isdigit()]
        if not tokens:
            return raw_value.strip()
        # Birden fazla şehir varsa ilk 2-3'ünü al (genelde şehir + ilçe olur)
        return " ".join(tokens[:3])

    def _canonicalize_url(self, value: str) -> str:
        parsed = urlparse(value.strip())
        cleaned = parsed._replace(query="", fragment="")
        return urlunparse(cleaned)

    def _infer_source_platform(self, url: str) -> JobSourcePlatform:
        host = urlparse(url).netloc.casefold()
        if "linkedin." in host:
            return JobSourcePlatform.linkedin
        if "kariyer.net" in host:
            return JobSourcePlatform.kariyernet
        if "indeed." in host:
            return JobSourcePlatform.indeed
        if "eleman.net" in host or "eleman." in host and "net" in host:
            return JobSourcePlatform.eleman_net
        if "secrethr." in host:
            return JobSourcePlatform.secrethr
        if "yenibiris." in host:
            return JobSourcePlatform.yenibiris
        if "jobturk." in host or "jobturkiye" in host:
            return JobSourcePlatform.jobturk
        return JobSourcePlatform.company_page

    def _build_verification_note(
        self, source_platform: JobSourcePlatform, fetched_jobs: int
    ) -> str:
        if source_platform == JobSourcePlatform.linkedin:
            return (
                "LinkedIn public job URL taraması uygulandı."
                if fetched_jobs
                else "LinkedIn kaynağı denendi; public erişimde sonuç bulunamadı veya sayfa boş döndü."
            )
        if source_platform == JobSourcePlatform.kariyernet:
            return (
                "Kariyer.net public ilan URL taraması uygulandı."
                if fetched_jobs
                else "Kariyer.net kaynağı denendi; erişilebilir ilan kartı bulunamadı."
            )
        if source_platform == JobSourcePlatform.eleman_net:
            return (
                "Eleman.net ilan listesi regex ile parse edildi."
                if fetched_jobs
                else "Eleman.net denendi; ilan kartı / liste öğesi bulunamadı."
            )
        if source_platform == JobSourcePlatform.secrethr:
            return (
                "SecretHR ilan listesi parse edildi."
                if fetched_jobs
                else "SecretHR denendi; eşleşen ilan bulunamadı."
            )
        if source_platform == JobSourcePlatform.yenibiris:
            return (
                "Yenibiris ilan listesi parse edildi."
                if fetched_jobs
                else "Yenibiris denendi; ilan kartı yok."
            )
        if source_platform == JobSourcePlatform.jobturk:
            return (
                "JobTürk ilan listesi parse edildi."
                if fetched_jobs
                else "JobTürk denendi; liste boş veya erişim engeli."
            )
        return (
            "Kaynak başarıyla işlendi."
            if fetched_jobs
            else "Kaynak denendi ancak ilan bulunamadı."
        )

    def _parse_relative_date(self, value: str) -> str | None:
        normalized = value.casefold().strip()
        if not normalized:
            return None
        now = datetime.now(timezone.utc)
        if "new" in normalized or "yeni" in normalized:
            return now.isoformat()
        match = re.search(
            r"(\d+)\s+(hour|hours|day|days|week|weeks|saat|gün|hafta)", normalized
        )
        if not match:
            return None
        amount = int(match.group(1))
        unit = match.group(2)
        if unit in {"hour", "hours", "saat"}:
            return (now - timedelta(hours=amount)).isoformat()
        if unit in {"day", "days", "gün"}:
            return (now - timedelta(days=amount)).isoformat()
        if unit in {"week", "weeks", "hafta"}:
            return (now - timedelta(days=amount * 7)).isoformat()
        return None

    def _coerce_optional_datetime(self, value: object) -> str | None:
        if not value:
            return None
        if isinstance(value, str):
            return self._parse_datetime(value)
        return None

    def _parse_datetime(self, value: str) -> str | None:
        candidate = value.strip()
        if not candidate:
            return None
        try:
            normalized = candidate.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            pass

        parsed_relative = self._parse_relative_date(candidate)
        if parsed_relative:
            return parsed_relative
        return None

    def _match_first(self, value: str, pattern: str) -> str:
        match = re.search(pattern, value, re.IGNORECASE | re.DOTALL)
        if match is None:
            return ""
        group_value = match.groupdict().get("value")
        if group_value is not None:
            return group_value
        return match.group(1) if match.groups() else ""

    def _find_xml_text(self, element: ET.Element, names: list[str]) -> str:
        for child in list(element):
            local_name = child.tag.split("}")[-1]
            if local_name in names and child.text:
                return child.text.strip()
        return ""

    def _find_xml_attribute(
        self, element: ET.Element, tag_name: str, attr_name: str
    ) -> str:
        for child in list(element):
            local_name = child.tag.split("}")[-1]
            if local_name == tag_name and child.attrib.get(attr_name):
                return child.attrib[attr_name].strip()
        return ""

    def _coerce_text(self, value: object) -> str:
        return value.strip() if isinstance(value, str) else ""
