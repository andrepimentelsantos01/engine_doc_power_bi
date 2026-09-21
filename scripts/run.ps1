$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FixedPort = 8765

Set-Location -LiteralPath $ProjectRoot

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
        Write-Host "[port] Stopping PID $PortProcessId on port $FixedPort..."
        Stop-Process -Id $PortProcessId -Force -ErrorAction Stop
    }
}

$Python = Get-Command python -ErrorAction SilentlyContinue
if ($Python) {
    & $Python.Source main.py --input input --output output --serve --port $FixedPort
    exit $LASTEXITCODE
}

$PythonLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($PythonLauncher) {
    & $PythonLauncher.Source -3 main.py --input input --output output --serve --port $FixedPort
    exit $LASTEXITCODE
}

throw "Python 3 was not found. Install Python 3.11 or newer and run .\run.cmd again."
