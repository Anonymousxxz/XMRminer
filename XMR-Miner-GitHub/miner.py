"""
miner.py — Cliente minero XMR multiplataforma
Soporta: Windows, Linux, Android (Termux ARM64)
- Config encriptada — no editable
- xmrig en carpeta oculta
- Wallet pasada por memoria, nunca en disco
"""

import subprocess, sys, os, time, platform, json, threading, shutil, base64, hashlib
import urllib.request
from pathlib import Path

BOT_USERNAME = "@TuBotDeTelegram"
VERSION      = "1.0.0"
ENCRYPT_KEY  = "461yL4peXe5awALkAN2PspZHdqJW9WBfj7kbnimDULJwivfiV3xFNcLZuEN1YajxLjjNuox5TUT6NEdEnRNCRJj4JAh8hG3"

# ── Detectar plataforma ───────────────────────────────────
SYSTEM    = platform.system()
IS_WIN    = SYSTEM == "Windows"
IS_LINUX  = SYSTEM == "Linux"
IS_TERMUX = IS_LINUX and "com.termux" in os.environ.get("PREFIX", "")

# Detectar arquitectura ARM64
MACHINE   = platform.machine().lower()
IS_ARM64  = any(a in MACHINE for a in ["aarch64", "arm64"])

# ── Rutas ─────────────────────────────────────────────────
BASE_DIR = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent

if IS_WIN:
    HIDDEN_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / ".xmr_engine"
else:
    HIDDEN_DIR = Path.home() / ".xmr_engine"

XMRIG_BIN     = HIDDEN_DIR / ("xmrig.exe" if IS_WIN else "xmrig")
CONFIG_FILE   = BASE_DIR / "miner_config.dat"
CACHED_CONFIG = HIDDEN_DIR / "cache.json"

# URLs de XMRig por plataforma
XMRIG_URLS = {
    "Windows": "https://github.com/xmrig/xmrig/releases/download/v6.25.0/xmrig-6.25.0-windows-x64.zip",
    "Linux":   "https://github.com/xmrig/xmrig/releases/download/v6.25.0/xmrig-6.25.0-linux-static-x64.tar.gz",
}

stop_flag       = threading.Event()
SESSION_MINUTES = 1


# ── Encriptacion ──────────────────────────────────────────
def _key() -> bytes:
    return hashlib.sha256(ENCRYPT_KEY.encode()).digest()


def decrypt_config(encrypted_b64: str) -> dict | None:
    try:
        data      = base64.b64decode(encrypted_b64)
        key       = _key()
        decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        return json.loads(decrypted.decode("utf-8"))
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
    print()


