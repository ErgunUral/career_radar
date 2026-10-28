import html
import json
import os
import pathlib
import sqlite3
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse, unquote

try:
    from zoneinfo import ZoneInfo
    _IST = ZoneInfo("Europe/Istanbul")
except Exception:  # noqa: BLE001
    _IST = None  # type: ignore[assignment]

import httpx
import pandas as pd
import streamlit as st

# ================== CONFIG ==================
API_BASE = "http://127.0.0.1:8000"
DEFAULT_USER = "user-ergun"

_HERE = pathlib.Path(__file__).resolve()
_APPS_DIR = _HERE.parents[1]
_API_DIR = _APPS_DIR / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

from app.core.config import get_settings  # noqa: E402
from _url_utils import add_url_column_to_rows, sanitize_url, safe_html_anchor  # noqa: E402

_SETTINGS = get_settings()
_PARSED = urlparse(_SETTINGS.database_url)
if _PARSED.scheme == "sqlite" and _PARSED.path:
    ROOT_DB = pathlib.Path(unquote(_PARSED.path)).resolve()
else:
    ROOT_DB = (_HERE.parents[2] / "apps" / "api" / "app" / "storage" / "careerradar.db").resolve()

_API_HEADERS: dict[str, str] = {}
if _SETTINGS.api_key:
    _API_HEADERS["X-API-Key"] = _SETTINGS.api_key

st.set_page_config(
    page_title="CareerRadar AI · Dashboard", page_icon="🎯", layout="wide"
)

# ====== GLOBAL CSS (Görsel ipuçları: link rengi, underline, imleç pointer) ======
st.markdown(
    """
<style>
/* Genel link görünümü: mavi, altı çizili, hover'da koyulaşır */
a.job-link,
a.job-link:visited,
a[href*="linkedin.com/jobs/view"],
a[href*="kariyer.net/is-ilan"] {
    color: #1e66c4 !important;
    text-decoration: underline !important;
    text-decoration-color: #6ea8fe !important;
    text-underline-offset: 2px;
    font-weight: 600;
    cursor: pointer !important;
    padding: 0 2px;
    border-radius: 3px;
}
a.job-link:hover,
a[href*="linkedin.com/jobs/view"]:hover,
a[href*="kariyer.net/is-ilan"]:hover {
    color: #0c4a9e !important;
    background-color: #eaf2ff !important;
    text-decoration-color: #1e66c4 !important;
}
/* Streamlit dataframe link sütunu içindeki linkler de aynı görünsün */
[data-testid="stDataFrame"] a {
    color: #1e66c4 !important;
    text-decoration: underline !important;
    font-weight: 600;
    cursor: pointer !important;
}
[data-testid="stDataFrame"] a:hover {
    color: #0c4a9e !important;
    background-color: #eaf2ff !important;
}
/* Bağlantı sütunu ikonu için */
.job-url-col a {
    font-size: 1rem;
}
/* Mobil cihazlar için minimum dokunma alanı: 44x44px (WCAG) */
@media (max-width: 768px) {
    a.job-link,
    [data-testid="stDataFrame"] a {
        display: inline-block !important;
        min-height: 44px !important;
        line-height: 44px !important;
        padding: 0 8px !important;
    }
}
</style>
""",
    unsafe_allow_html=True,
)

st.title("🎯 CareerRadar AI · Kişisel İş Radar Paneli")
st.caption(
    f"Son güncelleme: {datetime.now(tz=_IST).strftime('%d.%m.%Y %H:%M TSİ') if _IST else datetime.now().strftime('%d.%m.%Y %H:%M')}  ·  SQLite: {ROOT_DB}"
)

# Session state defaultları (USER_ID / SMTP Ayarları)
if "USER_ID" not in st.session_state:
    st.session_state.USER_ID = DEFAULT_USER
if "smtp_host" not in st.session_state:
    st.session_state.smtp_host = os.environ.get("SMTP_HOST", "")
if "smtp_port" not in st.session_state:
    try:
        st.session_state.smtp_port = int(os.environ.get("SMTP_PORT", "0") or 0)
    except Exception:
        st.session_state.smtp_port = 0
if "smtp_user" not in st.session_state:
    st.session_state.smtp_user = os.environ.get("SMTP_USER", "")
if "smtp_pass" not in st.session_state:
    st.session_state.smtp_pass = os.environ.get("SMTP_PASS", "")
if "smtp_from" not in st.session_state:
    st.session_state.smtp_from = os.environ.get("SMTP_FROM", "")
if "to_email_test" not in st.session_state:
    st.session_state.to_email_test = st.session_state.smtp_user or "test@ornek.com"

USER_ID = st.session_state.USER_ID


def mark_all_read(user_id: str) -> int:
    """PATCH /api/v1/notifications/read-all → kaç adet okunmuş yapıldı?"""
    try:
        r = httpx.patch(
            f"{API_BASE}/api/v1/notifications/read-all",
            params={"user_id": user_id},
            headers=_API_HEADERS,
            timeout=8,
        )
        if r.status_code == 200:
            return int(r.json().get("marked_read_count", 0))
    except Exception as e:
        st.error(f"Mark-all API hatası: {e}")
    return 0


def mark_one_read(notification_id: str, user_id: str, is_read: bool = True) -> bool:
    """PATCH /notifications/:id/read veya /unread"""
    suffix = "read" if is_read else "unread"
    try:
        r = httpx.patch(
            f"{API_BASE}/api/v1/notifications/{notification_id}/{suffix}",
            params={"user_id": user_id},
            headers=_API_HEADERS,
            timeout=8,
        )
        return r.status_code == 200
    except Exception:
        return False


