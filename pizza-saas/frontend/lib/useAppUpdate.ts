"use client";
import { useEffect } from "react";

/**
 * L'app installata come PWA non ricarica mai da sola quando viene riaperta
 * (a differenza di una scheda browser normale, che spesso rifa' il fetch):
 * dopo un deploy l'utente resterebbe bloccato sulla versione vecchia finche'
 * non la chiude e riapre manualmente il processo. Quando l'app torna in
 * primo piano, confronta il buildId Next.js caricato con quello attualmente
 * pubblicato e, se diverso, ricarica da sola.
 */
export function useAppUpdate() {
  useEffect(() => {
    async function checkForUpdate() {
      const currentBuildId = (window as unknown as { __NEXT_DATA__?: { buildId?: string } }).__NEXT_DATA__?.buildId;
      if (!currentBuildId) return;
      try {
        const res = await fetch(window.location.pathname, { cache: "no-store" });
        const html = await res.text();
        const match = html.match(/"buildId":"([^"]+)"/);
        if (match && match[1] && match[1] !== currentBuildId) {
          window.location.reload();
        }
      } catch {
        // offline o rete instabile: ritenta al prossimo focus, non bloccare l'uso
      }
    }

    function onVisibility() {
      if (document.visibilityState === "visible") checkForUpdate();
    }
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("focus", checkForUpdate);
    // Anche se l'app resta sempre aperta in primo piano (es. un tablet in
    // cucina mai bloccato) - un controllo ogni 5 minuti copre pure quel caso.
    const intervalId = setInterval(checkForUpdate, 5 * 60 * 1000);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("focus", checkForUpdate);
      clearInterval(intervalId);
    };
  }, []);
}
