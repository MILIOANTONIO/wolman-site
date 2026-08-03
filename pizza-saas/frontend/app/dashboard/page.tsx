"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useMe } from "@/lib/useMe";
import { useOrdersSocket } from "@/lib/useOrdersSocket";

type Order = {
  id: string; order_number: string; channel: string; order_type: string;
  customer_name: string | null; customer_phone: string | null;
  status: string; total_cents: number; created_at: string;
};

const NEXT_STATUS: Record<string, { label: string; status: string }[]> = {
  ricevuto: [{ label: "Metti in forno", status: "in_forno" }],
  in_forno: [{ label: "Pronta", status: "pronta" }, { label: "In consegna", status: "in_consegna" }],
  pronta: [{ label: "In consegna", status: "in_consegna" }, { label: "Consegnata", status: "consegnata" }],
  in_consegna: [{ label: "Consegnata", status: "consegnata" }],
  consegnata: [],
  annullato: [],
};

export default function DashboardPage() {
  const me = useMe();
  const [orders, setOrders] = useState<Order[]>([]);

  useEffect(() => {
    api.get("/api/dashboard/orders").then(setOrders).catch(() => {});
  }, []);

  useOrdersSocket(me?.tenant_id ?? null, (event) => {
    if (event.type === "order_created") {
      api.get("/api/dashboard/orders").then(setOrders).catch(() => {});
    } else if (event.type === "order_status_changed") {
      setOrders((prev) => prev.map((o) => (o.id === event.order_id ? { ...o, status: event.status } : o)));
    }
  });

  async function changeStatus(orderId: string, status: string) {
    try {
      await api.post(`/api/dashboard/orders/${orderId}/status`, { status });
    } catch {
      // il WebSocket allineerà comunque lo stato reale al prossimo evento
    }
  }

  const active = orders.filter((o) => !["consegnata", "annullato"].includes(o.status));
  const done = orders.filter((o) => ["consegnata", "annullato"].includes(o.status));

  return (
    <div className="page" style={{ maxWidth: 900 }}>
      <nav>
        <a href="/dashboard">Ordini</a>
        <a href="/dashboard/consumi">Consumi</a>
        <a href="/onboarding">Impostazioni</a>
      </nav>
      <h1>Ordini in arrivo</h1>

      {active.length === 0 && <p className="muted">Nessun ordine attivo al momento.</p>}
      {active.map((o) => (
        <div key={o.id} className="order-card">
          <div>
            <strong>#{o.order_number}</strong> <span className={`badge ${o.status}`}>{o.status.replace("_", " ")}</span>
            <div className="muted">
              {o.channel === "voice" ? "📞" : "💬"} {o.order_type} — {o.customer_name || "cliente"} {o.customer_phone && `(${o.customer_phone})`}
            </div>
            <div>{(o.total_cents / 100).toFixed(2)} €</div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {(NEXT_STATUS[o.status] || []).map((next) => (
              <button key={next.status} onClick={() => changeStatus(o.id, next.status)}>{next.label}</button>
            ))}
          </div>
        </div>
      ))}

      {done.length > 0 && (
        <>
          <h2 style={{ marginTop: 32 }}>Completati</h2>
          {done.map((o) => (
            <div key={o.id} className="order-card">
              <span>#{o.order_number} — {o.customer_name || "cliente"}</span>
              <span className={`badge ${o.status}`}>{o.status}</span>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
