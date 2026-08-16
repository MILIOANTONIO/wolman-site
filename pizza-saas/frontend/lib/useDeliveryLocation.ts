"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "./api";

export type LocationSharingStatus = "idle" | "requesting" | "sharing" | "denied" | "unsupported";

/** Nel telefono del fattorino: chiede subito il permesso GPS al montaggio
 * (nessun click separato, come da richiesta) e manda la posizione al
 * server ogni volta che il browser ne rileva una nuova, con un minimo di
 * 10 secondi tra un invio e l'altro per non intasare il server. */
export function useDeliveryLocationSharing(enabled: boolean) {
  const [status, setStatus] = useState<LocationSharingStatus>("idle");
  const lastSentRef = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    if (!("geolocation" in navigator)) {
      setStatus("unsupported");
      return;
    }

    setStatus("requesting");
    const watchId = navigator.geolocation.watchPosition(
      (position) => {
        setStatus("sharing");
        const now = Date.now();
        if (now - lastSentRef.current < 10000) return;
        lastSentRef.current = now;
        api
          .put("/api/dashboard/delivery/location", {
            lat: position.coords.latitude,
            lng: position.coords.longitude,
          })
          .catch(() => {});
      },
      () => setStatus("denied"),
      { enableHighAccuracy: true, maximumAge: 5000 }
    );

    return () => navigator.geolocation.clearWatch(watchId);
  }, [enabled]);

  return status;
}
