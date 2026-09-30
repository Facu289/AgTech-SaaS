# =========================================================
# reorganizar.ps1 - Termina de ordenar AgroApp en carpetas. Se corre UNA vez.
#
#   1. Frena si el backend o el bot estan corriendo.
#   2. Mueve la base y los backups a la carpeta datos/ (copia, verifica, y recien ahi borra).
#   3. Borra los archivos viejos de la raiz y static/ (solo si su reemplazo nuevo existe).
#   4. Corre los tests para confirmar que todo anda.
#
# Uso (desde la carpeta agroapp):
#   powershell -ExecutionPolicy Bypass -File reorganizar.ps1
# Se puede correr de nuevo sin problema: lo que ya esta hecho, lo saltea.
# =========================================================
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Paso($texto) { Write-Host "`n== $texto" -ForegroundColor Cyan }
function Ok($texto) { Write-Host "   OK  $texto" -ForegroundColor Green }
function Aviso($texto) { Write-Host "   --  $texto" -ForegroundColor DarkGray }
function Frenar($texto) {
    Write-Host "`n   ERROR: $texto" -ForegroundColor Red
    Write-Host "   No se cambio nada mas. Corregilo y volve a correr el script." -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------
Paso "1) Controles"

# El backend y el bot tienen que estar apagados (para poder mover la base).
try {
    $corriendo = Get-CimInstance Win32_Process |
        Where-Object { $_.CommandLine -and $_.CommandLine -match "uvicorn|bot\.py" -and $_.ProcessId -ne $PID }
} catch {
    $corriendo = $null  # Si no se puede consultar, seguimos (el paso de la base igual controla).
}
if ($corriendo) {
    Frenar "El backend o el bot estan corriendo. Frenalos (Ctrl+C en cada terminal) y volve a correr el script."
}
Ok "Backend y bot apagados"

# Los archivos nuevos tienen que estar.
$nuevos = @("app/main.py", "app/nucleo/database.py", "app/insumos/db.py", "bot/bot.py",
            "web/index.html", "web/css/estilos.css", "web/js/comun.js", "docs/PROJECT_CONTEXT.md", "README.md")
foreach ($f in $nuevos) {
    if (-not (Test-Path $f)) { Frenar "Falta $f. Los archivos nuevos no estan completos." }
}
Ok "Los archivos nuevos estan todos"

# ---------------------------------------------------------
Paso "2) Base de datos y backups -> datos/"

New-Item -ItemType Directory -Force -Path "datos/backups" | Out-Null

if ((Test-Path "agroapp.db") -and (Test-Path "datos/agroapp.db")) {
    # Si son identicas, es que la copia ya se hizo en una corrida anterior: borramos la de la raiz.
    if ((Get-FileHash "agroapp.db").Hash -eq (Get-FileHash "datos/agroapp.db").Hash) {
        Remove-Item "agroapp.db" -Force
        Ok "agroapp.db de la raiz borrada (ya estaba copiada igual en datos/)"
    } else {
        Frenar "Hay DOS bases distintas: agroapp.db (raiz) y datos/agroapp.db. Revisa cual es la buena antes de seguir."
    }
}

if (Test-Path "agroapp.db") {
    # Copia extra de seguridad, por las dudas.
    $fecha = Get-Date -Format "yyyy-MM-dd_HHmmss"
    Copy-Item "agroapp.db" "datos/backups/agroapp_antes_de_reorganizar_$fecha.db"
    # Copiar, comprobar que la copia es identica, y recien ahi borrar la original.
    Copy-Item "agroapp.db" "datos/agroapp.db"
    $original = (Get-FileHash "agroapp.db").Hash
    $copia = (Get-FileHash "datos/agroapp.db").Hash
    if ($original -ne $copia) {
        Remove-Item "datos/agroapp.db" -Force
        Frenar "La copia de la base no quedo igual a la original. No se borro nada."
    }
    Remove-Item "agroapp.db" -Force
    foreach ($extra in @("agroapp.db-journal", "agroapp.db-wal", "agroapp.db-shm")) {
        if (Test-Path $extra) { Move-Item $extra "datos/$extra" }
    }
    Ok "agroapp.db -> datos/agroapp.db (copia verificada)"
} elseif (Test-Path "datos/agroapp.db") {
    Aviso "La base ya estaba en datos/"
} else {
    Aviso "No hay base de datos todavia (se crea sola al arrancar)"
}

if (Test-Path "backups") {
    $cantidad = 0
    foreach ($archivo in Get-ChildItem "backups" -File) {
        $destino = "datos/backups/$($archivo.Name)"
        if (-not (Test-Path $destino)) { Move-Item $archivo.FullName $destino; $cantidad++ }
    }
    if (-not (Get-ChildItem "backups")) { Remove-Item "backups" }
    Ok "$cantidad backup(s) -> datos/backups/"
}

if (Test-Path "agroapp_danada.db") {
    New-Item -ItemType Directory -Force -Path "datos/viejo" | Out-Null
    Move-Item "agroapp_danada.db" "datos/viejo/agroapp_danada.db"
    Ok "agroapp_danada.db -> datos/viejo/"
}
if (Test-Path "Tareas.md") {
    New-Item -ItemType Directory -Force -Path "docs/viejo" | Out-Null
    Move-Item "Tareas.md" "docs/viejo/Tareas.md"
    Ok "Tareas.md -> docs/viejo/"
}

# ---------------------------------------------------------
Paso "3) Archivos viejos (ya tienen su reemplazo en las carpetas nuevas)"

$reemplazos = [ordered]@{
    "main.py" = "app/main.py"; "database.py" = "app/nucleo/database.py"; "backup.py" = "app/nucleo/backup.py"
    "opciones.py" = "app/nucleo/opciones.py"; "tipos.py" = "app/nucleo/tipos.py"; "utilidades.py" = "app/nucleo/utilidades.py"
    "db_maquinaria.py" = "app/maquinaria/db.py"; "db_ganaderia.py" = "app/ganaderia/db.py"
    "insumos.py" = "app/insumos/rutas.py"; "maquinaria.py" = "app/maquinaria/rutas.py"; "ganaderia.py" = "app/ganaderia/rutas.py"
    "exportar.py" = "app/exportar.py"; "lenguaje_natural.py" = "app/telegram/lenguaje_natural.py"; "bot.py" = "bot/bot.py"
    "PROJECT_CONTEXT.md" = "docs/PROJECT_CONTEXT.md"; "ROADMAP.md" = "docs/ROADMAP.md"
}
foreach ($viejo in $reemplazos.Keys) {
    if (Test-Path $viejo) {
        if (Test-Path $reemplazos[$viejo]) { Remove-Item $viejo -Force; Ok "$viejo  (ahora: $($reemplazos[$viejo]))" }
        else { Aviso "$viejo se deja: no esta $($reemplazos[$viejo])" }
    }
}
if (Test-Path "static") {
    # La web entera ahora esta en web/. Controlamos que no falte ninguna pagina antes de borrar.
    foreach ($pagina in Get-ChildItem "static" -Filter "*.html") {
        if (-not (Test-Path "web/$($pagina.Name)")) { Frenar "Falta web/$($pagina.Name): no se borra static/." }
    }
    Remove-Item "static" -Recurse -Force
    Ok "static/  (ahora: web/)"
}
if (Test-Path "__pycache__") { Remove-Item "__pycache__" -Recurse -Force; Ok "__pycache__/ (archivos temporales de Python)" }

# ---------------------------------------------------------
Paso "4) Tests"

$python = if (Test-Path ".venv/Scripts/python.exe") { ".venv/Scripts/python.exe" } else { "python" }
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n   Algun test fallo. Mandale la salida a Claude antes de seguir." -ForegroundColor Yellow
    exit 1
}

# ---------------------------------------------------------
Paso "5) Git"
git add -A
git status --short
Write-Host "`nListo! Ahora:" -ForegroundColor Green
Write-Host "  1. git commit -m `"Reorganizar el proyecto en carpetas`""
Write-Host "  2. Backend:  uvicorn app.main:app --reload"
Write-Host "  3. Bot:      python bot/bot.py"
