from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from .config import Settings, get_settings


async def verify_api_key(
    x_api_key: Annotated[str | None, Header(description="API anahtarı. API_KEY env boşsa gerekli DEĞİL (dev/test).")] = None,
    settings: Annotated[Settings, Depends(get_settings)] = ...,  # type: ignore[assignment]
) -> bool:
    """API_KEY dolu ise X-API-Key header ile doğrula. Boş ise (dev/test) her isteğe izin ver.

    Usage:
        @router.get("/benim-ozel-endpointim")
        def my_ep(_ok: Annotated[bool, Depends(verify_api_key)]):
            ...
    """
    required = settings.api_key and settings.api_key.strip()
    if not required:
        return True
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header gerekli (Bu sunucu API_KEY ile güvenlik altında).",
        )
    # Güvenli olmayan (sabit zamanlı değil) karşılaştırma ama düşük risk — production JWT'ye geçilecek
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key hatalı.",
        )
    return True
