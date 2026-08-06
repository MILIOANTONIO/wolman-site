"use client";
import { useEffect, useRef } from "react";
import { API_URL } from "./api";

export type OrderEvent =
  | { type: "order_created"; order: Record<string, unknown> }
  | { type: "order_status_changed"; order_id: string; status: string }
  | { type: "order_assigned"; order_id: string; assigned_to_user_id: string }
  | { type: "delivery_location_changed"; user_id: string; email: string; lat: number; lng: number }
  | { type: "reservation_created"; reservation: Record<string, unknown> }
  | { type: "order_confirmation_changed"; order_id: string; confirmation_status: string }
  | { type: "reservation_confirmation_changed"; reservation_id: string; confirmation_status: string };

export function useOrdersSocket(tenantId: string | null, onEvent: (e: OrderEvent) => void) {
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  useEffect(() => {
    if (!tenantId) return;
    const wsUrl = API_URL.replace(/^http/, "ws") + `/ws/tenant/${tenantId}/orders`;

    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;
    let stopped = false;

    function connect() {
      socket = new WebSocket(wsUrl);
      socket.onopen = () => { attempt = 0; };
      socket.onmessage = (event) => {
        try {
          handlerRef.current(JSON.parse(event.data));
        } catch {
          // messaggio non JSON, ignorato
        }
      };
      // Senza riconnessione, una caduta della connessione (es. redeploy del
      // backend, rete instabile) lascia l'app silenziosamente senza nuovi
      // ordini/notifiche finche' non si ricarica la pagina a mano.
      socket.onclose = () => {
        if (stopped) return;
        const delay = Math.min(1000 * 2 ** attempt, 15000);
        attempt += 1;
        reconnectTimer = setTimeout(connect, delay);
      };
    }

    connect();
    const onOnline = () => { if (socket?.readyState !== WebSocket.OPEN) { attempt = 0; connect(); } };
    window.addEventListener("online", onOnline);

    return () => {
      stopped = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      window.removeEventListener("online", onOnline);
      socket?.close();
    };
  }, [tenantId]);
}
