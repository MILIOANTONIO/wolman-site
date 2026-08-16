# Controlla ogni 10 secondi se il backend risponde su /api/health; se non
# risponde, lo riavvia. Pensato solo per lo sviluppo in locale - in
# produzione su Render il riavvio automatico e' gia' gestito dalla piattaforma.
$backendDir = "C:\Users\anton\claude project\pizza-saas\backend"
$pythonExe = "$backendDir\venv\Scripts\python.exe"
$logFile = "$backendDir\watchdog.log"

function Write-Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

function Test-Backend {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8000/api/health" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        return $resp.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Stop-AllBackendInstances {
    # Soluzione definitiva: invece di riconoscere i processi dal testo del
    # comando (fragile - python diversi, venv vs sistema, o processi avviati
    # in modo diverso potevano sfuggire al controllo), chiudiamo QUALUNQUE
    # processo risulti in ascolto sulla porta 8000, chiunque sia.
    $pids = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($p in $pids) {
        Write-Log "Chiudo processo sulla porta 8000 (PID $p)"
        Stop-Process -Id $p -Force -Confirm:$false -ErrorAction SilentlyContinue
    }
    # Rete di sicurezza aggiuntiva: chiude anche qualunque uvicorn di questo
    # progetto rimasto vivo ma non ancora in ascolto (in fase di avvio).
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*uvicorn*app.main*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

function Start-Backend {
    Stop-AllBackendInstances
    Write-Log "Avvio backend..."
    Start-Process -FilePath $pythonExe `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000" `
        -WorkingDirectory $backendDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$backendDir\uvicorn_watchdog_out.log" `
        -RedirectStandardError "$backendDir\uvicorn_watchdog_err.log"
}

Write-Log "Watchdog avviato (controllo ogni 10 secondi)."
while ($true) {
    if (-not (Test-Backend)) {
        Start-Backend
        Start-Sleep -Seconds 8  # tempo per l'avvio prima di ricontrollare
    }
    Start-Sleep -Seconds 10
}
