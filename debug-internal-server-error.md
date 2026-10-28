# Debug Session: internal-server-error

- Status: OPEN
- Symptom: Kullanıcı uygulamada `Internal Server Error` görüyor.
- Scope: Backend / frontend proxy / veri sıfırlama sonrası başlangıç akışı

## Hypotheses

1. Veritabanı silindikten sonra backend ilk istekte tablo/seed bekleyen bir akışta exception fırlatıyor.
2. Frontend, temizlenen backend verisine karşı stale client state gönderiyor ve bu state bir 500 üretiyor.
3. Yeni eklenen canlı keşif veya watcher akışı, eksik metadata/source URL nedeniyle korunmayan bir hata veriyor.
4. Frontend proxy doğru backend’e bağlı değil ya da backend ayağa kalksa da belirli route import zincirinde runtime exception oluşuyor.
5. Veri silme sonrası dosya/DB path’i yeniden oluşturulamadığı için profile/job/watcher repository katmanında açılış hatası oluşuyor.

## Evidence Log

- `http://127.0.0.1:3002/api/v1/profile?user_id=user-1` başlangıçta `500 Internal Server Error` döndürdü.
- Aynı anda `watchers`, `jobs`, `applications`, `notifications`, `archive` GET endpoint'leri de `500` verdi.
- Ayrı başlatılan temiz backend örneği `http://127.0.0.1:8002` üzerinde aynı istek `404 {"detail":"Profil bulunamadı."}` döndürdü.
- `8001` portunda çalışan prosesin cwd'si doğru repo içindeydi; sorun yanlış servis değil, yaşayan proses durumuydu.
- `8001` üzerindeki eski backend prosesi sonlandırılıp temiz yeniden başlatıldı.
- Yeniden başlatma sonrası:
  - `http://127.0.0.1:8001/api/v1/profile?user_id=user-1` -> `404 Profil bulunamadı.`
  - `http://127.0.0.1:3002/api/v1/profile?user_id=user-1` -> `404 Profil bulunamadı.`

## Analysis

- Hypothesis 1, 4 ve 5 içinden en güçlü doğrulanan kök neden: veritabanı silindikten sonra açık kalan backend prosesinin stale SQLite/runtime state ile `500` üretmesi.
- Aynı kod yeni proses altında `500` değil beklenen `404` verdiği için business logic bug'ı doğrulanmadı.
- Kullanıcının verileri sıfırlandığı için yeni doğru davranış `profil yoksa 404` dönmektir.

## Next Step

- Kullanıcı doğrulaması al. Onaydan sonra debug oturumunu kapat ve cleanup yap.
