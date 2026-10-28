# CareerRadar AI Matching API

Bu servis, aday profili ile iş ilanlarını hibrit bir yapay zekâ eşleştirme motoru üzerinden puanlar.

## Özellikler
- Türkçe metin normalizasyonu, stop-word temizleme ve hafif stemming
- Yapılandırılmış veriler için eksik veri imputasyonu ve aykırı değer kırpma
- Kural tabanlı alt skorlar + anlamsal benzerlik tabanlı hibrit skor
- KVKK/GDPR odaklı gizlilik notları
- FastAPI tabanlı REST API
- Pytest ile birim, entegrasyon ve API testleri

## Kurulum

```bash
cd apps/api
python3 -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

## Uç Noktalar
- `GET /api/v1/matching/health`
- `POST /api/v1/matching/preprocess`
- `POST /api/v1/matching/batch-match`

## Örnek İstek

```bash
curl -X POST http://localhost:8000/api/v1/matching/batch-match \
  -H "Content-Type: application/json" \
  -d @example-request.json
```

## Test Çalıştırma

```bash
cd apps/api
pytest -q
```

## Benchmark

```bash
python3 infra/scripts/benchmark_matching.py
```

## Not
- `sentence-transformers` entegrasyonu adaptör seviyesinde hazırdır; paket kurulduğunda daha gelişmiş semantik embedding ile değiştirilebilir.
- Gerçek dünyadaki F1, yanlış pozitif ve yanlış negatif hedefleri için etiketli üretim verisi üzerinde ayrıca kalibrasyon yapılmalıdır.
