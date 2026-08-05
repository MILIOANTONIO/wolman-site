"use client";
import { useEffect } from "react";
import { api } from "./api";

const INTERVAL_MS = 60_000;

/** Segnala che questo utente ha la dashboard aperta in questo momento (vedi
 * GET /api/dashboard/team-presence, mostrato nella pagina Statistiche) -
 * un ping al minuto, nessuno stato locale da gestire. */
export function useHeartbeat(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return;
    const ping = () => api.put("/api/dashboard/heartbeat", {}).catch(() => {});
    ping();
    const id = setInterval(ping, INTERVAL_MS);
    return () => clearInterval(id);
  }, [enabled]);
}
