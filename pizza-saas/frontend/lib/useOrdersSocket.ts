"use client";
import { useEffect, useRef } from "react";
import { API_URL } from "./api";

export type OrderEvent =
  | { type: "order_created"; order: Record<string, unknown> }
  | { type: "order_status_changed"; order_id: string; status: string };

export function useOrdersSocket(tenantId: string | null, onEvent: (e: OrderEvent) => void) {
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  useEffect(() => {
    if (!tenantId) return;
    const wsUrl = API_URL.replace(/^http/, "ws") + `/ws/tenant/${tenantId}/orders`;
    const socket = new WebSocket(wsUrl);
    socket.onmessage = (event) => {
      try {
        handlerRef.current(JSON.parse(event.data));
      } catch {
        // messaggio non JSON, ignorato
      }
    };
    return () => socket.close();
  }, [tenantId]);
}