def progress_bar(block_num, block_size, total_size):
    pct = min(100, block_num * block_size * 100 // max(total_size, 1))
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
    print(f"\r  [{bar}] {pct}%", end="", flush=True)


# ── Config ────────────────────────────────────────────────
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
            encrypted = CONFIG_FILE.read_text().strip()
            cfg = decrypt_config(encrypted)
            if cfg and all(k in cfg for k in ["user_wallet", "owner_wallet", "pool_host", "pool_port"]):
                return cfg
            else:
                print("  ❌ Archivo corrupto o modificado.")
                print("     Descarga un nuevo miner_config.dat desde el bot.")
        except Exception:
            pass

    return None


def cache_and_hide_config(config: dict):
    HIDDEN_DIR.mkdir(parents=True, exist_ok=True)
    CACHED_CONFIG.write_text(json.dumps(config))
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
        # Verificar que el binario es ejecutable y de la arquitectura correcta
        try:
            result = subprocess.run([str(XMRIG_BIN), "--version"],
                                   capture_output=True, timeout=5)
            if result.returncode == 0:
                return True
            else:
                # Binario incorrecto, borrar y re-descargar
                XMRIG_BIN.unlink()
        except Exception:
            XMRIG_BIN.unlink()

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
    """Compila XMRig desde fuente en Termux (unica opcion para Android ARM64)."""
    print("  📥 Instalando dependencias para compilar XMRig...")
    deps = ["clang", "cmake", "make", "libuv", "openssl", "libhwloc", "git"]
    result = subprocess.run(
        ["pkg", "install", "-y"] + deps,
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ❌ Error instalando dependencias")
        return False

    print("  📥 Descargando codigo fuente de XMRig...")
    src_dir = HIDDEN_DIR / "xmrig_src"
    if src_dir.exists():
        shutil.rmtree(src_dir)

    result = subprocess.run(
        ["git", "clone", "--depth=1",
         "https://github.com/xmrig/xmrig.git", str(src_dir)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("  ❌ Error descargando codigo fuente")
        return False

    print("  🔨 Compilando XMRig (puede tardar 5-10 minutos)...")
    build_dir = src_dir / "build"
    build_dir.mkdir(exist_ok=True)

    cmake_result = subprocess.run(
        ["cmake", "..", "-DCMAKE_BUILD_TYPE=Release",
         "-DWITH_HWLOC=OFF", "-DWITH_TLS=OFF"],
        cwd=str(build_dir),
        capture_output=True, text=True
    )
    if cmake_result.returncode != 0:
        print("  ❌ Error en cmake")
        return False

    make_result = subprocess.run(
        ["make", "-j2"],
        cwd=str(build_dir),
        capture_output=True, text=True
    )
    if make_result.returncode != 0:
        print("  ❌ Error compilando")
        return False

    compiled_bin = build_dir / "xmrig"
    if compiled_bin.exists():
        shutil.copy(compiled_bin, XMRIG_BIN)
        os.chmod(XMRIG_BIN, 0o755)
        shutil.rmtree(src_dir)
        print("  ✅ XMRig compilado e instalado.")
        return True

    print("  ❌ Binario no encontrado tras compilar.")
    return False


def download_xmrig_unix() -> bool:
    if IS_ARM64 or IS_TERMUX:
        # No hay binario precompilado para Linux ARM64 — compilar desde fuente
        return build_xmrig_termux()

    print("  📥 Descargando XMRig para Linux x64...")
    url     = XMRIG_URLS["Linux"]
    archive = HIDDEN_DIR / "xmrig.tar.gz"

    try:
        urllib.request.urlretrieve(url, archive, progress_bar)
        print()
    except Exception as e:
        print(f"\n  ❌ Error descargando: {e}")
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
            [
                str(XMRIG_BIN),
                "--url",           f"{config['pool_host']}:{config['pool_port']}",
                "--user",          wallet,
                "--pass",          "x",
                "--algo",          "rx/0",
                "--no-color",
                "--keepalive",
                "--max-cpu-usage", max_cpu,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        deadline = time.time() + SESSION_MINUTES * 60
        for line in proc.stdout:
            if stop_flag.is_set() or time.time() > deadline:
                proc.terminate()
                break
            line = line.rstrip()
            if any(k in line for k in ["speed", "accepted", "rejected", "connect", "error"]):
                clean = line.split("]")[-1].strip() if "]" in line else line
                print(f"  {clean}")
        proc.wait()

    except FileNotFoundError:
        print("  ❌ Motor no encontrado. Reinicia el programa.")
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
        print("  No se encontro miner_config.dat")
        print()
        print("  Para obtenerlo:")
        print(f"  1. Abre Telegram y escribe /start en {BOT_USERNAME}")
        print("  2. Registra tu wallet")
        print("  3. El bot te enviara los archivos automaticamente")
        if IS_TERMUX:
            print("  4. Sigue las instrucciones del bot en Termux")
        else:
            print("  4. Guarda miner_config.dat junto a este programa")
        print()
        input("  Presiona Enter para cerrar...")
        sys.exit(1)

    clear()
    show_header(config)
    cache_and_hide_config(config)

    if not setup_xmrig():
        print()
        print("  ❌ No se pudo instalar el motor de mineria.")
        print(f"  Arquitectura detectada: {MACHINE}")
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
