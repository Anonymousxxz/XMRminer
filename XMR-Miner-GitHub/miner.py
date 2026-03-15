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

# ── Detectar plataforma ───────────────────────────────────
SYSTEM    = platform.system()
IS_WIN    = SYSTEM == "Windows"
IS_LINUX  = SYSTEM == "Linux"
IS_TERMUX = IS_LINUX and "com.termux" in os.environ.get("PREFIX", "")

MACHINE  = platform.machine().lower()
IS_ARM64 = any(a in MACHINE for a in ["aarch64", "arm64"])

# ── Rutas ─────────────────────────────────────────────────
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
}

stop_flag       = threading.Event()
SESSION_MINUTES = 1


# ── Decodificar config (base64) ───────────────────────────
def decode_config(b64_data: str) -> dict | None:
    try:
        decoded = base64.b64decode(b64_data)
        return json.loads(decoded.decode("utf-8"))
    except Exception:
        return None


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
    if IS_TERMUX:
        print()
        print("  ⚠️  Primera vez: compilacion de 5-10 minutos.")
        print("  No cierres Termux hasta que termine.")
    print()


def progress_bar(block_num, block_size, total_size):
    pct = min(100, block_num * block_size * 100 // max(total_size, 1))
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
    print(f"\r  [{bar}] {pct}%", end="", flush=True)


# ── Config ────────────────────────────────────────────────
def load_config() -> dict | None:
    # 1. Buscar cache oculta (arranques posteriores)
    if CACHED_CONFIG.exists():
        try:
            cfg = json.loads(CACHED_CONFIG.read_text())
            if all(k in cfg for k in ["user_wallet", "owner_wallet", "pool_host", "pool_port"]):
                return cfg
        except Exception:
            pass

    # 2. Leer config visible (primer arranque)
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
    """Guarda en oculto y borra el archivo visible inmediatamente."""
    HIDDEN_DIR.mkdir(parents=True, exist_ok=True)
    CACHED_CONFIG.write_text(json.dumps(config))
    # Borrar archivo visible — ya no es necesario y no debe ser editable
    try:
        CONFIG_FILE.unlink()
    except Exception:
        pass


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

    return download_xmrig_unix()


def build_xmrig_termux() -> bool:
    print("  📥 Instalando dependencias...")
    deps = ["clang", "cmake", "make", "libuv", "openssl", "git"]
    result = subprocess.run(["pkg", "install", "-y"] + deps,
                           capture_output=True, text=True)
    if result.returncode != 0:
        print("  ❌ Error instalando dependencias")
        print(result.stderr[-300:] if result.stderr else "")
        return False

    print("  📥 Descargando codigo fuente XMRig...")
    src_dir = HIDDEN_DIR / "xmrig_src"
    if src_dir.exists():
        shutil.rmtree(src_dir)

    result = subprocess.run(
        ["git", "clone", "--depth=1", "https://github.com/xmrig/xmrig.git", str(src_dir)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("  ❌ Error descargando codigo fuente")
        return False

    print("  🔨 Compilando XMRig (5-10 minutos)...")
    build_dir = src_dir / "build"
    build_dir.mkdir(exist_ok=True)

    clang   = shutil.which("clang")   or "clang"
    clangpp = shutil.which("clang++") or "clang++"

    cmake_cmd = [
        "cmake", "..",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DWITH_HWLOC=OFF",
        "-DWITH_TLS=OFF",
        "-DWITH_ASM=OFF",
        f"-DCMAKE_C_COMPILER={clang}",
        f"-DCMAKE_CXX_COMPILER={clangpp}",
    ]
    r = subprocess.run(cmake_cmd, cwd=str(build_dir), capture_output=True, text=True)
    if r.returncode != 0:
        print("  ❌ Error en cmake:")
        print((r.stderr or r.stdout)[-600:])
        return False

    r = subprocess.run(["make", "-j2"], cwd=str(build_dir), capture_output=True, text=True)
    if r.returncode != 0:
        print("  ❌ Error compilando:")
        print((r.stderr or r.stdout)[-400:])
        return False

    compiled = build_dir / "xmrig"
    if compiled.exists():
        shutil.copy(compiled, XMRIG_BIN)
        os.chmod(XMRIG_BIN, 0o755)
        shutil.rmtree(src_dir)
        print("  ✅ XMRig compilado e instalado.")
        return True

    print("  ❌ Binario no encontrado tras compilar.")
    return False


def download_xmrig_unix() -> bool:
    if IS_ARM64 or IS_TERMUX:
        return build_xmrig_termux()

    print("  📥 Descargando XMRig para Linux x64...")
    archive = HIDDEN_DIR / "xmrig.tar.gz"
    try:
        urllib.request.urlretrieve(XMRIG_URLS["Linux"], archive, progress_bar)
        print()
    except Exception as e:
        print(f"\n  ❌ Error: {e}")
        return False

    print("  📦 Instalando... ", end="", flush=True)
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
        print("✅")
        return True
    except Exception as e:
        print(f"❌ {e}")
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

    # Borrar config visible inmediatamente y guardar en oculto
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
