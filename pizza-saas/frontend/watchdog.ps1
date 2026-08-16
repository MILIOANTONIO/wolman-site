# Controlla ogni 10 secondi se il frontend risponde su :3000; se non
# risponde (o risponde con errore 500, tipico di una cache .next corrotta)
# lo riavvia da zero. Solo per lo sviluppo in locale.
$frontendDir = "C:\Users\anton\claude project\pizza-saas\frontend"
$nodeExe = "C:\Program Files\nodejs\node.exe"
$logFile = "$frontendDir\watchdog.log"

function Write-Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

# Ritorna "ok", "down" (nessuna risposta: server spento) oppure "broken"
# (risponde ma con 500 - quasi sempre .next corrotta da un riavvio andato
# male o da più istanze partite in contemporanea sulla stessa cartella).
function Test-Frontend {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:3000" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        return "ok"
    } catch [System.Net.WebException] {
        if ($_.Exception.Response) {
            $code = [int]$_.Exception.Response.StatusCode
            if ($code -ge 500) { return "broken" }
            return "ok"  # 4xx e' comunque il server vivo che risponde
        }
        return "down"
    } catch {
        return "down"
    }
}

function Stop-AllFrontendInstances {
    # Soluzione definitiva: invece di riconoscere i processi dal testo del
    # comando (fragile - un processo avviato in un altro modo, tipo dal
    # tool di preview del browser, poteva sfuggire al controllo e restare
    # in ascolto sulla porta, facendo ripartire i riavvii successivi su
    # porte diverse tipo 3001/3003 senza che ce ne accorgessimo), chiudiamo
    # QUALUNQUE processo risulti in ascolto sulla porta 3000, chiunque sia.
    $pids = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($p in $pids) {
        Write-Log "Chiudo processo sulla porta 3000 (PID $p)"
        Stop-Process -Id $p -Force -Confirm:$false -ErrorAction SilentlyContinue
    }
    # Rete di sicurezza aggiuntiva: chiude anche qualunque "next dev" di
    # questo progetto rimasto vivo ma non ancora in ascolto (in fase di
    # avvio/compilazione), cosi' non ne restano due a scontrarsi su .next.
    Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*next*" -and $_.CommandLine -like "*pizza-saas*frontend*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

function Start-Frontend {
    param([switch]$ClearCache)

    Stop-AllFrontendInstances

    if ($ClearCache) {
        $nextDir = Join-Path $frontendDir ".next"
        if (Test-Path $nextDir) {
            Write-Log "Cache .next corrotta, la elimino prima di ripartire"
            Remove-Item -Recurse -Force $nextDir -ErrorAction SilentlyContinue
        }
    }

    Write-Log "Avvio frontend..."
    Start-Process -FilePath $nodeExe `
        -ArgumentList "node_modules\next\dist\bin\next", "dev" `
        -WorkingDirectory $frontendDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$frontendDir\next_watchdog_out.log" `
        -RedirectStandardError "$frontendDir\next_watchdog_err.log"
}

Write-Log "Watchdog frontend avviato (controllo ogni 10 secondi)."
while ($true) {
    $state = Test-Frontend
    if ($state -eq "down") {
        Start-Frontend
        Start-Sleep -Seconds 8
    } elseif ($state -eq "broken") {
        Start-Frontend -ClearCache
        Start-Sleep -Seconds 8
    }
    Start-Sleep -Seconds 10
}
