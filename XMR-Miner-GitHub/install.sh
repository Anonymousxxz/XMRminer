#!/bin/bash
# install.sh — Instalador Linux/Android para MinerXMR
# La config ya fue escrita en ~/.xmr_miner/miner_config.dat por el comando del bot

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
echo -e "${YELLOW}  Verificando dependencias...${NC}"
if $IS_TERMUX; then
    command -v python &>/dev/null || pkg install -y python
    command -v curl   &>/dev/null || pkg install -y curl
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
