<#
.SYNOPSIS
  Despliega AeroAcademy en la VM con un solo comando (PowerShell 7, desde la raíz del repositorio).

.DESCRIPTION
  1. Revisa el estado de git (en main, sin cambios, al día con origin/main).
  2. Opcionalmente corre tools/preflight.py.
  3. Copia private/cursos y private/dgac a la VM, solo si existen.
  4. Entra por SSH (con terminal, para que funcione la contraseña de sudo) y corre
     `sudo aeroacademy actualizar`: respalda, instala, comprueba la salud y, si falla, vuelve atrás solo.

  Conexión: variables de entorno AEROACADEMY_VM_HOST y AEROACADEMY_VM_USER, o el archivo local
  deploy/vm.local.json (ignorado por git; hay un modelo en deploy/vm.local.json.ejemplo):
      { "host": "<IP-DE-LA-VM>", "user": "example" }
  Nunca pongas el host real, la IP ni el usuario en un archivo versionado.

  Para no escribir contraseñas de SSH, usa una llave (equivalente a ssh-copy-id en Windows):
      ssh-keygen -t ed25519
      Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub | ssh example@<IP-DE-LA-VM> "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
  (la contraseña de sudo se sigue pidiendo en la VM: es lo esperado).

.PARAMETER SoloComprobar  Solo mira la salud del servicio en la VM (no cambia nada).
.PARAMETER Revertir       Vuelve a la versión anterior guardada por la última actualización.
.PARAMETER SinPrivados    No copia private/cursos ni private/dgac.
.PARAMETER DryRun         Muestra los comandos sin ejecutarlos.
.PARAMETER Preflight      Corre `python tools/preflight.py` antes de desplegar.
.PARAMETER PublicFunnel   '1' o '0': pasa PUBLIC_FUNNEL a la VM (sin indicar, se conserva lo que ya esté activo).
#>
[CmdletBinding()]
param(
    [switch]$SoloComprobar,
    [switch]$Revertir,
    [switch]$SinPrivados,
    [switch]$DryRun,
    [switch]$Preflight,
    [ValidateSet('', '0', '1')][string]$PublicFunnel = ''
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (& git -C $PSScriptRoot rev-parse --show-toplevel).Trim()
Set-Location $RepoRoot

function Write-Step([string]$Text) { Write-Host "==> $Text" -ForegroundColor Cyan }
function Write-Note([string]$Text) { Write-Host "    $Text" }
function Write-Warn([string]$Text) { Write-Host "    ! $Text" -ForegroundColor Yellow }
function Stop-Deploy([string]$Text) { Write-Host "No se despliega: $Text" -ForegroundColor Red; exit 1 }

# ── Conexión ─────────────────────────────────────────────────────────────────────────────────────────────────
$VmHost = $env:AEROACADEMY_VM_HOST
$VmUser = $env:AEROACADEMY_VM_USER
$LocalFile = Join-Path $RepoRoot 'deploy/vm.local.json'
if ((-not $VmHost -or -not $VmUser) -and (Test-Path $LocalFile)) {
    $cfg = Get-Content -Raw $LocalFile | ConvertFrom-Json
    if (-not $VmHost) { $VmHost = $cfg.host }
    if (-not $VmUser) { $VmUser = $cfg.user }
}
if (-not $VmHost -or -not $VmUser -or $VmHost.StartsWith('<')) {
    Stop-Deploy "falta la conexión. Define AEROACADEMY_VM_HOST y AEROACADEMY_VM_USER, o copia deploy/vm.local.json.ejemplo a deploy/vm.local.json y complétalo."
}
if ($VmHost -notmatch '^[A-Za-z0-9._:-]+$' -or $VmUser -notmatch '^[A-Za-z0-9._-]+$') {
    Stop-Deploy 'el host o el usuario tienen caracteres no permitidos.'
}
$Target = "$VmUser@$VmHost"

function Invoke-Cmd([string]$Display, [scriptblock]$Action) {
    if ($DryRun) { Write-Note "[dry-run] $Display"; return }
    & $Action
    if ($LASTEXITCODE -ne 0) { Stop-Deploy "falló: $Display (código $LASTEXITCODE)." }
}

function Get-FolderSize([string]$Path) {
    $bytes = (Get-ChildItem -LiteralPath $Path -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    if (-not $bytes) { return '0 MB' }
    return ('{0:N1} MB' -f ($bytes / 1MB))
}

# Se llama al script del repositorio (no al atajo `aeroacademy actualizar`, que solo existe después de la primera
# instalación con este flujo). Antes de actualizar se trae el código con `git pull --ff-only`, así el script que
# corre ya es el de la versión nueva.
$Remote = 'sudo ./deploy/actualizar.sh'
$Pull = 'git pull --ff-only && '
if ($Revertir) { $Remote = 'sudo ./deploy/actualizar.sh --revertir'; $Pull = '' }
elseif ($SoloComprobar) { $Remote = 'sudo ./deploy/actualizar.sh --solo-comprobar'; $Pull = '' }
if ($PublicFunnel -ne '' -and -not $Revertir -and -not $SoloComprobar) {
    $Remote = "sudo PUBLIC_FUNNEL=$PublicFunnel ./deploy/actualizar.sh"
}
$RemoteCmd = "cd ~/AeroAcademy && $Pull$Remote"

if ($DryRun) { Write-Warn 'Modo DryRun: no se ejecuta nada.' }

# ── 1. Estado de git ─────────────────────────────────────────────────────────────────────────────────────────
if (-not $SoloComprobar -and -not $Revertir) {
    Write-Step 'Estado de git'
    $branch = (& git rev-parse --abbrev-ref HEAD).Trim()
    if ($branch -ne 'main') { if ($DryRun) { Write-Warn "no estás en main ($branch)" } else { Stop-Deploy "estás en '$branch'; cambia a main." } }
    if (& git status --porcelain --untracked-files=no) {
        if ($DryRun) { Write-Warn 'hay cambios sin confirmar' } else { Stop-Deploy 'hay cambios sin confirmar (git status).' }
    }
    & git fetch origin --quiet
    if ($LASTEXITCODE -ne 0) { Stop-Deploy 'git fetch falló (¿sin red?).' }
    $counts = (& git rev-list --left-right --count 'origin/main...HEAD').Trim() -split '\s+'
    $behind = [int]$counts[0]; $ahead = [int]$counts[1]
    if ($behind -gt 0) { Write-Warn "tu main está $behind commit(s) detrás de origin/main: la VM instalará origin/main, no tu copia local." }
    if ($ahead -gt 0) { Write-Warn "tu main tiene $ahead commit(s) sin subir: la VM NO los verá (git push primero)." }
    if ($behind -eq 0 -and $ahead -eq 0) { Write-Note 'main limpio y al día con origin/main' }
    Write-Note ('commit local: ' + (& git log --oneline -1))

    if ($Preflight) {
        Write-Step 'tools/preflight.py'
        Invoke-Cmd 'python tools/preflight.py' { & python tools/preflight.py }
    }

    # ── 2. Archivos privados (ignorados por git) ─────────────────────────────────────────────────────────────
    if ($SinPrivados) {
        Write-Step 'Archivos privados: omitidos (-SinPrivados)'
    }
    else {
        Write-Step 'Archivos privados (solo los que existen)'
        $copied = 0
        foreach ($name in 'cursos', 'dgac') {
            $dir = Join-Path $RepoRoot "private/$name"
            if (-not (Test-Path -LiteralPath $dir)) { Write-Note "private/$name no existe: se omite"; continue }
            Write-Note "private/$name ($(Get-FolderSize $dir))"
            # tar por ssh: respeta la estructura y solo pide la contraseña de SSH una vez por carpeta.
            $pipe = "tar -C private -cf - $name | ssh $Target `"mkdir -p ~/AeroAcademy/private && tar -C ~/AeroAcademy/private -xf -`""
            Invoke-Cmd $pipe { cmd /c $pipe }
            $copied++
        }
        if ($copied -eq 0) { Write-Note 'nada que copiar' }
    }
}

# ── 3. Actualizar en la VM ───────────────────────────────────────────────────────────────────────────────────
Write-Step "En la VM ($Target): $Remote"
Write-Note 'Te pedirá la contraseña de sudo de la VM (y la de SSH si no usas llave).'
$exit = 0
if ($DryRun) {
    Write-Note "[dry-run] ssh -t $Target `"$RemoteCmd`""
}
else {
    & ssh -t $Target $RemoteCmd
    $exit = $LASTEXITCODE
}

# ── 4. Resumen ───────────────────────────────────────────────────────────────────────────────────────────────
Write-Host ''
if ($DryRun) { Write-Step 'DryRun terminado: no se cambió nada.'; exit 0 }
if ($exit -eq 0) {
    Write-Host 'Listo.' -ForegroundColor Green
    if (-not $SoloComprobar) { Write-Note 'Recarga el navegador con Ctrl+F5 (los estáticos nuevos pueden estar en caché).' }
}
else {
    Write-Host "La VM terminó con código $exit." -ForegroundColor Red
    switch ($exit) {
        1 { Write-Note 'La actualización falló y se restauró la versión anterior (lee el resumen de arriba).' }
        2 { Write-Note 'La reversa también falló: entra por SSH y revisa `journalctl -u centro -n 200 --no-pager`.' }
        3 { Write-Note 'No se cumplió una precondición en la VM (no se cambió nada).' }
        default { Write-Note 'Revisa la salida de arriba.' }
    }
}
Write-Note 'Para no escribir la contraseña de SSH cada vez: ssh-keygen -t ed25519 y copia la llave pública a ~/.ssh/authorized_keys de la VM (ver ayuda: Get-Help ./tools/desplegar.ps1 -Full).'
exit $exit
