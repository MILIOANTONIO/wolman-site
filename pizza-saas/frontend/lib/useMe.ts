"use client";
import { useEffect, useState } from "react";
import { api } from "./api";

export type Me = { id: string; email: string; tenant_id: string; role: string; on_duty: boolean };

// "Impossibile contattare il server..." (vedi api.ts/safeFetch) è l'unico
// messaggio che indica un errore di rete/server irraggiungibile invece di
// un vero 401 - senza distinguerli, un backend momentaneamente lento o in
// riavvio sbatterebbe fuori l'utente verso /login invece di ritentare da
// solo (resta undefined = "in caricamento" finché non risponde davvero).
const NETWORK_ERROR = "Impossibile contattare il server. Verifica che sia acceso e riprova.";
const RETRY_MS = 3000;

export function useMe() {
  const [me, setMe] = useState<Me | null | undefined>(undefined); // undefined = ancora in caricamento

  useEffect(() => {
    let cancelled = false;
    let retryId: ReturnType<typeof setTimeout> | undefined;

    function load() {
      api
        .get("/api/auth/me")
        .then((data) => {
          if (!cancelled) setMe(data);
        })
        .catch((e) => {
          if (cancelled) return;
          if (e instanceof Error && e.message === NETWORK_ERROR) {
            retryId = setTimeout(load, RETRY_MS); // server irraggiungibile: non è un logout, ritenta da solo
          } else {
            setMe(null); // 401/403 legittimo: davvero non autenticato
          }
        });
    }

    load();
    return () => {
      cancelled = true;
      clearTimeout(retryId);
    };
  }, []);

  return me;
}