def delete_watcher(wid: str) -> bool:
    try:
        r = httpx.delete(f"{API_BASE}/api/v1/watchers/{wid}", headers=_API_HEADERS, timeout=8)
        return r.status_code == 200
    except Exception:
        return False


def toggle_watcher_active(wid: str, active: bool) -> bool:
    try:
        r = httpx.patch(
            f"{API_BASE}/api/v1/watchers/{wid}/active",
            params={"is_active": str(bool(active)).lower()},
            headers=_API_HEADERS,
            timeout=8,
        )
        return r.status_code == 200
    except Exception:
        return False


def list_watchers_api() -> list[dict]:
    """GET /api/v1/watchers listesini USER_ID filtresi ile döner (geri kalan herkesi göster fallback)."""
    try:
        r = httpx.get(
            f"{API_BASE}/api/v1/watchers", params={"user_id": USER_ID}, headers=_API_HEADERS, timeout=8
        )
        if r.status_code == 200:
            arr = r.json() or []
            arr_mine = [x for x in arr if str(x.get("user_id")) == str(USER_ID)]
            return arr_mine or arr
    except Exception:
        pass
    return []


def send_test_email(
    host: str, port: int, user: str, pwd: str, sender: str, to_email: str
) -> tuple[bool, str]:
    """SMTP test emaili gönder (frontend tarafında TEST amaçlı) — True/False + mesaj"""
    if not (host and port and user and pwd and to_email):
        return False, "Lütfen tüm SMTP alanlarını + Hedef e-postayı doldurun."
    try:
        import smtplib
        import ssl
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"] = "[CareerRadar AI] ✅ SMTP Test Maili — Başarılı!"
        msg["From"] = sender or user
        msg["To"] = to_email
        msg.set_content(
            f"""Merhaba,\n\nCareerRadar AI SMTP ayarlarınız BAŞARILI 👏:\n  Host: {host}:{port}\n  Kullanıcı: {user}\n  Zaman: {datetime.now(tz=_IST).strftime('%d.%m.%Y %H:%M TSİ') if _IST else datetime.now().strftime('%d.%m.%Y %H:%M')}\n\nArtık yüksek eşleşen ilanlar size bu adresten gönderilecektir.\n\n-- CareerRadar AI · Kişisel İş Radar Paneli"""
        )
        ctx = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=20) as s:
                s.login(user, pwd)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.ehlo()
                try:
                    s.starttls(context=ctx)
                    s.ehlo()
                except Exception:
                    pass
                s.login(user, pwd)
                s.send_message(msg)
        return (
            True,
            f"✅ Test emaili gönderildi! Lütfen {to_email} adresini (Spam klasörü dahil) kontrol edin.",
        )
    except Exception as e:
        return False, f"❌ SMTP hatası: {type(e).__name__}: {e}"


# ================== API/SQLite DATA ==================
@st.cache_data(ttl=300)
def load_data(user_id: str):
    rows = []
    status = {}
    notifications = []
    try:
        # Scheduler status
        r = httpx.get(f"{API_BASE}/api/v1/scheduler/status", headers=_API_HEADERS, timeout=4)
        status = r.json() if r.status_code == 200 else {}
    except Exception:
        status = {
            "error": "API çalışmıyor (localhost:8000) — Veriler doğrudan SQLite'dan okunuyor"
        }
    try:
        # Direct SQLite: job_archive + notifications
        if ROOT_DB.exists():
            conn = sqlite3.connect(ROOT_DB)
            c = conn.cursor()
            c.execute("""
              SELECT id, title, company_name, location, source_platform,
                     last_match_score, last_recommendation, last_seen_at,
                     job_id, watcher_id, metadata
              FROM job_archive ORDER BY id DESC LIMIT 250
            """)
            cols = [d[0] for d in c.description]
            for r in c.fetchall():
                d = dict(zip(cols, r, strict=False))
                rows.append(d)
            # Her satıra apply_url ekle
            add_url_column_to_rows(rows, conn=conn)
            # Notif URL map: (job_id, watcher_id) -> apply_url (bildirimlere URL eklemek için)
            url_by_jobid = {}
            url_by_archive_id = {}
            for r in rows:
                jid = str(r.get("job_id") or "")
                if jid and jid not in url_by_jobid:
                    url_by_jobid[jid] = r.get("apply_url", "")
                if isinstance(r.get("id"), int) and r["id"] not in url_by_archive_id:
                    url_by_archive_id[r["id"]] = r.get("apply_url", "")
            c.execute("""
              SELECT id, user_id, watcher_id, job_id, channel, title, message, created_at, is_read
              FROM notifications ORDER BY id DESC LIMIT 100
            """)
            cols_n = [d[0] for d in c.description]
            for r in c.fetchall():
                n = dict(zip(cols_n, r, strict=False))
                # Bildirime apply_url ekle
                jid = str(n.get("job_id") or "")
                n["apply_url"] = url_by_jobid.get(jid, "")
                notifications.append(n)
            conn.close()
    except Exception as e:
        st.error(f"DB okuma hatası: {e}")
    return rows, status, notifications


rows, status, notifications = load_data(USER_ID)
df = (
    pd.DataFrame(rows)
    if rows
    else pd.DataFrame(
        columns=[
            "id",
            "title",
            "company_name",
            "location",
            "source_platform",
            "last_match_score",
            "last_recommendation",
            "last_seen_at",
            "job_id",
            "watcher_id",
        ]
    )
)

