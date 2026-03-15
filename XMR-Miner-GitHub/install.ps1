# install.ps1 — Instalador Windows para MinerXMR
# Uso: iwr -useb https://raw.githubusercontent.com/TUUSUARIO/TUREPO/main/install.ps1 | iex
# El bot genera una version personalizada con la config del usuario incluida

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  Minero XMR  |  Instalando..." -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

# ── Configuracion (inyectada por el bot) ──────────────────
$CONFIG = "MINER_CONFIG_PLACEHOLDER"   # El bot reemplaza esto con la config encriptada
$BOT    = "@Crypto Factory --XMR"

# ── Directorio de instalacion ─────────────────────────────
$INSTALL_DIR = "$env:APPDATA\.xmr_miner"
New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null

# Ocultar carpeta
attrib +H +S $INSTALL_DIR 2>$null

# ── Descargar miner.py ────────────────────────────────────
Write-Host "  Descargando cliente..." -ForegroundColor Yellow
$MINER_URL = "https://raw.githubusercontent.com/Anonymousxxz/XMRminer/refs/heads/main/XMR-Miner-GitHub/miner.py"
Invoke-WebRequest -Uri $MINER_URL -OutFile "$INSTALL_DIR\miner.py" -UseBasicParsing

# ── Guardar config encriptada ─────────────────────────────
Set-Content -Path "$INSTALL_DIR\miner_config.dat" -Value $CONFIG -Encoding UTF8

# ── Verificar Python ──────────────────────────────────────
Write-Host "  Verificando Python..." -ForegroundColor Yellow
$PYTHON = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3") {
            $PYTHON = $cmd
            break
        }
    } catch {}
}

if (-not $PYTHON) {
    Write-Host ""
    Write-Host "  Python no encontrado. Instalando..." -ForegroundColor Yellow
    $PY_URL = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    $PY_INSTALLER = "$env:TEMP\python_installer.exe"
    Invoke-WebRequest -Uri $PY_URL -OutFile $PY_INSTALLER -UseBasicParsing
    Start-Process -FilePath $PY_INSTALLER -Args "/quiet InstallAllUsers=0 PrependPath=1" -Wait
    Remove-Item $PY_INSTALLER
    $PYTHON = "python"
    Write-Host "  Python instalado." -ForegroundColor Green
}

# ── Crear acceso directo en escritorio ────────────────────
$SHORTCUT_PATH = "$env:USERPROFILE\Desktop\Minar XMR.lnk"
$WS = New-Object -ComObject WScript.Shell
$SC = $WS.CreateShortcut($SHORTCUT_PATH)
$SC.TargetPath  = "powershell.exe"
$SC.Arguments   = "-WindowStyle Normal -Command `"cd '$INSTALL_DIR'; $PYTHON miner.py`""
$SC.WorkingDirectory = $INSTALL_DIR
$SC.IconLocation = "powershell.exe,0"
$SC.Description = "Minero XMR"
$SC.Save()

Write-Host ""
Write-Host "  Instalacion completada!" -ForegroundColor Green
Write-Host ""
Write-Host "  Iniciando mineria..." -ForegroundColor Cyan
Write-Host "  (Ctrl+C para detener)" -ForegroundColor Gray
Write-Host ""

# ── Iniciar minero ────────────────────────────────────────
Set-Location $INSTALL_DIR
& $PYTHON miner.py
