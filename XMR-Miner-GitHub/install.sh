#!/bin/bash
# install.sh — Instalador Linux/Android para MinerXMR
# Uso: curl -sSL https://raw.githubusercontent.com/TUUSUARIO/TUREPO/main/install.sh | bash
# El bot genera una version personalizada con la config del usuario incluida

# ── Configuracion (inyectada por el bot) ──────────────────
CONFIG="MINER_CONFIG_PLACEHOLDER"   # El bot reemplaza esto
BOT="@Crypto Factory --XMR"

# ── Colores ───────────────────────────────────────────────
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

# ── Verificar/instalar dependencias ───────────────────────
echo -e "${YELLOW}  Verificando dependencias...${NC}"

if $IS_TERMUX; then
    # Android/Termux
    if ! command -v python &>/dev/null; then
        echo -e "${YELLOW}  Instalando Python...${NC}"
        pkg install -y python curl
    fi
    if ! command -v curl &>/dev/null; then
        pkg install -y curl
    fi
else
    # Linux
    if ! command -v python3 &>/dev/null; then
        echo -e "${YELLOW}  Instalando Python3...${NC}"
        if command -v apt-get &>/dev/null; then
            sudo apt-get install -y python3 curl -qq
        elif command -v yum &>/dev/null; then
            sudo yum install -y python3 curl -q
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y python3 curl -q
        fi
    fi
fi

# ── Descargar miner.py ────────────────────────────────────
echo -e "${YELLOW}  Descargando cliente...${NC}"
MINER_URL="https://raw.githubusercontent.com/Anonymousxxz/XMRminer/main/miner.py"
curl -sSL "$MINER_URL" -o "$INSTALL_DIR/miner.py"

if [ ! -f "$INSTALL_DIR/miner.py" ]; then
    echo "  Error descargando miner.py"
    exit 1
fi

# ── Guardar config encriptada ─────────────────────────────
echo "$CONFIG" > "$INSTALL_DIR/miner_config.dat"

# ── Configurar autostart (solo Linux, no Termux) ─────────
if ! $IS_TERMUX && command -v systemctl &>/dev/null; then
    read -p "  ¿Iniciar automaticamente al arrancar el sistema? [s/N]: " AUTOSTART
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