# ================== 4 ANA SEKME ==================
tab_dash, tab_watch, tab_profile, tab_settings = st.tabs(
    [
        "📊 Dashboard (İlanlar + Filtreler)",
        "👀 Watcher Yönetimi (List / Oluştur / Sil)",
        "👤 Aday Profili (CV + Yetenekler)",
        "⚙️ Ayarlar (Kullanıcı + SMTP + Bildirim)",
    ]
)

# ============================================================
# 📊 SEKME 1 · DASHBOARD
# ============================================================
with tab_dash:
    # ================== KPI CARDS ==================
    c1, c2, c3, c4, c5 = st.columns(5)
    total_archive = len(df)
    avg_score = round(df["last_match_score"].mean(), 2) if total_archive else 0.0
    high_match = len(df[df["last_match_score"] >= 65]) if total_archive else 0
    new_notif = len([n for n in notifications if not n.get("is_read")])
    next_run = (
        status.get("jobs", [{}])[0].get("next_run_time") if status.get("jobs") else "—"
    )
    if next_run and isinstance(next_run, str) and next_run.endswith("+00:00"):
        try:
            if _IST:
                next_run_dt = datetime.fromisoformat(next_run).replace(tzinfo=timezone.utc).astimezone(_IST)
                next_run = next_run_dt.strftime("%d.%m.%Y %H:%M TSİ")
            else:
                next_run = datetime.fromisoformat(next_run).strftime("%d.%m.%Y %H:%M")
        except Exception:
            pass
    c1.metric("📦 Arşivdeki İlan", f"{total_archive}")
    c2.metric("📊 Ortalama Skor", f"{avg_score}")
    c3.metric("🏆 Yüksek Skor (≥65)", f"{high_match}")
    c4.metric("🔔 Okunmamış Bildirim", f"{new_notif}")
    c5.metric("⏱️ Sonraki Scan", f"{next_run}", delta_color="off")

    # ================== SCHEDULER DURUMU ==================
    with st.expander("⏱️ Scheduler Durumu (120dk interval)", expanded=False):
        st.json(status)
        col1, col2, col3 = st.columns(3)
        if col1.button("▶️ Manuel Run (Tüm Watcherlar)"):
            try:
                r = httpx.post(f"{API_BASE}/api/v1/scheduler/run", headers=_API_HEADERS, timeout=120)
                st.success(
                    f"Sonuç: {r.status_code} — {json.dumps(r.json(), ensure_ascii=False)[:300]}"
                )
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Run hatası: {e}")
        if col2.button("🔄 API Yenile"):
            st.cache_data.clear()
            st.rerun()

    # ================== FİLTRELER ==================
    if total_archive:
        st.markdown("### 🎛️ Filtreler")
        f1, f2, f3, f4 = st.columns(4)
        with f1:
            min_score = st.slider(
                "Min. Skor",
                float(df.last_match_score.min()),
                float(df.last_match_score.max()),
                float(df.last_match_score.min()),
            )
        with f2:
            plats = ["Tümü"] + sorted(list(df.source_platform.dropna().unique()))
            plat = st.selectbox("Platform", plats)
        with f3:
            recs = ["Tümü"] + sorted(list(df.last_recommendation.dropna().unique()))
            rec = st.selectbox("Öneri", recs)
        with f4:
            search = st.text_input("🔎 Şirket / Başlık Ara", value="")

        q = df[df.last_match_score >= min_score]
        if plat != "Tümü":
            q = q[q.source_platform == plat]
        if rec != "Tümü":
            q = q[q.last_recommendation == rec]
        if search.strip():
            q = q[
                q.apply(
                    lambda r: (
                        search.casefold() in str(r.title).casefold()
                        or search.casefold() in str(r.company_name).casefold()
                    ),
                    axis=1,
                )
            ]

        # ================== SKOR HISTOGRAM ==================
        st.markdown("### 📊 Skor Dağılımı")
        bins = [0, 50, 55, 60, 62, 65, 68, 70, 75, 80, 100]
        labels = [
            "0-50",
            "50-55",
            "55-60",
            "60-62",
            "62-65",
            "65-68",
            "68-70",
            "70-75",
            "75-80",
            "80+",
        ]
        q["_b"] = pd.cut(q.last_match_score, bins=bins, labels=labels)
        st.bar_chart(q["_b"].value_counts().sort_index(), use_container_width=True)

        # ================== ARŞİV TABLOSU ==================
        st.markdown(f"### 📋 Eşleşen İlanlar ({len(q)} adet)")
        tbl_cols = [
            "last_match_score",
            "last_recommendation",
            "source_platform",
            "apply_url",
            "title",
            "company_name",
            "location",
            "last_seen_at",
        ]
        q_show = (
            q[tbl_cols].sort_values("last_match_score", ascending=False).copy()
        )
        renames = {
            "last_match_score": "⭐ Skor",
            "last_recommendation": "🎯 Öneri",
            "source_platform": "🌐 Platform",
            "apply_url": "🔗 İlan Linki",
            "title": "📌 Başlık",
            "company_name": "🏢 Şirket",
            "location": "📍 Konum",
            "last_seen_at": "🕒 Son Görülme",
        }
        q_show = q_show.rename(columns=renames)
        display_cols = [
            "⭐ Skor",
            "🎯 Öneri",
            "🌐 Platform",
            "📌 Başlık",
            "🔗 İlan Linki",
            "🏢 Şirket",
            "📍 Konum",
            "🕒 Son Görülme",
        ]
        st.dataframe(
            q_show[display_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "⭐ Skor": st.column_config.NumberColumn(format="%.1f", width="small"),
                "🎯 Öneri": st.column_config.TextColumn(width="medium"),
                "🌐 Platform": st.column_config.TextColumn(width="medium"),
                "📌 Başlık": st.column_config.TextColumn(width="large"),
                "🔗 İlan Linki": st.column_config.LinkColumn(
                    display_text="🔗 İlanı Aç",
                    width="small",
                    help="İlanın orijinal detay sayfasına git (LinkedIn/KariyerNET) — yeni sekmede açılır.",
                    disabled=False,
                ),
                "🏢 Şirket": st.column_config.TextColumn(width="medium"),
                "📍 Konum": st.column_config.TextColumn(width="medium"),
                "🕒 Son Görülme": st.column_config.TextColumn(width="medium"),
            },
            height=580,
        )
        # Başlık → link mapping: Her ilan başlığı yanına markdown link olarak ek göster
        # (Kullanıcı başlığa değil yanındaki 🔗 ya da aşağıdaki ayrı listeye tıklar)
        if not q_show.empty:
            with st.expander("🔗 📋 Başlık Listesi — Doğrudan Tıklanabilir (Tüm İlanlar)", expanded=True):
                st.caption(
                    "Aşağıdaki mavi, altı çizili bağlantılara tıklayarak ilanların detay sayfasına doğrudan gidebilirsiniz "
                    "(LinkedIn / KariyerNET — yeni tarayıcı sekmesinde açılır)."
                )
                items = []
                for _, r in q_show[["📌 Başlık", "🏢 Şirket", "⭐ Skor", "🔗 İlan Linki", "🌐 Platform"]].iterrows():
                    baslik = str(r["📌 Başlık"]).strip() or "İlan Detayı"
                    sirket = str(r["🏢 Şirket"]).strip() or ""
                    skor = f"{float(r['⭐ Skor']):.1f}" if isinstance(r["⭐ Skor"], (int, float)) else "-"
                    url = str(r["🔗 İlan Linki"]).strip()
                    plat = str(r["🌐 Platform"]).strip() or ""
                    if url:
                        safe_anchor = safe_html_anchor(url, baslik)
                        skor_esc = html.escape(str(skor), quote=True)
                        sirket_esc = html.escape(str(sirket), quote=False)
                        plat_esc = html.escape(str(plat), quote=False)
                        items.append(
                            f'<div style="margin: 4px 0; padding: 6px 8px; border-radius: 6px; '
                            f'background: linear-gradient(90deg, #f8fbff 0%, #ffffff 100%); '
                            f'border: 1px solid #e4edf8;">'
                            f'<span style="color:#888; font-size:12px; margin-right:8px;">[%{skor_esc}]</span>'
                            f'{safe_anchor}'
                            f' <span style="color:#666; font-size:12px; margin: 0 4px;">· {sirket_esc}</span>'
                            f' <span style="color:#999; font-size:11px; float:right;">{plat_esc}</span>'
                            f'</div>'
                        )
                if items:
                    st.markdown(
                        "\n".join(items[:120]),
                        unsafe_allow_html=True,
                    )

        # ================== BİLDİRİMLER ==================
        if notifications:
            st.markdown(f"### 🔔 Bildirimler ({len(notifications)})")
            ndf = pd.DataFrame(notifications)
            ndf["_is_read_str"] = ndf["is_read"].map(
                lambda v: "✅ Okundu" if v else "🔴 Okunmadı"
            )
            # Kullanıcıya ait olanları filtrele
            ndf_user = (
                ndf[ndf["user_id"] == USER_ID].copy()
                if "user_id" in ndf.columns
                else ndf.copy()
            )
            ndf_show = (
                ndf_user if len(ndf_user) > 0 else ndf
            )  # user_id eşleşme yoksa tümünü göster (backward uyum)
            st.info(
                f"Toplam {len(ndf_show)} bildirim listeleniyor (filtre: user_id={USER_ID}). Okunmamış: {sum(1 for _r in ndf_show.itertuples() if not _r.is_read)}"
            )

            # Tabloyu göster (ID görünür, satır seçme ile tekil okundu)
            tbl_cols_n = [
                "id",
                "_is_read_str",
                "created_at",
                "channel",
                "title",
                "message",
                "apply_url",
            ]
            # created_at kolonu TSİ formatla (varsa)
            if "created_at" in ndf_show.columns and len(ndf_show) > 0 and _IST:
                def _fmt_ts(s: object) -> str:
                    try:
                        s_str = str(s)
                        dt = datetime.fromisoformat(s_str).astimezone(_IST)
                        return dt.strftime("%d.%m.%Y %H:%M TSİ")
                    except Exception:
                        return s_str if isinstance(s, str) else str(s)
                ndf_show = ndf_show.copy()
                ndf_show["created_at"] = ndf_show["created_at"].apply(_fmt_ts)
            st.dataframe(
                ndf_show[tbl_cols_n].rename(
                    columns={
                        "id": "🆔 Bildirim ID",
                        "_is_read_str": "👀 Durum",
                        "created_at": "📅 Oluşturulma",
                        "channel": "🔗 Kanal",
                        "title": "📌 Başlık",
                        "message": "📝 Mesaj",
                        "apply_url": "🔗 İlan Linki",
                    }
                ),
                use_container_width=True,
                height=320,
                hide_index=True,
                column_config={
                    "🆔 Bildirim ID": st.column_config.TextColumn(width="small"),
                    "🔗 İlan Linki": st.column_config.LinkColumn(
                        display_text="🔗 Aç",
                        width="small",
                        help="Bildirime karşılık gelen ilan orijinal detay sayfası",
                    ),
                },
            )
            # Tekil okundu butonları (en eski 9 okunmamış)
            unread_list = [
                n for n in ndf_show.to_dict("records") if not n.get("is_read")
            ]
            if unread_list:
                st.markdown(
                    "#### 📌 Okunmamış Bildirimler — Tekil Okundu İşaretle + İlan Linki:"
                )
                per_row = 2
                for chunk in [
                    unread_list[i : i + per_row]
                    for i in range(0, min(len(unread_list), 10), per_row)
                ]:
                    cols_row = st.columns(per_row)
                    for cc, item in zip(cols_row, chunk, strict=False):
                        short_title = (item.get("title") or "")[:48]
                        apply_url = item.get("apply_url") or ""
                        lbl = f"✅ OKUNDU: {short_title}"
                        # 2 sütun: Sol OKUNDU butonu, Sağ 🔗 link
                        c1, c2 = cc.columns([3, 1])
                        if c1.button(lbl, key=f"mrk_{item.get('id')}"):
                            if mark_one_read(str(item.get("id")), USER_ID, True):
                                cc.success("İşaretlendi!")
                                st.cache_data.clear()
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                cc.error("İşaretleme başarısız (ID hatalı / API yok)")
                        if apply_url:
                            c2.markdown(
                                safe_html_anchor(apply_url, "🔗 İlanı Aç"),
                                unsafe_allow_html=True,
                            )
    else:
        st.warning(
            "Arşivde henüz ilan yok — '⏱️ Scheduler Durumu' içinden ▶️ Manuel Run tuşuna basın veya 120dk bekleyin."
        )


