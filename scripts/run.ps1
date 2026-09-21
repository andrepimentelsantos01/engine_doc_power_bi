param(
    [switch]$SkipAI
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FixedPort = 8765

Set-Location -LiteralPath $ProjectRoot

$EngineArguments = @(
    "main.py",
    "--input", "input",
    "--output", "output",
    "--serve",
    "--port", $FixedPort
)
if ($SkipAI) {
    $EngineArguments += "--skip-ai"
}

$PortProcesses = @(
    & "$env:SystemRoot\System32\netstat.exe" -ano -p TCP |
        ForEach-Object {
            $Fields = ($_ -split '\s+') | Where-Object { $_ }
            if ($Fields.Count -ge 4 -and $Fields[0] -eq "TCP" -and $Fields[1] -match "[:.]$FixedPort$") {
                $CandidatePid = $Fields[-1]
                if ($CandidatePid -match '^\d+$') { [int]$CandidatePid }
            }
        } |
        Sort-Object -Unique
)

foreach ($PortProcessId in $PortProcesses) {
    if ($PortProcessId -and $PortProcessId -ne $PID) {
        Write-Host "[porta] Encerrando o processo $PortProcessId na porta $FixedPort..."
        Stop-Process -Id $PortProcessId -Force -ErrorAction Stop
    }
}

$Python = Get-Command python -ErrorAction SilentlyContinue
if ($Python) {
    & $Python.Source -c "import requests" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[configuração] Instalando dependências..."
        & $Python.Source -m pip install -r requirements.txt
    }
    & $Python.Source @EngineArguments
    exit $LASTEXITCODE
}

$PythonLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($PythonLauncher) {
    & $PythonLauncher.Source -3 -c "import requests" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[configuração] Instalando dependências..."
        & $PythonLauncher.Source -3 -m pip install -r requirements.txt
    }
    & $PythonLauncher.Source -3 @EngineArguments
    exit $LASTEXITCODE
}

throw "Python 3 não foi encontrado. Instale o Python 3.11 ou mais recente e execute .\start novamente."
