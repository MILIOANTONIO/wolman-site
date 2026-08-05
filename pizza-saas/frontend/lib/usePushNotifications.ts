"use client";
import { useEffect, useState } from "react";
import { api } from "./api";

export type PushStatus = "idle" | "requesting" | "subscribed" | "denied" | "unsupported";

function urlBase64ToUint8Array(base64: string) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const base64Safe = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64Safe);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

/** Registra il service worker e chiede subito il permesso per le notifiche
 * push (stesso approccio "chiedi appena entri" usato per il GPS del
 * delivery) - vale per tutti i ruoli, utile a tutti sapere subito quando
 * arriva un ordine/prenotazione senza dover tenere la pagina aperta. */
export function usePushNotifications(enabled: boolean) {
  const [status, setStatus] = useState<PushStatus>("idle");

  useEffect(() => {
    if (!enabled) return;
    if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
      setStatus("unsupported");
      return;
    }

    let cancelled = false;

    async function run() {
      try {
        const registration = await navigator.serviceWorker.register("/sw.js");
        setStatus("requesting");

        const permission = await Notification.requestPermission();
        if (cancelled) return;
        if (permission !== "granted") {
          setStatus("denied");
          return;
        }

        const { key } = await api.get("/api/push/vapid-public-key");
        if (!key) {
          setStatus("unsupported");
          return;
        }

        let subscription = await registration.pushManager.getSubscription();
        if (!subscription) {
          subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(key),
          });
        }

        await api.post("/api/push/subscribe", subscription.toJSON());
        if (!cancelled) setStatus("subscribed");
      } catch {
        if (!cancelled) setStatus("denied");
      }
    }

    run();
    return () => { cancelled = true; };
  }, [enabled]);

  return status;
}
