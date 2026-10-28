#!/usr/bin/env python3
import subprocess, sys, os, time, pathlib, signal, socket

ROOT = pathlib.Path("/Users/ergunural/Documents/trae_projects/CareerRadar_AI").resolve()
os.chdir(ROOT)
ENV = os.environ.copy()
ENV["PYTHONUNBUFFERED"] = "1"
ENV.pop("VIRTUAL_ENV", None)

def port_open(port, host="127.0.0.1", timeout=0.5):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        s.close()

def launch(name, cmd, cwd=None, wait_ready_port=None, max_wait=25):
    print(f"\n[{name}] Çalıştırılıyor: {' '.join(cmd)}")
    print(f"        cwd: {cwd or ROOT}")
    out = open(f"/tmp/_cr_{name.lower()}.log", "a")
    proc = subprocess.Popen(
        cmd, cwd=cwd or str(ROOT), stdout=out, stderr=out,
        start_new_session=True, env=ENV, bufsize=1,
    )
    print(f"        PID={proc.pid}  (log /tmp/_cr_{name.lower()}.log)")
    t0 = time.time()
    last_size = 0
    if wait_ready_port:
        while time.time() - t0 < max_wait:
            if port_open(wait_ready_port):
                print(f"        ✅ Port {wait_ready_port} AÇIK  ({time.time()-t0:.1f}s)")
                return proc
            try:
                size = pathlib.Path(f"/tmp/_cr_{name.lower()}.log").stat().st_size
            except Exception:
                size = 0
            if size != last_size:
                last_size = size
            time.sleep(0.6)
        print(f"        ⚠️ Zaman aşımı ({max_wait}s) — PID hala {proc.pid} yaşıyor mu? {proc.poll() is None}")
    return proc

uv = launch("UVICORN_8000",
    ["python3", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--log-level", "warning"],
    cwd=str(ROOT / "apps" / "api"), wait_ready_port=8000)

st = launch("STREAMLIT_8501",
    ["python3", "-m", "streamlit", "run", "apps/frontend/streamlit_app.py",
     "--server.address", "127.0.0.1", "--server.port", "8501",
     "--server.fileWatcherType", "none", "--server.headless", "true",
     "--logger.level", "warning"],
    cwd=str(ROOT), wait_ready_port=8501)

time.sleep(1.0)
print("\n" + "="*70)
print(f"  UVICORN  8000  →  PID {uv.pid}   canlı={uv.poll() is None}   port 8000={port_open(8000)}")
print(f"  STREAMLIT 8501  →  PID {st.pid}   canlı={st.poll() is None}   port 8501={port_open(8501)}")
print("="*70)
print(f"\n  Son 3 satır UVICORN  log:")
try:
    lines = open("/tmp/_cr_uvicorn_8000.log").read().splitlines()[-3:]
    for l in lines: print(f"    · {l[:180]}")
except Exception as e:
    print(f"    ❌ {e}")
print(f"\n  Son 3 satır STREAMLIT log:")
try:
    lines = open("/tmp/_cr_streamlit_8501.log").read().splitlines()[-3:]
    for l in lines: print(f"    · {l[:180]}")
except Exception as e:
    print(f"    ❌ {e}")
sys.exit(0)
