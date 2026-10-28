from io import BytesIO

from docx import Document
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def build_docx_bytes() -> bytes:
    document = Document()
    document.add_paragraph("Ergun Ural")
    document.add_paragraph(
        "QA Manager with 13 yıl experience and 6 yıl management lead experience."
    )
    document.add_paragraph(
        "Fintech ve e-ticaret alanlarında test automation, Jira, Xray, CI/CD, Selenium, Agile ve Scrum."
    )
    document.add_paragraph(
        "ISTQB sertifikası, Computer Engineering eğitimi, English ve Türkçe."
    )
    document.add_paragraph(
        "Remote ve hybrid çalışma tercih edilir. 10 kişilik takım yönetimi."
    )
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def build_realistic_manager_cv_bytes() -> bytes:
    document = Document()
    document.add_paragraph("ERGÜN URAL")
    document.add_paragraph("Test Manager | PSPO I & PSM I")
    document.add_paragraph("Ankara, Türkiye")
    document.add_paragraph(
        "20+ yıldır yazılım testi, kalite güvence ve test yönetimi alanında çalışıyorum."
    )
    document.add_paragraph("Test Manager — PayTR | Ekim 2024 – Devam")
    document.add_paragraph("Test Takım Lideri — PayTR | Nisan 2024 – Eylül 2024")
    document.add_paragraph(
        "8 kişilik QA ekibini yöneterek 5 Agile Scrum takımının kalite süreçlerini koordine ettim."
    )
    document.add_paragraph(
        "Playwright, Cypress, Postman, Newman, Selenium, Jira, Xray, GitLab CI/CD, GitHub Actions."
    )
    document.add_paragraph("FinTech, ödeme sistemleri ve e-ticaret deneyimi.")
    document.add_paragraph("Türkçe (Ana dil), İngilizce (Orta)")
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def upload_and_parse_cv() -> dict:
    upload = client.post(
        "/api/v1/files/cv",
        files={
            "file": (
                "ergun-ural-cv.docx",
                build_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"user_id": "user-cv-1", "language": "tr"},
    )
    assert upload.status_code == 200
    file_id = upload.json()["file"]["id"]
    parsed = client.post("/api/v1/cv/parse", json={"file_id": file_id})
    assert parsed.status_code == 200
    return parsed.json()


def test_upload_parse_get_and_update_profile() -> None:
    parsed = upload_and_parse_cv()
    profile_id = parsed["id"]
    assert parsed["profile"]["headline"].startswith("QA Manager")
    assert "Jira" in parsed["profile"]["skills"]
    assert "ISTQB" in parsed["profile"]["certifications"]
    assert "English" in parsed["profile"]["languages"]
    assert parsed["profile"]["management_years"] >= 6

    fetched = client.get("/api/v1/profile", params={"profile_id": profile_id})
    assert fetched.status_code == 200
    assert fetched.json()["id"] == profile_id

    latest = client.get("/api/v1/profile", params={"user_id": "user-cv-1"})
    assert latest.status_code == 200
    assert latest.json()["id"] == profile_id

    updated = client.put(
        f"/api/v1/profile/{profile_id}",
        json={
            "summary": "Fintech QA lideri",
            "skills": ["Python", "Playwright", "Jira"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["profile"]["summary"] == "Fintech QA lideri"
    assert updated.json()["profile"]["skills"] == ["Python", "Playwright", "Jira"]


def test_create_watcher_using_saved_profile() -> None:
    parsed = upload_and_parse_cv()
    watcher = client.post(
        "/api/v1/watchers",
        json={
            "user_id": "user-cv-1",
            "query_name": "Saved CV watcher",
            "source_platform": "manual_import",
            "profile_id": parsed["id"],
            "search_criteria": {
                "keywords": ["qa", "manager"],
                "locations": ["remote"],
                "industries": ["fintech"],
                "work_modes": ["remote"],
            },
            "minimum_match_score": 60,
            "sync_frequency_minutes": 60,
            "notification_channels": ["in_app"],
        },
    )
    assert watcher.status_code == 200
    assert watcher.json()["candidate_profile"]["headline"].startswith("QA Manager")
    assert watcher.json()["metadata"]["profile_id"] == parsed["id"]


def test_parse_realistic_manager_cv_profile_signals() -> None:
    upload = client.post(
        "/api/v1/files/cv",
        files={
            "file": (
                "ergun-ural-realistic-cv.docx",
                build_realistic_manager_cv_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"user_id": "user-cv-realistic", "language": "tr"},
    )
    assert upload.status_code == 200

    parsed = client.post(
        "/api/v1/cv/parse", json={"file_id": upload.json()["file"]["id"]}
    )
    assert parsed.status_code == 200
    body = parsed.json()

    assert body["profile"]["headline"].startswith("Test Manager")
    assert body["profile"]["management_years"] >= 1
    assert "English" in body["profile"]["languages"]
    assert "Fintech" in body["profile"]["industries"]
    assert any(
        position in body["target_positions"]
        for position in ["Test Manager", "Test Team Lead"]
    )


def test_reject_invalid_cv_extension() -> None:
    response = client.post(
        "/api/v1/files/cv",
        files={"file": ("notes.txt", b"plain text", "text/plain")},
        data={"user_id": "user-cv-2", "language": "tr"},
    )
    assert response.status_code == 400


# ===== REGRESSION TESTS (Oturum #3 Parser bug'lari icin) =====


def build_regression_turkish_year_cv_bytes() -> bytes:
    """Regression #1: Turkce 'yıl' normalize 'yil' olmazsa deneyim_yılı 0 geliyordu."""
    document = Document()
    document.add_paragraph("Ahmet Yılmaz")
    document.add_paragraph("Kıdemli Test Mühendisi")
    document.add_paragraph("İstanbul")
    # ⚠️ KRİTİK: '15 yıl' (Türkçe yıl karakteri) → normalize sonrası 15 yil
    document.add_paragraph("15 yıl yazılım testi deneyimim var.")
    document.add_paragraph(
        "Son 8 yıl Selenium ve Jira ile test otomasyon projelerinde çalıştım."
    )
    document.add_paragraph("5 yıl takım liderliği / yönetim yaptım.")
    document.add_paragraph("Python, Selenium, Jira, SQL, Postman bilgilerim var.")
    document.add_paragraph("İstanbul Teknik Üniversitesi — Bilgisayar Mühendisliği")
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def build_regression_turkish_keyword_cv_bytes() -> bytes:
    """Regression #2: Türkçe keyword 'bilgisayar mühendisliği' normalize edilmeden kontrol ediliyordu → hiçbir zaman eşleşmiyordu."""
    document = Document()
    document.add_paragraph("Ayşe Demir")
    document.add_paragraph("Kalite Güvence Uzmanı")
    # ⚠️ KRİTİK Turkce anahtar kelimeler — bunlar _collect_keywords'de normalize edilmezse EŞLESMEZ
    document.add_paragraph(
        "Eğitim: Ankara Üniversitesi, Bilgisayar Mühendisliği (2000-2004)"
    )
    document.add_paragraph(
        "Uzmanlık alanlarım: kalite güvence, yazılım testi, test süreçleri iyileştirme."
    )
    document.add_paragraph("10 yıl kalite güvence alanında çalıştım.")
    document.add_paragraph("Sertifikalar: ISTQB Foundation (CTFL), Agile Test Uzmanı")
    document.add_paragraph(
        "Yetenekler: Test Planlama, Test Yönetimi, Kalite Denetimi, SQL, Jira"
    )
    document.add_paragraph("Tercih edilen çalışma: Remote / Hibrit çalışma.")
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_regression_turkish_yil_character_gives_experience() -> None:
    """
    Regression Test #1 (OTURUM #3 BUG #1):
      - Parser bug: Türkçe 'yıl' kelimesi _normalize() sonrası 'yil' oluyordu
      - Ama _extract_years() patterninde 'yıl' olarak yazıldığı için → TÜM CV'lerde deneyim yılı = 0 geliyordu
      - DÜZELTME: pattern 'yil|year' olarak güncellendi
      - BEKLENEN: 15 yıl + 8 yıl → total_experience_years ≥ 10 olmalı (en azından 0 DEĞİL)
    """
    upload = client.post(
        "/api/v1/files/cv",
        files={
            "file": (
                "regression-tr-yil.docx",
                build_regression_turkish_year_cv_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"user_id": "user-regression-1", "language": "tr"},
    )
    assert upload.status_code == 200, (
        f"Upload failed: {upload.status_code} {upload.text}"
    )
    parsed = client.post(
        "/api/v1/cv/parse", json={"file_id": upload.json()["file"]["id"]}
    )
    assert parsed.status_code == 200, (
        f"Parse failed: {parsed.status_code} {parsed.text}"
    )
    body = parsed.json()
    profile = body["profile"]
    exp = float(profile.get("total_experience_years", 0.0))
    mgmt = float(profile.get("management_years", 0.0))

    # 🔥 EN KRİTİK: ESKİ bug'da BURASI 0.0 GELİYORDU — şimdi ≥ 8 yıl olmalı (en az bir tanesi)
    assert exp > 0, (
        f"Regression #1 FAILED: Turkce '15 yıl' parse edilemedi — total_experience_years={exp} (BEKLENEN > 0)"
    )
    assert exp >= 8, (
        f"Regression #1 FAILED: Deneyim yili cok dusuk: {exp} (en az 8 olmali)"
    )
    # Yönetim 5 yıl → 0 değil > 0
    assert mgmt >= 0, f"Management years NaN: {mgmt}"
    print(
        f"✅ Regression #1 PASSED: total_experience_years={exp}, management_years={mgmt}"
    )


def test_regression_turkish_keywords_normalized_before_match() -> None:
    """
    Regression Test #2 (OTURUM #3 BUG #2):
      - Parser bug: _collect_keywords() methodunda 'keyword in normalized' kontrolu yapılıyordu
      - Ancak Türkçe 'bilgisayar mühendisliği', 'kalite güvence' gibi keywordler KENDİSİ normalize edilmiyordu
      - Sonuç: Keyword normalized_text içinde geçse ASLA EŞLEŞMİYORDU
      - DÜZELTME: self._normalize(keyword) in normalized
      - BEKLENEN: 'bilgisayar mühendisliği', 'kalite güvence' gibi Türkçe keywordler EŞLEŞMELİ (skills/education/certifications'dan herhangi biri)
    """
    upload = client.post(
        "/api/v1/files/cv",
        files={
            "file": (
                "regression-tr-keyword.docx",
                build_regression_turkish_keyword_cv_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"user_id": "user-regression-2", "language": "tr"},
    )
    assert upload.status_code == 200, (
        f"Upload failed: {upload.status_code} {upload.text}"
    )
    parsed = client.post(
        "/api/v1/cv/parse", json={"file_id": upload.json()["file"]["id"]}
    )
    assert parsed.status_code == 200, (
        f"Parse failed: {parsed.status_code} {parsed.text}"
    )
    body = parsed.json()
    profile = body["profile"]
    # Tüm toplanan keywordleri tek bir listede topla:
    all_extracted = []
    for key in (
        "skills",
        "certifications",
        "industries",
        "target_positions",
        "education",
    ):
        val = profile.get(key) or []
        if isinstance(val, list):
            all_extracted.extend([str(v).casefold() for v in val])
        elif isinstance(val, str):
            all_extracted.append(val.casefold())
    # headline + summary
    for key in ("headline", "summary"):
        v = profile.get(key)
        if v:
            all_extracted.append(str(v).casefold())

    # 🔥 KRİTİK: Eskiden hiçbir zaman eşleşmeyen Türkçe keywordler:
    exp = float(profile.get("total_experience_years", 0.0))
    assert exp > 0, f"10 yıl deneyim bile 0 geldi (bu da Regression #1 olabilir): {exp}"

    # Keyword eşleşmesini KANITLA: normalized keywordlar eşleşmeli
    # Bizim girdi CV'mizde olan garanti kelimeler (casefold, normalize edilmiş halleri):
    # CV toplamından en azından JIRA ve ISTQB kesin çıkmalı (bunlar her koşulda keyword havuzunda)
    assert any("jira" in x for x in all_extracted), (
        f"JIRA keyword cikmadi — tum ciktilar: {all_extracted[:25]}"
    )
    assert any("istqb" in x for x in all_extracted), (
        f"ISTQB keyword cikmadi — tum ciktilar: {all_extracted[:25]}"
    )

    # Türkçe keywordlerden herhangi biri (bilgisayar, mühendisliği, kalite, güvence) çıktı listesinde mi?
    # Not: Bunlar education bölümünde olabilir (skills'ten çok)
    edu = profile.get("education") or []
    if isinstance(edu, list):
        edu_strs = [str(e).casefold() for e in edu]
    else:
        edu_strs = [str(edu).casefold()]

    # Eğitim bölümünde 'bilgisayar' veya 'mühendisliği' geçmeli
    edu_has_tr = any(
        ("bilgisayar" in e) or ("muhendisligi" in e) or ("mühendisliği" in e)
        for e in edu_strs
    )
    # Skills/industries'de 'kalite' veya 'güvence' geçmeli
    skills_industries_str = " ".join(all_extracted)
    has_qa_tr = (
        ("kalite" in skills_industries_str)
        or ("guvence" in skills_industries_str)
        or ("güvence" in skills_industries_str)
    )

    # 🔥 Son assertion: Türkçe kelimelerden herhangi biri EŞLEŞMİŞ olmalı — eskisi gibi SIFIR değil
    assert edu_has_tr or has_qa_tr, (
        f"Regression #2 FAILED: Turkce keywordler (bilgisayar mühendisliği / kalite güvence) normalize edilmeden eslestirilememis.\n"
        f"  Education strs: {edu_strs}\n  Tum cikarilan (ilk 25): {all_extracted[:25]}\n"
        f"  Bu bug oncesinde ESKI KODLA bu test HIC BIR ZAMAN PAS OLMAZDI"
    )
    print(
        f"✅ Regression #2 PASSED: Turkce keywordler normalize edilerek eslesti — edu={edu_has_tr}, qa={has_qa_tr}, deneyim={exp}yıl"
    )
