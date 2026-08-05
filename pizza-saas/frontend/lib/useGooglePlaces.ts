"use client";
import { useCallback, useEffect, useRef, useState } from "react";

export const GOOGLE_MAPS_KEY = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;

let bootstrapped = false;

// Snippet di bootstrap ufficiale di Google (https://developers.google.com/maps/documentation/javascript/load-maps-js-api):
// definisce google.maps.importLibrary SINCRONAMENTE come stub che carica lo
// script vero al primo utilizzo. Caricare lo script con un tag <script src>
// "a mano" e aspettare solo il suo evento onload NON basta: onload si attiva
// quando il bootstrap iniziale è arrivato, non quando importLibrary è
// effettivamente pronto - in pratica lascia una finestra in cui
// google.maps esiste ma google.maps.importLibrary no, causando un crash.
export function bootstrapGoogleMaps() {
  if (bootstrapped || typeof window === "undefined") return;
  bootstrapped = true;
  (function (g: any) {
    let h: any, a: any, k: string, b: any;
    const p = "The Google Maps JavaScript API", c = "google", l = "importLibrary", q = "__ib__";
    const m = document;
    b = (window as any)[c] || ((window as any)[c] = {});
    const d = b.maps || (b.maps = {}), r = new Set(), e = new URLSearchParams();
    const u = () =>
      h ||
      (h = new Promise(async (f, n) => {
        a = m.createElement("script");
        e.set("libraries", [...Array.from(r)] + "");
        for (k in g) e.set(k.replace(/[A-Z]/g, (t: string) => "_" + t[0].toLowerCase()), g[k]);
        e.set("callback", c + ".maps." + q);
        a.src = `https://maps.${c}apis.com/maps/api/js?` + e;
        d[q] = f;
        a.onerror = () => (h = n(Error(p + " could not load.")));
        a.nonce = (m.querySelector("script[nonce]") as any)?.nonce || "";
        m.head.append(a);
      }));
    d[l] ? console.warn(p + " only loads once. Ignoring:", g) : (d[l] = (f: string, ...n: any[]) => r.add(f) && u().then(() => d[l](f, ...n)));
  })({ key: GOOGLE_MAPS_KEY, v: "weekly" });
}

type ParsedAddress = { address: string; city: string; province: string };

function parsePlace(place: any): ParsedAddress {
  // La nuova Places API restituisce addressComponents con {longText, shortText, types}
  // (camelCase), a differenza della vecchia address_components con long_name/short_name.
  const components: { longText: string; shortText: string; types: string[] }[] = place.addressComponents || [];
  const get = (type: string, useShort = false) => {
    const c = components.find((c) => c.types.includes(type));
    return c ? (useShort ? c.shortText : c.longText) : "";
  };
  const streetNumber = get("street_number");
  const route = get("route");
  const city = get("locality") || get("postal_town") || get("administrative_area_level_3");
  const province = get("administrative_area_level_2", true);
  const address = [route, streetNumber].filter(Boolean).join(", ") || place.formattedAddress || "";
  return { address, city, province };
}

/** Collega il widget di autocompletamento indirizzi di Google Places (nuova
 * API, limitata all'Italia) dentro il container indicato: appena l'utente
 * seleziona un suggerimento, richiama onPlaceSelected con indirizzo/città/
 * provincia già separati.
 *
 * Usa un callback ref (invece di useRef) per il contenitore: con useRef il
 * mount del nodo DOM e il completamento del caricamento asincrono dello
 * script Google possono correre in ordini diversi tra loro, e leggere
 * containerRef.current dentro un effetto innescato solo dallo stato
 * "ready" a volte lo trovava ancora null. Il callback ref invece aggiorna
 * uno state React esattamente quando il nodo monta, garantendo che
 * l'effetto riparta appena entrambe le condizioni sono vere. */
export function useGooglePlacesAutocomplete(onPlaceSelected: (parsed: ParsedAddress) => void) {
  const [container, setContainer] = useState<HTMLDivElement | null>(null);
  const containerRef = useCallback((node: HTMLDivElement | null) => setContainer(node), []);
  const elementRef = useRef<any>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "unavailable">(GOOGLE_MAPS_KEY ? "loading" : "unavailable");

  useEffect(() => {
    if (!GOOGLE_MAPS_KEY) return;
    let cancelled = false;
    bootstrapGoogleMaps();
    (window as any).google.maps
      .importLibrary("places")
      .then(() => { if (!cancelled) setStatus("ready"); })
      .catch(() => { if (!cancelled) setStatus("unavailable"); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (status !== "ready" || !container || elementRef.current) return;
    let cancelled = false;
    (window as any).google.maps.importLibrary("places").then((places: any) => {
      if (cancelled || elementRef.current || !container) return;
      const el = new places.PlaceAutocompleteElement({ includedRegionCodes: ["it"] });
      el.id = "address-autocomplete";
      el.style.width = "100%";
      container.appendChild(el);
      elementRef.current = el;

      const listener = async (event: any) => {
        const place = event.placePrediction.toPlace();
        await place.fetchFields({ fields: ["addressComponents", "formattedAddress"] });
        onPlaceSelected(parsePlace(place));
      };
      el.addEventListener("gmp-select", listener);
      el.__listener = listener;
    });
    return () => {
      cancelled = true;
      if (elementRef.current?.__listener) elementRef.current.removeEventListener("gmp-select", elementRef.current.__listener);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, container]);

  return { containerRef, status };
}
