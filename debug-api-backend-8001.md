# Debug Session: api-backend-8001

Status: OPEN

## Problem
- `apps/api` FastAPI backend `127.0.0.1:8001` üzerinde servis vermiyor.
- Hedef: süreci başlatıp exact exit reason veya bind failure nedenini toplamak.

## Hypotheses
1. Gerekli Python environment veya bağımlılıklar eksik, bu yüzden süreç import/startup aşamasında exit ediyor.
2. Uygulama yanlış entrypoint ya da yanlış çalışma diziniyle başlatılıyor ve `module not found`/config hatası veriyor.
3. `8001` portu başka bir süreç tarafından kullanılıyor ve Uvicorn bind aşamasında kapanıyor.
4. Zorunlu environment değişkenleri veya config dosyaları eksik olduğu için FastAPI startup event içinde hata alıyor.
5. Veritabanı veya başka bir dış bağımlı bağlantısı startup sırasında exception fırlatıyor.

## Evidence Log
- `apps/web/next.config.ts` varsayılan backend adresini `http://127.0.0.1:8001` olarak ayarlıyor.
- `apps/api/README.md` start komutunu `uvicorn app.main:app --reload` olarak veriyor; bu durumda Uvicorn varsayılan olarak `127.0.0.1:8000` portunu kullanır.
- `apps/api/Dockerfile` içinde hem `EXPOSE 8000` hem de `CMD ... --port 8000` tanımlı.
- `8001` için listener kontrolünde aktif dinleyen süreç görülmedi.
- Sandbox içinde `python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8001` denemesi exit code `0` ile hemen döndü ancak stdout/stderr üretmedi; bu nedenle uygulama içi traceback yerine repo konfigürasyonu ana kanıt oldu.

## Notes
- İlk aşamada business logic değişikliği yapılmayacak.
- En güçlü kök neden: frontend `8001` bekliyor, backend varsayılan start talimatı ve container konfigürasyonu `8000` açıyor.
