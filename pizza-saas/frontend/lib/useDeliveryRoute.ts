"use client";
import { useEffect, useState } from "react";
import { bootstrapGoogleMaps, GOOGLE_MAPS_KEY } from "./useGooglePlaces";

export type RouteStop = { orderId: string; label: string; lat: number; lng: number };

type RouteResult = {
  status: "idle" | "loading" | "ready" | "error" | "unavailable";
  orderedStops: RouteStop[];
  navigationUrl: string | null;
};

function buildNavigationUrl(stops: RouteStop[]): string {
  const last = stops[stops.length - 1];
  const waypoints = stops.slice(0, -1).map((s) => `${s.lat},${s.lng}`).join("|");
  const params = new URLSearchParams({
    api: "1",
    destination: `${last.lat},${last.lng}`,
    travelmode: "driving",
  });
  if (waypoints) params.set("waypoints", waypoints);
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}

/** Calcola l'ordine di consegna piu' efficiente tra piu' tappe (Directions
 * API con optimizeWaypoints) e prepara il link per aprire la navigazione
 * vera in Google Maps con le tappe gia' in quell'ordine - non reinventiamo
 * un navigatore turn-by-turn, riusiamo quello che il fattorino gia' conosce. */
export function useDeliveryRoute(stops: RouteStop[]): RouteResult {
  const [result, setResult] = useState<RouteResult>({ status: "idle", orderedStops: [], navigationUrl: null });

  useEffect(() => {
    if (stops.length === 0) {
      setResult({ status: "idle", orderedStops: [], navigationUrl: null });
      return;
    }
    if (!GOOGLE_MAPS_KEY) {
      setResult({ status: "unavailable", orderedStops: stops, navigationUrl: buildNavigationUrl(stops) });
      return;
    }
    if (stops.length === 1) {
      setResult({ status: "ready", orderedStops: stops, navigationUrl: buildNavigationUrl(stops) });
      return;
    }

    let cancelled = false;
    setResult((r) => ({ ...r, status: "loading" }));

    function computeFrom(origin: { lat: number; lng: number } | null) {
      bootstrapGoogleMaps();
      (window as any).google.maps.importLibrary("routes").then((routes: any) => {
        if (cancelled) return;
        const service = new routes.DirectionsService();
        const originPoint = origin || { lat: stops[0].lat, lng: stops[0].lng };
        service.route(
          {
            origin: originPoint,
            destination: { lat: stops[stops.length - 1].lat, lng: stops[stops.length - 1].lng },
            waypoints: stops.slice(0, -1).map((s) => ({ location: { lat: s.lat, lng: s.lng } })),
            optimizeWaypoints: true,
            travelMode: (window as any).google.maps.TravelMode.DRIVING,
          },
          (response: any, status: string) => {
            if (cancelled) return;
            if (status !== "OK" || !response) {
              setResult({ status: "error", orderedStops: stops, navigationUrl: buildNavigationUrl(stops) });
              return;
            }
            const order: number[] = response.routes[0].waypoint_order || [];
            const middle = stops.slice(0, -1);
            const ordered = [...order.map((i) => middle[i]), stops[stops.length - 1]];
            setResult({ status: "ready", orderedStops: ordered, navigationUrl: buildNavigationUrl(ordered) });
          }
        );
      });
    }

    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => computeFrom({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
        () => computeFrom(null),
        { timeout: 5000 }
      );
    } else {
      computeFrom(null);
    }

    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(stops)]);

  return result;
}
