param([int]$Porta = 8766)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$WebBuild = Join-Path $FrontendRoot "build\web\index.html"
$Url = "http://127.0.0.1:$Porta"
$LogDir = Join-Path $ProjectRoot "output"
Set-Location -LiteralPath $ProjectRoot

function Get-PythonRuntime {
    $Python = Get-Command python -ErrorAction SilentlyContinue
    if ($Python) { return @{ FilePath = $Python.Source; Prefix = @() } }
    $Launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($Launcher) { return @{ FilePath = $Launcher.Source; Prefix = @("-3") } }
    throw "Python 3 não foi encontrado."
}

function Get-FlutterRuntime {
    $Flutter = Get-Command flutter -ErrorAction SilentlyContinue
    if ($Flutter) { return $Flutter.Source }
    $WorkspaceRoot = Split-Path -Parent (Split-Path -Parent $ProjectRoot)
    $Bundled = Join-Path $WorkspaceRoot "PROJETOS FLUTTER\flutter\bin\flutter.bat"
    if (Test-Path -LiteralPath $Bundled) { return $Bundled }
    throw "Flutter não foi encontrado."
}

function Get-EngineDocSession {
    try { return Invoke-RestMethod -Uri "$Url/health" -Method Get -TimeoutSec 2 }
    catch { return $null }
}

$PythonRuntime = Get-PythonRuntime
$FlutterRuntime = Get-FlutterRuntime
$NeedsBuild = -not (Test-Path -LiteralPath $WebBuild)
if (-not $NeedsBuild) {
    $BuildTime = (Get-Item -LiteralPath $WebBuild).LastWriteTimeUtc
    $SourceFolders = @((Join-Path $FrontendRoot "lib"), (Join-Path $FrontendRoot "web"))
    $NewerSource = Get-ChildItem -LiteralPath $SourceFolders -File -Recurse | Where-Object { $_.LastWriteTimeUtc -gt $BuildTime } | Select-Object -First 1
    $NeedsBuild = $null -ne $NewerSource -or (Get-Item -LiteralPath (Join-Path $FrontendRoot "pubspec.yaml")).LastWriteTimeUtc -gt $BuildTime
}

if ($NeedsBuild) {
    Write-Host "[app] Preparando a interface para o navegador..."
    Set-Location -LiteralPath $FrontendRoot
    & $FlutterRuntime pub get
    if ($LASTEXITCODE -ne 0) { throw "Falha ao preparar as dependências Flutter." }
    & $FlutterRuntime build web --release --no-web-resources-cdn
    if ($LASTEXITCODE -ne 0) { throw "Falha ao construir a interface web." }
    Set-Location -LiteralPath $ProjectRoot
}

$Session = Get-EngineDocSession
if ($Session -and ($Session.root -ne $ProjectRoot -or $Session.web -ne $true)) { throw "A porta $Porta está ocupada por outro serviço." }
if (-not $Session) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    $Arguments = @()
    $Arguments += $PythonRuntime.Prefix
    $Arguments += @("-u", "desktop_backend.py", "--port", "$Porta")
    $Process = Start-Process -FilePath $PythonRuntime.FilePath -ArgumentList $Arguments -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $LogDir "desktop-backend.log") -RedirectStandardError (Join-Path $LogDir "desktop-backend-error.log") -PassThru
    $Ready = $false
    for ($Attempt = 0; $Attempt -lt 60; $Attempt++) {
        if ($Process.HasExited) { throw "O serviço não iniciou. Consulte output\desktop-backend-error.log." }
        $Session = Get-EngineDocSession
        if ($Session -and $Session.root -eq $ProjectRoot -and $Session.web -eq $true) { $Ready = $true; break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $Ready) { throw "O serviço local não respondeu no tempo esperado." }
}
Write-Host "[app] Abrindo Engine Doc Power BI no navegador..."
Start-Process $Url
