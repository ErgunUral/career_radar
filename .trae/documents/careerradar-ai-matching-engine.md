## 1. Amaç
Bu doküman, CareerRadar AI içinde aday profili ile iş ilanlarını eşleştiren gelişmiş yapay zekâ motorunun teknik tasarımını, API kullanımını, doğrulama yaklaşımını ve hata ayıklama rehberini açıklar.

## 2. Hedeflenen Eşleştirme Senaryosu
- Birincil senaryo: `aday-profili <-> iş ilanı`
- Veri kaynakları:
  - Yapılandırılmış aday profili
  - CV veya LinkedIn özetinden gelen serbest metin
  - İlan başlığı, açıklaması, gereksinimler ve meta alanları
- Çıktılar:
  - 0-100 toplam skor
  - Alt skorlar
  - Eksik yetkinlikler
  - Güçlü yönler
  - Başvuru önceliği

## 3. Uygulanan Bileşenler
### 3.1 Veri Ön İşleme
- Türkçe metin normalize edilir.
- Stop-word temizliği uygulanır.
- Hafif suffix tabanlı stemming uygulanır.
- Sayısal alanlar için eksik veri ortalama ile doldurulur.
- Aykırı değerler IQR yaklaşımı ile kırpılır.
- Kategorik alanlar `unknown` ile güvenli biçimde tamamlanır.

### 3.2 Hibrit Eşleştirme
- Kural tabanlı alt skorlar:
  - unvan
  - deneyim
  - teknik yetkinlik
  - liderlik
  - sektör
  - lokasyon ve çalışma modeli
  - dil
  - eğitim ve sertifika
  - maaş
- Anlamsal katman:
  - varsayılan olarak hızlı `HashingVectorizer` tabanlı embedding
  - opsiyonel olarak `sentence-transformers` adaptörü
  - kozinüs benzerliği ile semantik yakınlık
- Hibrit skor:
  - varsayılan olarak kural skoru yüzde 80
  - anlamsal skor yüzde 20

### 3.3 Performans Optimizasyonu
- Batch embedding üretimi
- NumPy tabanlı vektörleştirilmiş kozinüs benzerliği
- `InMemoryVectorIndex` ile semantik ön filtreleme
- Yüksek hacimde `semantic_prefilter_limit` ile aday iş kümesini daraltma
- `infra/scripts/benchmark_matching.py` ile throughput ölçümü

### 3.4 Güvenlik ve Gizlilik
- Gizlilik ayarları istek modeline dahil edildi.
- Hassas veri için açık rıza kontrolü var.
- PII maskeleme notları yanıt içinde dönüyor.
- Federatif öğrenme gereksinimi için merkezi olmayan işlem önerisi yer alıyor.
- Gerçek üretim kullanımında alan bazlı şifreleme, audit log ve veri silme iş akışları zorunlu.

## 4. API Kullanım Kılavuzu
### 4.1 Sağlık Kontrolü
`GET /api/v1/matching/health`

Örnek yanıt:

```json
{
  "status": "ok"
}
```

### 4.2 Ön İşleme
`POST /api/v1/matching/preprocess`

Örnek istek:

```json
{
  "samples": [
    {
      "text": "Yazılım test süreçlerinde otomasyon araçlarıyla çalıştım.",
      "numeric_features": {
        "years": 12
      },
      "categorical_features": {
        "mode": "remote"
      }
    }
  ]
}
```

### 4.3 Toplu Eşleştirme
`POST /api/v1/matching/batch-match`

Örnek istek:

```json
{
  "candidate": {
    "candidate_id": "cand-1",
    "headline": "QA Manager",
    "summary": "Fintech ve e-ticaret kalite liderliği",
    "total_experience_years": 14,
    "management_years": 7,
    "team_size_managed": 18,
    "skills": ["Python", "CI/CD", "Jira", "Xray"],
    "industries": ["Fintech"],
    "languages": ["Türkçe", "İngilizce"],
    "preferred_locations": ["remote"],
    "work_modes": ["remote"]
  },
  "jobs": [
    {
      "job_id": "job-1",
      "title": "Software Test Manager",
      "requirements": "Python, CI/CD, Jira, Xray",
      "required_skills": ["Python", "CI/CD", "Jira", "Xray"],
      "industries": ["Fintech"],
      "min_years_experience": 10,
      "management_years_required": 5,
      "location": "remote",
      "work_mode": "remote",
      "language_requirement": "İngilizce"
    }
  ]
}
```

## 5. Doğrulama Kriterleri
- Birim testleri:
  - ön işleme doğruluğu
  - skor hesaplama
  - metrik hesapları
- Entegrasyon testleri:
  - servis düzeyinde sıralama doğrulaması
- Uçtan uca testler:
  - API health
  - preprocess
  - batch-match
- Performans doğrulama:
  - benchmark betiği ile throughput ölçümü
- Kalite eşiği:
  - testlerde kürate edilmiş fixture üzerinde F1, FPR ve FNR eşiği kontrolü

## 6. Hata Ayıklama Rehberi
- Düşük skor geldiğinde:
  - `missing_keywords` alanını kontrol et
  - `breakdown` alt skorlarında en düşük boyutları incele
  - `semantic_similarity` ile kural skorunun ayrışıp ayrışmadığına bak
- Beklenmeyen eşleşmeler varsa:
  - aday ve ilan metninin normalize edilmiş versiyonunu `/preprocess` ile doğrula
  - `required_skills` ve `preferred_skills` alanlarının doğru ayrıştırıldığını kontrol et
  - `preferred_locations` ve `work_modes` alanlarını gözden geçir
- Performans düşerse:
  - `semantic_prefilter_limit` değerini küçült
  - batch boyutunu artır
  - opsiyonel vektör veritabanı entegrasyonuna geç
- Gizlilik riski varsa:
  - `mask_pii_for_llm=true` kullan
  - LLM çağrılarında sadece özetlenmiş metin gönder
  - aday kimliklerini pseudonymous ID ile taşı

## 7. Varsayımlar
- İlk sürümde gerçek `sentence-transformers` modeli opsiyonel entegrasyon olarak bırakılmıştır.
- Üretim hedefleri için etiketli veri seti ile ek kalibrasyon gerekecektir.
- `100.000+` kayıt için gerçek üretim ortamında pgvector veya eşdeğer ANN indeks önerilir.

## 8. Üretilen Dosyalar
- `apps/api/app/domains/matching/preprocessing.py`
- `apps/api/app/domains/matching/embedding.py`
- `apps/api/app/domains/matching/scorers.py`
- `apps/api/app/domains/matching/service.py`
- `apps/api/app/api/routes/matching.py`
- `apps/api/tests/*`
- `infra/scripts/benchmark_matching.py`