# ============================================================
# 👀 SEKME 2 · WATCHER YÖNETİMİ
# ============================================================
with tab_watch:
    st.markdown("## 👀 Watcher (İzleyici) Yönetimi")
    watchers = list_watchers_api()
    st.caption(
        f"Kullanıcı: **{USER_ID}** · API'den dönen watcher sayısı: **{len(watchers)}**"
    )

    # ------ WATCHER LİSTESİ ------
    st.subheader("📋 Mevcut Watcherlar")
    if watchers:
        wlist = []
        for w in watchers:
            sc = w.get("search_criteria") or {}
            cp = w.get("candidate_profile") or {}
            wlist.append(
                {
                    "id": w.get("id", "")[:12],
                    "query_name": w.get("query_name", ""),
                    "platform": str(w.get("source_platform")),
                    "keywords": ", ".join(sc.get("keywords") or [])[:60] if sc else "",
                    "locations": ", ".join(sc.get("locations") or [])[:60]
                    if sc
                    else "",
                    "min_score": w.get("minimum_match_score", 0),
                    "active": bool(w.get("is_active")),
                    "freq": w.get("sync_frequency_minutes"),
                    "channels": ", ".join(
                        str(x) for x in (w.get("notification_channels") or [])
                    ),
                    "last_synced": w.get("last_synced_at") or "—",
                }
            )
        wdf = pd.DataFrame(wlist)
        tbl_cols_w = [
            "id",
            "query_name",
            "platform",
            "keywords",
            "locations",
            "min_score",
            "freq",
            "channels",
            "last_synced",
            "active",
        ]
        st.dataframe(
            wdf[tbl_cols_w].rename(
                columns={
                    "id": "🆔 ID",
                    "query_name": "🎯 İsmi",
                    "platform": "🌐 Platform",
                    "keywords": "🔎 Anahtar Kelimeler",
                    "locations": "📍 Konumlar",
                    "min_score": "⭐ Min Skor",
                    "freq": "⏱️ Frekans (dk)",
                    "channels": "🔔 Bildirim",
                    "last_synced": "🕒 Son Çalışma",
                    "active": "✅ Aktif",
                }
            ),
            use_container_width=True,
            hide_index=True,
            height=260,
        )

        # ------ TEKİL WATCHER İŞLEMLERİ (3 kolon) ------
        st.markdown("#### 🛠️ Tekil Watcher İşlemleri (Her satır için Toggle / Delete)")
        action_cols = st.columns([1, 1, 1])
        action_cols[0].caption("🔁 Durum Değiştir")
        action_cols[1].caption("❌ Sil")
        action_cols[2].caption("Durum / Sonuç")

        for w in watchers[:12]:  # maks 12 adet göster
            wid = w.get("id")
            short = f"{w.get('query_name', '?')} ({w.get('source_platform')!s})"
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                new_active = not bool(w.get("is_active"))
                lbl = f"🔁 {'PASİF yap' if w.get('is_active') else 'AKTİF yap'}: {short[:35]}"
                if st.button(lbl, key=f"tg_{wid}"):
                    if toggle_watcher_active(wid, new_active):
                        st.cache_data.clear()
                        time.sleep(0.4)
                        st.rerun()
                    else:
                        st.error("Toggle başarısız")
            with c2:
                if st.button(f"❌ Sil: {short[:35]}", key=f"del_{wid}"):
                    if delete_watcher(wid):
                        st.success(f"{short} silindi ✅")
                        st.cache_data.clear()
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Silme başarısız (404 / API yok)")
            with c3:
                st.write(f"ID: `{wid[:14]}` · Aktif: **{w.get('is_active')}**")
    else:
        st.info(
            "Henüz watcher tanımlı değil. Aşağıdaki formdan yeni bir izleyici oluşturun!"
        )

    st.divider()

    # ------ YENİ WATCHER OLUŞTUR ------
    st.subheader("➕ Yeni Watcher (İzleyici) Oluştur")
    wc1, wc2 = st.columns([1, 1])
    with wc1:
        nq = st.text_input(
            "🎯 Watcher Adı (Query Name)", value="Test Mühendisi / QA Yöneticisi"
        )
        platform_opts = [
            "manual_import",
            "linkedin_search_url",
            "linkedin_alert",
            "email_forward",
        ]
        np = st.selectbox("🌐 Kaynak Platform", platform_opts, index=0)
        n_min_score = st.slider("⭐ Minimum Eşleşme Skoru", 0, 100, 60, 1)
        n_freq = st.number_input("⏱️ Sync Sıklığı (dk)", 15, 1440, 120, 15)
        kw_txt = st.text_area(
            "🔎 Anahtar Kelimeler (virgülle ayır)",
            value="Test Mühendisi, QA, Yazılım Test, Selenium, Jira",
        )
        loc_txt = st.text_area(
            "📍 Konumlar (virgülle ayır)", value="İstanbul, Ankara, İzmir, Remote"
        )

    with wc2:
        headline = st.text_input(
            "👤 Aday Headline (Meslek/Unvan)",
            value="Test Yöneticisi / QA Yöneticisi / Yazılım Kalite Uzmanı",
        )
        summary = st.text_area(
            "📝 Aday Özeti",
            value="7+ yıl yazılım test ve kalite güvence deneyimi; test otomasyonu (Selenium, Playwright, Cypress), API test, load test, Agile/Scrum.",
            height=130,
        )
        years = st.slider("⏳ Toplam Deneyim (Yıl)", 0, 40, 7, 1)
        skills_txt = st.text_area(
            "💻 Yetenekler (virgülle)",
            value="Selenium, Playwright, Cypress, Postman, Jmeter, JUnit, PyTest, Jira, Confluence, SQL, Python, Java, JavaScript, REST API, CI/CD, Git, Agile, Scrum",
        )
        n_chan = st.multiselect(
            "🔔 Bildirim Kanalları", ["in_app", "email"], default=["in_app"]
        )

    create_body = {
        "user_id": USER_ID,
        "query_name": nq,
        "source_platform": np,
        "search_criteria": {
            "keywords": [x.strip() for x in kw_txt.split(",") if x.strip()],
            "locations": [x.strip() for x in loc_txt.split(",") if x.strip()],
            "min_experience_years": max(0, years - 3),
            "max_experience_years": years + 5,
        },
        "candidate_profile": {
            "headline": headline,
            "summary": summary,
            "total_experience_years": years,
            "skills": [s.strip() for s in skills_txt.split(",") if s.strip()],
        },
        "minimum_match_score": n_min_score,
        "sync_frequency_minutes": int(n_freq),
        "notification_channels": n_chan,
    }
    if st.button(
        "➕ KAYDET: Yeni Watcher Oluştur", type="primary", use_container_width=True
    ):
        try:
            rc = httpx.post(f"{API_BASE}/api/v1/watchers", json=create_body, headers=_API_HEADERS, timeout=15)
            if rc.status_code == 200:
                st.success(f"✅ Watcher oluşturuldu! ID: **{rc.json().get('id')}**")
                st.cache_data.clear()
                time.sleep(0.7)
                st.rerun()
            else:
                st.error(f"Hata {rc.status_code}: {rc.text[:350]}")
                with st.expander("📄 Gönderilen JSON Body (debug)"):
                    st.json(create_body)
        except Exception as e:
            st.error(f"Create hatası: {e}")


