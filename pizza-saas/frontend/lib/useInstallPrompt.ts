"use client";
import { useEffect, useState } from "react";

// Evento non ancora nei tipi standard del DOM.
interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

function isStandaloneNow(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia?.("(display-mode: standalone)").matches ||
    // Safari iOS: proprietà non standard, non tipizzata da lib.dom.
    (window.navigator as unknown as { standalone?: boolean }).standalone === true
  );
}

/**
 * Chrome/Android mostra il prompt nativo di installazione UNA volta sola in
 * automatico e poi mai più, a meno che l'evento "beforeinstallprompt" non
 * venga catturato e ritriggerato da un bottone nostro. iOS Safari questo
 * evento non lo spara mai: li' l'unica via e' "Condividi -> Aggiungi a Home",
 * niente prompt programmabile.
 */
export function useInstallPrompt() {
  const [deferredEvent, setDeferredEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [isStandalone, setIsStandalone] = useState(false);
  const [isIOS, setIsIOS] = useState(false);

  useEffect(() => {
    setIsStandalone(isStandaloneNow());
    setIsIOS(/iphone|ipad|ipod/i.test(window.navigator.userAgent));

    function onBeforeInstallPrompt(e: Event) {
      e.preventDefault();
      setDeferredEvent(e as BeforeInstallPromptEvent);
    }
    function onInstalled() {
      setDeferredEvent(null);
      setIsStandalone(true);
    }

    window.addEventListener("beforeinstallprompt", onBeforeInstallPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstallPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  async function promptInstall() {
    if (!deferredEvent) return;
    await deferredEvent.prompt();
    await deferredEvent.userChoice;
    setDeferredEvent(null);
  }

  return { canInstall: !!deferredEvent, promptInstall, isIOS, isStandalone };
}
