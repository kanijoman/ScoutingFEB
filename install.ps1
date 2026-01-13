# Instalación de Dependencias - ScoutingFEB

Write-Host "=== Instalación de ScoutingFEB ===" -ForegroundColor Green
Write-Host ""

# Verificar Python
Write-Host "Verificando Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ $pythonVersion encontrado" -ForegroundColor Green
} catch {
    Write-Host "✗ Python no encontrado. Por favor, instala Python 3.8 o superior." -ForegroundColor Red
    exit 1
}

# Verificar pip
Write-Host "Verificando pip..." -ForegroundColor Yellow
try {
    $pipVersion = pip --version 2>&1
    Write-Host "✓ pip encontrado" -ForegroundColor Green
} catch {
    Write-Host "✗ pip no encontrado. Por favor, instala pip." -ForegroundColor Red
    exit 1
}

# Verificar MongoDB
Write-Host ""
Write-Host "Verificando MongoDB..." -ForegroundColor Yellow
$mongoService = Get-Service -Name MongoDB -ErrorAction SilentlyContinue
if ($mongoService) {
    if ($mongoService.Status -eq 'Running') {
        Write-Host "✓ MongoDB está ejecutándose" -ForegroundColor Green
    } else {
        Write-Host "⚠ MongoDB está instalado pero no está ejecutándose" -ForegroundColor Yellow
        Write-Host "  Intentando iniciar MongoDB..." -ForegroundColor Yellow
        try {
            Start-Service -Name MongoDB
            Write-Host "✓ MongoDB iniciado correctamente" -ForegroundColor Green
        } catch {
            Write-Host "✗ No se pudo iniciar MongoDB. Inícialo manualmente con: net start MongoDB" -ForegroundColor Red
        }
    }
} else {
    Write-Host "⚠ MongoDB no está instalado como servicio" -ForegroundColor Yellow
    Write-Host "  Descarga MongoDB desde: https://www.mongodb.com/try/download/community" -ForegroundColor Yellow
    Write-Host "  O instala con Chocolatey: choco install mongodb" -ForegroundColor Yellow
}

# Instalar dependencias de Python
Write-Host ""
Write-Host "Instalando dependencias de Python..." -ForegroundColor Yellow
pip install -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Dependencias instaladas correctamente" -ForegroundColor Green
} else {
    Write-Host "✗ Error al instalar dependencias" -ForegroundColor Red
    exit 1
}

# Resumen
Write-Host ""
Write-Host "=== Instalación completada ===" -ForegroundColor Green
Write-Host ""
Write-Host "Para ejecutar el scraper:" -ForegroundColor Cyan
Write-Host "  cd src" -ForegroundColor White
Write-Host "  python main.py" -ForegroundColor White
Write-Host ""
Write-Host "Para más información, consulta el README.md" -ForegroundColor Cyan
Write-Host ""