# ============================================================
# 👤 SEKME 3 · ADAY PROFİLİ + CV YÜKLEME
# ============================================================
with tab_profile:
    st.markdown("## 👤 Aday Profili + CV (Özgeçmiş)")
    st.info(
        "CV dosyası (PDF/DOCX) yükleyin → otomatik **başlık/özet/deneyim/yetenek** çıkarımı (şimdilik: manuel düzenleme + SQLite DB'ye kayıt). Gelecek sürümde PDF/DOCX parse eklenecek."
    )

    cvf = st.file_uploader(
        "📂 CV Dosyası Yükle (PDF / DOCX / TXT)",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=False,
    )
    if cvf is not None:
        size_kb = round(len(cvf.getvalue()) / 1024, 1)
        st.success(
            f"✅ Yüklendi: **{cvf.name}** · {size_kb} KB. İleride PDF/DOCX parser burada çalışacak."
        )
        try:
            ext = pathlib.Path(cvf.name).suffix.lower()
            content_preview = "(PDF/DOCX - içerik okunmadı)"
            if ext == ".txt":
                try:
                    content_preview = cvf.getvalue().decode("utf-8", errors="replace")[
                        :3000
                    ]
                except Exception:
                    content_preview = "(metin çözülemedi)"
            with st.expander(f"🔍 İçerik Önizleme ({cvf.name})"):
                st.text(content_preview or "(boş / binary)")
        except Exception:
            pass

    st.divider()
    st.subheader("🛠️ Profil Bilgilerini Düzenle")
    p1, p2 = st.columns([1, 1])
    with p1:
        p_headline = st.text_input(
            "👤 Başlık / Unvan",
            value=st.session_state.get("p_headline", "Test Yöneticisi / QA Yöneticisi"),
        )
        p_city = st.text_input(
            "📍 Şehir", value=st.session_state.get("p_city", "İstanbul")
        )
        p_years = st.slider("⏳ Toplam Deneyim", 0, 30, 7, 1)
        p_edu = st.text_input(
            "🎓 Eğitim",
            value=st.session_state.get("p_edu", "Lisans - Bilgisayar Mühendisliği"),
        )

    with p2:
        p_skills_txt = st.text_area(
            "💻 Yetenekler (virgülle)",
            value=st.session_state.get(
                "p_skills_txt",
                "Selenium, Playwright, Cypress, Postman, Jmeter, JUnit, PyTest, Jira, SQL, Python, Java",
            ),
            height=140,
        )
        p_lang_txt = st.text_area(
            "🌍 Diller (virgülle)",
            value=st.session_state.get(
                "p_lang_txt", "Türkçe (Ana Dil), İngilizce (İleri - C1)"
            ),
            height=60,
        )
        p_cert_txt = st.text_area(
            "🏆 Sertifikalar (virgülle)",
            value=st.session_state.get(
                "p_cert_txt",
                "ISTQB Foundation, Certified Scrum Master, AWS Cloud Practitioner",
            ),
            height=60,
        )
        p_summary = st.text_area(
            "📝 Özet / Hakkımda",
            value=st.session_state.get(
                "p_summary",
                "7+ yıl yazılım test ve kalite güvence deneyimi; ürün kalitesini artıran, otomasyon oranını yükselten test stratejileri geliştirdim.",
            ),
            height=100,
        )

    st.session_state["p_headline"] = p_headline
    st.session_state["p_city"] = p_city
    st.session_state["p_skills_txt"] = p_skills_txt
    st.session_state["p_lang_txt"] = p_lang_txt
    st.session_state["p_cert_txt"] = p_cert_txt
    st.session_state["p_edu"] = p_edu
    st.session_state["p_summary"] = p_summary

    if st.button("💾 Profil Kaydet (session + .env proxy)", use_container_width=True):
        os.environ["CR_PROFILE_HEADLINE"] = p_headline
        os.environ["CR_PROFILE_CITY"] = p_city
        os.environ["CR_PROFILE_YEARS"] = str(p_years)
        os.environ["CR_PROFILE_SKILLS"] = p_skills_txt
        os.environ["CR_PROFILE_LANG"] = p_lang_txt
        os.environ["CR_PROFILE_CERT"] = p_cert_txt
        os.environ["CR_PROFILE_SUMMARY"] = p_summary
        st.success(f"""✅ Profil kaydedildi. Kalıcı kayıt için .env dosyasına ekleyebilirsiniz:
```bash
export CR_PROFILE_HEADLINE='{p_headline}'
export CR_PROFILE_CITY='{p_city}'
export CR_PROFILE_YEARS='{p_years}'
export CR_PROFILE_SKILLS='{p_skills_txt[:200]}...'
```""")


