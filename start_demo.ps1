param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8765,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$pythonCommand = Get-Command -Name python -ErrorAction SilentlyContinue
if ($null -eq $pythonCommand) {
    Write-Host "ERROR: Python was not found on PATH. Select the project Python environment and rerun; no packages were installed." -ForegroundColor Red
    exit 1
}

& $pythonCommand.Source -c "import numpy"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: The selected Python is missing required NumPy. Activate the project environment and install dependencies manually; this launcher never runs pip." -ForegroundColor Red
    exit 2
}

$portInUse = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
if ($portInUse) {
    Write-Host "ERROR: Port $Port is already in use on localhost. Open http://127.0.0.1:$Port/ if it is the demo, or choose another port with -Port (for example -Port 8766)." -ForegroundColor Red
    exit 3
}

$address = "http://127.0.0.1:$Port/"
Write-Host "HF-TCM-SIM deterministic defense demo: $address"
Write-Host "This launches only the existing localhost GUI. No simulation runs until you explicitly start the demo in the browser."

$launchArgs = @("-m", "hf_tcm.demo_studio", "--host", "127.0.0.1", "--port", "$Port")
if ($NoBrowser) {
    $launchArgs += "--no-browser"
}

& $pythonCommand.Source @launchArgs
exit $LASTEXITCODE
