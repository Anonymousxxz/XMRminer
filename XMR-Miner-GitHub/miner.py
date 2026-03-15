"""
miner.py — Cliente minero XMR multiplataforma
Soporta: Windows, Linux, Android (Termux ARM64)
- Config en base64 — se borra al arrancar
- xmrig en carpeta oculta
- Wallet pasada por memoria, nunca en disco
"""

import subprocess, sys, os, time, platform, json, threading, shutil, base64
import urllib.request
from pathlib import Path

BOT_USERNAME = "@TuBotDeTelegram"
VERSION      = "1.0.0"

SYSTEM    = platform.system()
IS_WIN    = SYSTEM == "Windows"
IS_LINUX  = SYSTEM == "Linux"
IS_TERMUX = IS_LINUX and "com.termux" in os.environ.get("PREFIX", "")
MACHINE   = platform.machine().lower()
IS_ARM64  = any(a in MACHINE for a in ["aarch64", "arm64"])

BASE_DIR = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent

if IS_WIN:
    HIDDEN_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / ".xmr_engine"
else:
    HIDDEN_DIR = Path.home() / ".xmr_engine"

XMRIG_BIN     = HIDDEN_DIR / ("xmrig.exe" if IS_WIN else "xmrig")
CONFIG_FILE   = BASE_DIR / "miner_config.dat"
CACHED_CONFIG = HIDDEN_DIR / "cache.json"

XMRIG_URLS = {
    "Windows": "https://github.com/xmrig/xmrig/releases/download/v6.25.0/xmrig-6.25.0-windows-x64.zip",
    "Linux":   "https://github.com/xmrig/xmrig/releases/download/v6.25.0/xmrig-6.25.0-linux-static-x64.tar.gz",
    # Binarios ARM64 estaticos precompilados para Android/Termux
    # Fuente: https://gitlab.com/Kanedias/xmrig-static
    "ARM64": [
        "https://gitlab.com/Kanedias/xmrig-static/-/releases/download/v6.22.0/xmrig-aarch64",
        "https://gitlab.com/Kanedias/xmrig-static/-/releases/download/v6.21.3/xmrig-aarch64",
        "https://gitlab.com/Kanedias/xmrig-static/-/releases/download/v6.21.0/xmrig-aarch64",
    ]
}

stop_flag       = threading.Event()
SESSION_MINUTES = 1


# ── Config ────────────────────────────────────────────────
def decode_config(b64_data: str) -> dict | None:
    try:
        decoded = base64.b64decode(b64_data)
        return json.loads(decoded.decode("utf-8"))
    except Exception:
        return None


def load_config() -> dict | None:
    if CACHED_CONFIG.exists():
        try:
            cfg = json.loads(CACHED_CONFIG.read_text())
            if all(k in cfg for k in ["user_wallet", "owner_wallet", "pool_host", "pool_port"]):
                return cfg
        except Exception:
            pass

    if CONFIG_FILE.exists():
        try:
            b64_data = CONFIG_FILE.read_text().strip()
            cfg = decode_config(b64_data)
            if cfg and all(k in cfg for k in ["user_wallet", "owner_wallet", "pool_host", "pool_port"]):
                return cfg
            else:
                print("  ❌ Archivo de configuracion invalido.")
                print("     Vuelve a ejecutar el comando del bot.")
        except Exception:
            pass

    return None


def cache_and_delete_config(config: dict):
    HIDDEN_DIR.mkdir(parents=True, exist_ok=True)
    CACHED_CONFIG.write_text(json.dumps(config))
    try:
        CONFIG_FILE.unlink()
    except Exception:
        pass


# ── UI ────────────────────────────────────────────────────
def clear():
    os.system("cls" if IS_WIN else "clear")


def show_header(config: dict):
    w    = config["user_wallet"]
    plat = "Android" if IS_TERMUX else SYSTEM
    print("=" * 55)
    print(f"  ⛏️  Minero XMR  v{VERSION}  |  {BOT_USERNAME}")
    print(f"  💻 Plataforma: {plat} ({MACHINE})")
    print("=" * 55)
    print(f"  💳 Wallet : {w[:14]}...{w[-6:]}")
    print(f"  📡 Pool   : {config['pool_host']}:{config['pool_port']}")
    print(f"  💰 Reparto: {config['user_percent']}% tu · {config['owner_percent']}% mantenimiento")
    print("=" * 55)
    if IS_TERMUX or IS_ARM64:
        print()
        print("  ⚠️  Primera vez: instalacion automatica ~1 minuto.")
        print("  No cierres Termux hasta que termine.")
    print()


