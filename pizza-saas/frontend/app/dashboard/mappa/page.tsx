"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useMe } from "@/lib/useMe";
import { useOrdersSocket } from "@/lib/useOrdersSocket";
import { bootstrapGoogleMaps, GOOGLE_MAPS_KEY } from "@/lib/useGooglePlaces";

type DeliveryLocation = { user_id: string; email: string; lat: number; lng: number; updated_at: string };

export default function MappaConsegnePage() {
  const me = useMe();
  const [locations, setLocations] = useState<DeliveryLocation[]>([]);
  const [mapsStatus, setMapsStatus] = useState<"loading" | "ready" | "unavailable">(GOOGLE_MAPS_KEY ? "loading" : "unavailable");
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<any>(null);
  const markersRef = useRef<Record<string, any>>({});

  function reload() {
    api.get("/api/dashboard/delivery/locations").then(setLocations).catch(() => {});
  }

  useEffect(reload, []);

  useOrdersSocket(me?.tenant_id ?? null, (event) => {
    if (event.type === "delivery_location_changed") {
      setLocations((prev) => {
        const next = prev.filter((l) => l.user_id !== event.user_id);
        next.push({ user_id: event.user_id, email: event.email, lat: event.lat, lng: event.lng, updated_at: new Date().toISOString() });
        return next;
      });
    }
  });

  useEffect(() => {
    if (!GOOGLE_MAPS_KEY) return;
    bootstrapGoogleMaps();
    (window as any).google.maps
      .importLibrary("maps")
      .then(() => setMapsStatus("ready"))
      .catch(() => setMapsStatus("unavailable"));
  }, []);

  useEffect(() => {
    if (mapsStatus !== "ready" || !containerRef.current || mapRef.current) return;
    const google = (window as any).google;
    mapRef.current = new google.maps.Map(containerRef.current, {
      center: { lat: 41.9028, lng: 12.4964 }, // Italia, centro di default finché non ci sono fattorini attivi
      zoom: 6,
    });
  }, [mapsStatus]);

  useEffect(() => {
    if (mapsStatus !== "ready" || !mapRef.current) return;
    const google = (window as any).google;
    const map = mapRef.current;
    const seen = new Set<string>();

    for (const loc of locations) {
      seen.add(loc.user_id);
      const position = { lat: loc.lat, lng: loc.lng };
      if (markersRef.current[loc.user_id]) {
        markersRef.current[loc.user_id].setPosition(position);
      } else {
        markersRef.current[loc.user_id] = new google.maps.Marker({
          position, map, title: loc.email, label: "🛵",
        });
      }
    }
    for (const userId of Object.keys(markersRef.current)) {
      if (!seen.has(userId)) {
        markersRef.current[userId].setMap(null);
        delete markersRef.current[userId];
      }
    }
    if (locations.length === 1) {
      // fitBounds su un solo punto (area zero) zooma al massimo consentito,
      // troppo vicino per essere utile - con un solo fattorino basta
      // centrare la mappa su di lui a uno zoom fisso da "quartiere".
      map.setCenter({ lat: locations[0].lat, lng: locations[0].lng });
      map.setZoom(15);
    } else if (locations.length > 1) {
      const bounds = new google.maps.LatLngBounds();
      locations.forEach((l) => bounds.extend({ lat: l.lat, lng: l.lng }));
      map.fitBounds(bounds, 80);
    }
  }, [locations, mapsStatus]);

  return (
    <div>
      <h1>Mappa consegne</h1>
      <p className="muted">Posizione in tempo reale dei fattorini con la condivisione posizione attiva (aggiornata automaticamente).</p>

      {mapsStatus === "unavailable" && <p className="error">Mappa non disponibile al momento.</p>}
      {locations.length === 0 && <p className="muted">Nessun fattorino attivo al momento.</p>}

      <div ref={containerRef} style={{ width: "100%", height: 480, borderRadius: 12, overflow: "hidden", border: "1px solid var(--border)" }} />

      {locations.length > 0 && (
        <div className="card" style={{ marginTop: 20 }}>
          <h2>Fattorini attivi</h2>
          {locations.map((l) => (
            <div key={l.user_id} className="order-card">
              <span>🛵 {l.email}</span>
              <span className="muted">agg. {new Date(l.updated_at).toLocaleTimeString("it-IT")}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