# ============================================================
# ⚙️ SEKME 4 · AYARLAR (User / SMTP / Bildirim)
# ============================================================
with tab_settings:
    st.markdown("## ⚙️ Kişisel Ayarlar (Kullanıcı + SMTP + Bildirim Kanalları)")

    st.subheader("👤 Kullanıcı")
    c01, c02 = st.columns([3, 1])
    c01.text_input(
        "Kullanıcı ID (Bildirim ve arşiv filtresi)", key="USER_ID", value=DEFAULT_USER
    )
    c02.metric("Seçili Kullanıcı", USER_ID)

    st.divider()
    st.subheader("📧 SMTP E-posta Ayarları (Yüksek Skorlu İlan Bildirimi)")
    s1, s2, s3 = st.columns(3)
    s1.text_input("SMTP Host (örn: smtp.gmail.com)", key="smtp_host")
    s2.number_input(
        "SMTP Port (465 = SSL / 587 = STARTTLS)",
        min_value=0,
        max_value=65535,
        step=1,
        key="smtp_port",
    )
    s3.text_input("SMTP Kullanıcı Adı (e-posta)", key="smtp_user")
    s4, s5, s6 = st.columns(3)
    s4.text_input("SMTP Şifre / Uygulama Şifresi", type="password", key="smtp_pass")
    s5.text_input("Görünen Gönderen (From) — opsiyonel", key="smtp_from")
    s6.text_input("Test Maili Gönderilecek Hedef E-posta", key="to_email_test")
    b_smtp1, b_smtp2 = st.columns([1, 1])
    if b_smtp1.button("💾 Ayarları Ortama Kaydet (env proxy)"):
        os.environ["SMTP_HOST"] = st.session_state.smtp_host
        os.environ["SMTP_PORT"] = str(st.session_state.smtp_port)
        os.environ["SMTP_USER"] = st.session_state.smtp_user
        os.environ["SMTP_PASS"] = st.session_state.smtp_pass
        os.environ["SMTP_FROM"] = st.session_state.smtp_from
        st.success(
            f"Ayarlar bu oturum için kaydedildi ✅. Kalıcı kayıt için .env dosyasına aşağıdaki satırları ekleyin:\n\n```bash\nexport SMTP_HOST='{st.session_state.smtp_host}'\nexport SMTP_PORT={st.session_state.smtp_port}\nexport SMTP_USER='{st.session_state.smtp_user}'\nexport SMTP_PASS='*********'\nexport SMTP_FROM='{st.session_state.smtp_from or st.session_state.smtp_user}'\n```"
        )
    if b_smtp2.button("📤 TEST MAİLİ GÖNDER"):
        ok, msg = send_test_email(
            host=st.session_state.smtp_host,
            port=st.session_state.smtp_port,
            user=st.session_state.smtp_user,
            pwd=st.session_state.smtp_pass,
            sender=st.session_state.smtp_from,
            to_email=st.session_state.to_email_test,
        )
        if ok:
            st.success(msg)
        else:
            st.warning(msg)

    st.divider()
    st.subheader("🔔 Bildirimler (Hızlı İşlemler)")
    bn1, bn2, bn3 = st.columns(3)
    try:
        ruc = httpx.get(
            f"{API_BASE}/api/v1/notifications/unread-count",
            params={"user_id": USER_ID},
            headers=_API_HEADERS,
            timeout=6,
        )
        uc_data = ruc.json() if ruc.status_code == 200 else {"unread_count": new_notif}
    except Exception:
        uc_data = {"unread_count": new_notif}
    bn1.metric("API: Okunmamış Sayısı", f"{uc_data.get('unread_count', new_notif)}")
    if bn2.button("✅ TÜMÜNÜ OKUNDU İŞARETLE"):
        cnt = mark_all_read(USER_ID)
        st.success(
            f"{cnt} adet bildirim OKUNDU olarak işaretlendi. Veriler yenileniyor..."
        )
        st.cache_data.clear()
        time.sleep(0.7)
        st.rerun()
    if bn3.button("🔄 Bildirimleri YENİDEN YÜKLE"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("📋 İşlem Logları (Operation Logs)")
    try:
        lf1, lf2, lf3 = st.columns(3)
        lvl_opts = ["Tümü", "DEBUG", "INFO", "WARN", "ERROR"]
        log_level = lf1.selectbox("Level", lvl_opts, index=0)
        src_opts = ["Tümü", "api", "scheduler", "discovery", "email", "match"]
        log_source = lf2.selectbox("Kaynak", src_opts, index=0)
        log_limit = lf3.slider("Gösterilecek Kayıt (son N)", 10, 500, 100, 10)
        params = {"limit": log_limit}
        if USER_ID and str(USER_ID).strip():
            params["user_id"] = str(USER_ID).strip()
        if log_level != "Tümü":
            params["level"] = log_level
        if log_source != "Tümü":
            params["source"] = log_source
        rl = httpx.get(f"{API_BASE}/api/v1/logs", params=params, headers=_API_HEADERS, timeout=10)
        logs_data = rl.json() if rl.status_code == 200 else []
    except Exception:
        # Fallback: doğrudan SQLite operation_logs tablosu (tablo yoksa [])
        logs_data = []
        try:
            if ROOT_DB.exists():
                cnx = sqlite3.connect(ROOT_DB)
                cx = cnx.cursor()
                cx.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='operation_logs'"
                )
                if cx.fetchone():
                    q = "SELECT id, timestamp, level, source, user_id, watcher_id, message, metadata FROM operation_logs WHERE user_id=? OR user_id IS NULL ORDER BY timestamp DESC LIMIT ?"
                    cx.execute(q, (USER_ID, int(params.get("limit", 100))))
                    c_cols = [d[0] for d in cx.description]
                    for row in cx.fetchall():
                        dd = dict(zip(c_cols, row, strict=False))
                        import json as _jj

                        try:
                            dd["metadata"] = _jj.loads(dd.get("metadata") or "{}")
                        except Exception:
                            dd["metadata"] = {}
                        logs_data.append(dd)
                cnx.close()
        except Exception:
            pass

    if logs_data:
        ldf = pd.DataFrame(logs_data)

        def _lvl_emoji(v: str) -> str:
            v = str(v).upper()
            return {"DEBUG": "🐞", "INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❌"}.get(v, "📝")

        ldf["_lvlicon"] = ldf["level"].map(_lvl_emoji)
        show_cols = [
            "id",
            "timestamp",
            "_lvlicon",
            "level",
            "source",
            "user_id",
            "watcher_id",
            "message",
        ]
        keep_cols = [c for c in show_cols if c in ldf.columns]
        cnt = len(ldf)
        err_n = (
            len(ldf[ldf.level.astype(str).str.upper() == "ERROR"])
            if "level" in ldf.columns
            else 0
        )
        warn_n = (
            len(ldf[ldf.level.astype(str).str.upper() == "WARN"])
            if "level" in ldf.columns
            else 0
        )
        m1, m2, m3 = st.columns(3)
        m1.metric(
            f"📝 Toplam {log_level.lower() if log_level != 'Tümü' else ''} Log",
            f"{cnt}",
        )
        m2.metric("⚠️ Uyarı (WARN)", f"{warn_n}")
        m3.metric("❌ Hata (ERROR)", f"{err_n}")
        st.dataframe(
            ldf[keep_cols].rename(
                columns={
                    "id": "🆔 ID",
                    "timestamp": "⏱️ Zaman",
                    "_lvlicon": "",
                    "level": "Level",
                    "source": "🎯 Kaynak",
                    "user_id": "👤 User",
                    "watcher_id": "👀 Watcher",
                    "message": "📝 Mesaj",
                }
            ),
            use_container_width=True,
            hide_index=True,
            height=380,
            column_config={
                "🆔 ID": st.column_config.TextColumn(width="small"),
            },
        )
    else:
        st.info(
            "📋 Henüz işlem logu kaydedilmemiş. İlk Scheduler Run veya Watcher CRUD sonrası burada görünecek."
        )
    if st.button("🔄 Logları Yenile", key="log_refresh"):
        st.cache_data.clear()
        st.rerun()


st.divider()
st.caption(
    "CareerRadar AI v1.6 · 49 Test PASSED · Hybrid Match · 3 Katmanlı Scraper + 8 Bot Domain PW Fallback · APScheduler 120dk · Operation Logs SQLite · DB: careerradar.db"
)
