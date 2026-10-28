[OPEN] Debug Session: api-500-error

## Semptom
- `localhost:3001` üzerinden `GET /api/v1/profile?user_id=user-1` ve `POST /api/v1/cv/parse` çağrıları `500 Internal Server Error` dönüyor.
- Bu hata `Önerilen İlanlar`, profil yenileme ve canlı gerçek veri akışını engelliyor.

## Beklenen Davranış
- Proxy üzerinden profile, parse ve jobs endpoint'leri sağlıklı dönmeli.
- UI, önerilen ilanlar ve güncel profil verisini backend'den okuyabilmeli.

## Hipotezler
1. `Next.js` rewrite doğru çalışıyor ama `127.0.0.1:8001` üzerinde backend süreci kapalı veya yanlış portta.
2. Backend ayağa kalkıyor fakat `user-1` profilini okurken veritabanı/şema uyumsuzluğu nedeniyle route içinde exception oluşuyor.
3. Yeni parser değişikliği sonrası `cv/parse` akışı mevcut kayıtta beklenmeyen veriyle kırılıyor.
4. Frontend dev server proxy katmanı request body veya header'ları bozduğu için backend doğru payload alamıyor.
5. 500 hatası yalnızca bazı route'larda oluşuyor ve ortak neden `storage/database path` gibi environment farkı.

## Kanıt Planı
- `3001` ve `8001` üstünden aynı endpoint'leri ayrı ayrı çağır.
- Backend sürecinin gerçekten dinleyip dinlemediğini doğrula.
- Gerekirse backend loglarını canlı okuyup ilk stack trace'i yakala.
- Hata route bazlı mı, yoksa tüm API katmanında mı ayır.

## Durum
- Başlangıç aşaması: runtime kanıt toplanıyor.

## Kanıt
- Next dev log: `ECONNREFUSED 127.0.0.1:8001`
- Frontend rewrite varsayılanı `8001`, backend README varsayılanı `8000`
- Sonuç: Hata route içi exception değil, öncelikle port uyuşmazlığı / backend erişimsizliği

## Uygulanan Düzeltme
- Frontend rewrite varsayılanı `8000` yapıldı.
- `.env.local.example` aynı port ile hizalandı.