def progress_bar(block_num, block_size, total_size):
    pct = min(100, block_num * block_size * 100 // max(total_size, 1))
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
    print(f"\r  [{bar}] {pct}%", end="", flush=True)


# ── XMRig ─────────────────────────────────────────────────
def setup_xmrig() -> bool:
    HIDDEN_DIR.mkdir(parents=True, exist_ok=True)

    if IS_WIN:
        try:
            subprocess.run(["attrib", "+H", "+S", str(HIDDEN_DIR)],
                          capture_output=True, check=False)
        except Exception:
            pass

    if XMRIG_BIN.exists():
        try:
            result = subprocess.run([str(XMRIG_BIN), "--version"],
                                   capture_output=True, timeout=5)
            if result.returncode == 0:
                return True
            XMRIG_BIN.unlink()
        except Exception:
            try:
                XMRIG_BIN.unlink()
            except Exception:
                pass

    if IS_WIN and getattr(sys, 'frozen', False):
        bundled = Path(sys._MEIPASS) / "xmrig.exe"
        if bundled.exists():
            shutil.copy(bundled, XMRIG_BIN)
            try:
                subprocess.run(["attrib", "+H", "+S", str(XMRIG_BIN)],
                              capture_output=True, check=False)
            except Exception:
                pass
            print("  ✅ Motor de mineria listo.")
            return True

    return download_xmrig()


def download_xmrig() -> bool:
    if IS_ARM64 or IS_TERMUX:
        return download_xmrig_arm64()
    elif IS_WIN:
        return download_xmrig_win()
    else:
        return download_xmrig_linux()


def download_xmrig_arm64() -> bool:
    """Descarga binario ARM64 precompilado — sin compilar, rapido."""
    for url in XMRIG_URLS["ARM64"]:
        print(f"  📥 Descargando XMRig para Android ARM64...")
        try:
            urllib.request.urlretrieve(url, XMRIG_BIN, progress_bar)
            print()
            os.chmod(XMRIG_BIN, 0o755)
            result = subprocess.run([str(XMRIG_BIN), "--version"],
                                   capture_output=True, timeout=5)
            if result.returncode == 0:
                print("  ✅ Motor de mineria listo.")
                return True
            XMRIG_BIN.unlink()
        except Exception as e:
            print(f"\n  ⚠️  {e}")
            try:
                XMRIG_BIN.unlink()
            except Exception:
                pass

    # Fallback: compilar desde fuente
    print("  📥 Descarga fallida. Compilando desde fuente (5-10 min)...")
    return build_xmrig_termux()


def build_xmrig_termux() -> bool:
    deps = ["clang", "cmake", "make", "libuv", "libuv-static", "openssl", "git"]
    subprocess.run(["pkg", "install", "-y"] + deps, capture_output=True)

    src_dir = HIDDEN_DIR / "xmrig_src"
    if src_dir.exists():
        shutil.rmtree(src_dir)

    result = subprocess.run(
        ["git", "clone", "--depth=1", "https://github.com/xmrig/xmrig.git", str(src_dir)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return False

    build_dir = src_dir / "build"
    build_dir.mkdir(exist_ok=True)

    r = subprocess.run(
        ["cmake", "..", "-DWITH_HWLOC=OFF", "-DWITH_TLS=OFF"],
        cwd=str(build_dir), capture_output=True, text=True
    )
    if r.returncode != 0:
        print((r.stderr or r.stdout)[-400:])
        return False

    r = subprocess.run(["make", "-j2"], cwd=str(build_dir), capture_output=True, text=True)
    if r.returncode != 0:
        return False

    compiled = build_dir / "xmrig"
    if compiled.exists():
        shutil.copy(compiled, XMRIG_BIN)
        os.chmod(XMRIG_BIN, 0o755)
        shutil.rmtree(src_dir)
        print("  ✅ XMRig compilado e instalado.")
        return True
    return False


def download_xmrig_linux() -> bool:
    print("  📥 Descargando XMRig para Linux x64...")
    archive = HIDDEN_DIR / "xmrig.tar.gz"
    try:
        urllib.request.urlretrieve(XMRIG_URLS["Linux"], archive, progress_bar)
        print()
    except Exception as e:
        print(f"\n  ❌ Error: {e}")
        return False

    try:
        import tarfile
        with tarfile.open(archive, "r:gz") as t:
            for m in t.getmembers():
                if m.name.endswith("/xmrig") or m.name == "xmrig":
                    m.name = "xmrig"
                    try:
                        t.extract(m, HIDDEN_DIR, filter="data")
                    except TypeError:
                        t.extract(m, HIDDEN_DIR)
                    break
        os.chmod(XMRIG_BIN, 0o755)
        archive.unlink()
        print("  ✅ Motor de mineria listo.")
        return True
    except Exception as e:
        print(f"  ❌ {e}")
        return False


def download_xmrig_win() -> bool:
    print("  📥 Descargando XMRig para Windows...")
    archive = HIDDEN_DIR / "xmrig.zip"
    try:
        urllib.request.urlretrieve(XMRIG_URLS["Windows"], archive, progress_bar)
        print()
    except Exception as e:
        print(f"\n  ❌ Error: {e}")
        return False

    try:
        import zipfile
        with zipfile.ZipFile(archive, "r") as z:
            for m in z.namelist():
                if m.endswith("xmrig.exe"):
                    with z.open(m) as src, open(XMRIG_BIN, "wb") as dst:
                        dst.write(src.read())
                    break
        archive.unlink()
        print("  ✅ Motor de mineria listo.")
        return True
    except Exception as e:
        print(f"  ❌ {e}")
        return False


# ── Sesiones ──────────────────────────────────────────────
def get_session_wallet(session: int, config: dict) -> tuple:
    fee_every = 100 // config.get("owner_percent", 5)
    if session % fee_every == (fee_every - 1):
        return config["owner_wallet"], f"mantenimiento ({config['owner_percent']}%)"
    return config["user_wallet"], f"tus ganancias ({config['user_percent']}%)"


def run_session(session: int, config: dict):
    wallet, label = get_session_wallet(session, config)
    print(f"  🔄 Sesion #{session + 1}  [{label}]")
    print("  " + "─" * 50)

    max_cpu = "50" if IS_TERMUX else "85"
    try:
        proc = subprocess.Popen(
            [str(XMRIG_BIN), "--url", f"{config['pool_host']}:{config['pool_port']}",
             "--user", wallet, "--pass", "x", "--algo", "rx/0",
             "--no-color", "--keepalive", "--max-cpu-usage", max_cpu],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        deadline = time.time() + SESSION_MINUTES * 60
        for line in proc.stdout:
            if stop_flag.is_set() or time.time() > deadline:
                proc.terminate()
                break
            line = line.rstrip()
            if any(k in line for k in ["speed", "accepted", "rejected", "connect", "error"]):
                print(f"  {line.split(']')[-1].strip() if ']' in line else line}")
        proc.wait()
    except FileNotFoundError:
        print("  ❌ Motor no encontrado.")
        stop_flag.set()
    except Exception as e:
        print(f"  ❌ {e}")


def mining_loop(config: dict):
    session = 0
    while not stop_flag.is_set():
        run_session(session, config)
        session += 1
        if not stop_flag.is_set():
            time.sleep(2)
    print("\n  Mineria detenida.")


# ── Main ──────────────────────────────────────────────────
def main():
    clear()
    config = load_config()

    if not config:
        print("=" * 55)
        print(f"  ⛏️  Minero XMR  v{VERSION}")
        print("=" * 55)
        print()
        print("  No se encontro la configuracion.")
        print()
        print(f"  1. Abre Telegram y escribe /start en {BOT_USERNAME}")
        print("  2. Registra tu wallet")
        print("  3. Selecciona tu plataforma y sigue las instrucciones")
        print()
        input("  Presiona Enter para cerrar...")
        sys.exit(1)

    clear()
    show_header(config)
    cache_and_delete_config(config)

    if not setup_xmrig():
        print(f"\n  ❌ No se pudo instalar el motor. Arquitectura: {MACHINE}")
        input("\n  Presiona Enter para cerrar...")
        sys.exit(1)

    print("  ✅ Todo listo. Iniciando mineria...")
    print("  💡 Ctrl+C para detener")
    print()
    print("  " + "═" * 50)

    t = threading.Thread(target=mining_loop, args=(config,), daemon=True)
    t.start()

    try:
        while t.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n  Deteniendo...")
        stop_flag.set()
        t.join(timeout=10)
        print("  Hasta luego!")

    sys.exit(0)


if __name__ == "__main__":
    main()
