"""Şifreleme yardımcıları (opsiyonel cryptography bağımlılığı).

- Cryptography/Fernet yoksa veya ENCRYPTION_KEY boşsa geriye dönük uyumlu DÜZ METİN döner.
- Environment'taki şifre alanları (ör. SMTP_PASS) `enc:v1:<fernet-token>` formatında ise decrypt edilir.
"""
from __future__ import annotations

import base64
import hashlib
import logging

try:  # opsiyonel — kurulmamışsa plaintext mod
    from cryptography.fernet import Fernet, InvalidToken

    _HAS_FERNET = True
except Exception:  # noqa: BLE001
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore
    _HAS_FERNET = False

_PREFIX = "enc:v1:"
log = logging.getLogger(__name__)


def _password_to_fernet_key(user_key: str) -> bytes:
    """Kullanıcının girdiği rastgele anahtarı 32 byte Fernet key'e çevir (base64 ile)."""
    digest = hashlib.sha256(user_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet(encryption_key: str) -> Fernet | None:
    if not _HAS_FERNET:
        return None
    if not encryption_key:
        return None
    try:
        return Fernet(_password_to_fernet_key(encryption_key))
    except Exception:
        log.exception("crypto: Fernet init başarısız — plaintext fallback")
        return None


def decrypt_env_value(raw: str | None, encryption_key: str) -> str:
    """Env değeri decrypt et:
    - `enc:v1:<token>` → Fernet decrypt
    - diğer → doğrudan dön (geriye dönük uyumlu)
    - None/empty → ""
    """
    if not raw:
        return ""
    s = str(raw).strip()
    if not s.startswith(_PREFIX):
        return s
    f = _get_fernet(encryption_key)
    if f is None:
        log.warning("crypto: Fernet yok/anahtar yok — prefixli şifre düz okunamadı, boş döndü")
        return ""
    token_b64 = s[len(_PREFIX):].strip()
    try:
        return f.decrypt(token_b64.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        log.error("crypto: Fernet decrypt başarısız — yanlış anahtar veya bozuk token")
        return ""
    except Exception:
        log.exception("crypto: decrypt hatası")
        return ""


def encrypt_value(value: str, encryption_key: str) -> str:
    """Düz metni Fernet ile şifrele → `enc:v1:<token>` formatında dön.

    Opsiyonel: kullanıcı production için şifreleri bu fonksiyonla şifreleyip env'e koyabilir.
    Şifreleme yoksa / anahtar boşsa düz metin döner (uyarı ile).
    """
    if not value:
        return ""
    f = _get_fernet(encryption_key)
    if f is None:
        log.warning("crypto: şifreleme atlandı — cryptography kurulmamış veya ENCRYPTION_KEY boş (dev/test)")
        return value
    token = f.encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{_PREFIX}{token}"
