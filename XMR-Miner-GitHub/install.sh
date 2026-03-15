#!/bin/bash
# install.sh — Instalador Linux/Android para MinerXMR

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}=======================================================${NC}"
echo -e "${CYAN}  Minero XMR  |  Instalando...${NC}"
echo -e "${CYAN}=======================================================${NC}"
echo ""

# ── Detectar entorno ──────────────────────────────────────
IS_TERMUX=false
if [ -n "$PREFIX" ] && echo "$PREFIX" | grep -q "com.termux"; then
    IS_TERMUX=true
fi

# ── Directorio de instalacion ─────────────────────────────
INSTALL_DIR="$HOME/.xmr_miner"
mkdir -p "$INSTALL_DIR"

# ── Verificar que la config existe ────────────────────────
if [ ! -s "$INSTALL_DIR/miner_config.dat" ]; then
    echo "  Error: miner_config.dat no encontrado o vacio."
    exit 1
fi

echo -e "${GREEN}  Config encontrada.${NC}"

# ── Dependencias ──────────────────────────────────────────
echo -e "${YELLOW}  Instalando dependencias...${NC}"
if $IS_TERMUX; then
    command -v python &>/dev/null || pkg install -y python
    command -v curl   &>/dev/null || pkg install -y curl
    command -v git    &>/dev/null || pkg install -y git
    command -v cmake  &>/dev/null || pkg install -y cmake
    command -v make   &>/dev/null || pkg install -y make
    command -v clang  &>/dev/null || pkg install -y clang
    pkg install -y libuv libuv-static openssl 2>/dev/null
else
    command -v python3 &>/dev/null || sudo apt-get install -y python3 curl -qq
fi

# ── Descargar miner.py ────────────────────────────────────
echo -e "${YELLOW}  Descargando cliente...${NC}"
MINER_URL="https://raw.githubusercontent.com/Anonymousxxz/XMRminer/refs/heads/main/XMR-Miner-GitHub/miner.py"
curl -sSL "$MINER_URL" -o "$INSTALL_DIR/miner.py"

if [ ! -f "$INSTALL_DIR/miner.py" ]; then
    echo "  Error descargando miner.py"
    exit 1
fi

# ── Compilar XMRig en Termux (solo primera vez) ───────────
XMRIG_BIN="$HOME/.xmr_engine/xmrig"
if $IS_TERMUX && [ ! -f "$XMRIG_BIN" ]; then
    mkdir -p "$HOME/.xmr_engine"
    echo -e "${YELLOW}  Compilando XMRig para Android (5-10 min)...${NC}"
    echo -e "  No cierres Termux hasta que termine."

    SRC_DIR="$HOME/.xmr_engine/xmrig_src"
    rm -rf "$SRC_DIR"

    git clone --depth=1 https://github.com/xmrig/xmrig.git "$SRC_DIR" 2>&1 | tail -3

    mkdir -p "$SRC_DIR/build"
    cd "$SRC_DIR/build"

    cmake .. -DWITH_HWLOC=OFF -DWITH_TLS=OFF 2>&1 | tail -5

    make -j2 2>&1 | tail -5

    # El binario compilado se llama xmrig-notls en Termux
    if [ -f "$SRC_DIR/build/xmrig-notls" ]; then
        cp "$SRC_DIR/build/xmrig-notls" "$XMRIG_BIN"
        chmod +x "$XMRIG_BIN"
        rm -rf "$SRC_DIR"
        echo -e "${GREEN}  XMRig compilado correctamente.${NC}"
    elif [ -f "$SRC_DIR/build/xmrig" ]; then
        cp "$SRC_DIR/build/xmrig" "$XMRIG_BIN"
        chmod +x "$XMRIG_BIN"
        rm -rf "$SRC_DIR"
        echo -e "${GREEN}  XMRig compilado correctamente.${NC}"
    else
        echo "  Error: binario no encontrado tras compilar."
        exit 1
    fi

    cd "$INSTALL_DIR"
fi

# ── Autostart solo en Linux ───────────────────────────────
if ! $IS_TERMUX && command -v systemctl &>/dev/null; then
    read -p "  Iniciar automaticamente al arrancar? [s/N]: " AUTOSTART
    if [[ "$AUTOSTART" =~ ^[Ss]$ ]]; then
        PYTHON_BIN=$(command -v python3)
        sudo bash -c "cat > /etc/systemd/system/xmr-miner.service" << EOF
[Unit]
Description=XMR Miner
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$PYTHON_BIN $INSTALL_DIR/miner.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        sudo systemctl daemon-reload
        sudo systemctl enable xmr-miner
        echo -e "${GREEN}  Autostart configurado.${NC}"
    fi
fi

echo ""
echo -e "${GREEN}  Instalacion completada!${NC}"
echo ""
echo -e "${CYAN}  Iniciando mineria...${NC}"
echo -e "  (Ctrl+C para detener)"
echo ""

# ── Iniciar minero ────────────────────────────────────────
cd "$INSTALL_DIR"
if $IS_TERMUX; then
    python miner.py
else
    python3 miner.py
fi
