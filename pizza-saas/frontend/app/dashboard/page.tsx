"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useMe } from "@/lib/useMe";
import { useOrdersSocket } from "@/lib/useOrdersSocket";
import { useDeliveryLocationSharing } from "@/lib/useDeliveryLocation";
import { useDeliveryRoute, RouteStop } from "@/lib/useDeliveryRoute";

type OrderItem = { name: string; quantity: number; notes: string | null };

type Order = {
  id: string; order_number: string; channel: string; order_type: string;
  customer_name: string | null; customer_phone: string | null;
  status: string; total_cents: number; created_at: string;
  items: OrderItem[];
  delivery_address: string | null; delivery_lat: number | null; delivery_lng: number | null;
  assigned_to_user_id: string | null; assigned_to_email: string | null;
};

const NEXT_STATUS: Record<string, { label: string; status: string }[]> = {
  ricevuto: [{ label: "Metti in forno", status: "in_forno" }],
  in_forno: [{ label: "Pronta", status: "pronta" }, { label: "In consegna", status: "in_consegna" }],
  pronta: [{ label: "In consegna", status: "in_consegna" }, { label: "Consegnata", status: "consegnata" }],
  in_consegna: [{ label: "Consegnata", status: "consegnata" }],
  consegnata: [],
  annullato: [],
};

const TITLE_BY_ROLE: Record<string, string> = {
  cuoco: "Comande in cucina",
  delivery: "Consegne",
  owner: "Ordini in arrivo",
};

// Promemoria per chi e' in cucina: quanti minuti sono passati dall'arrivo
// dell'ordine, aggiornato ogni minuto senza dover ricaricare la pagina.
function ElapsedMinutes({ createdAt }: { createdAt: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);
  const minutes = Math.max(0, Math.floor((now - new Date(createdAt).getTime()) / 60_000));
  const urgent = minutes >= 20;
  return (
    <span style={{ fontWeight: 700, fontSize: "0.85rem", color: urgent ? "var(--accent)" : "var(--muted)" }}>
      ⏱ {minutes === 0 ? "appena arrivato" : `${minutes} min fa`}
    </span>
  );
}

const LOCATION_STATUS_LABEL: Record<string, string> = {
  requesting: "📍 Richiesta permesso posizione...",
  sharing: "📍 Posizione condivisa con la pizzeria",
  denied: "⚠ Posizione non autorizzata — attivala nelle impostazioni del browser per farti trovare sulla mappa",
  unsupported: "⚠ Questo browser non supporta la condivisione posizione",
};

export default function DashboardPage() {
  const me = useMe();
  const [orders, setOrders] = useState<Order[]>([]);
  const [onDuty, setOnDuty] = useState(false);
  const [dutyLoading, setDutyLoading] = useState(false);
  const locationStatus = useDeliveryLocationSharing(me?.role === "delivery" && onDuty);

  useEffect(() => {
    api.get("/api/dashboard/orders").then(setOrders).catch(() => {});
  }, []);

  useEffect(() => {
    if (me?.role === "delivery") setOnDuty(me.on_duty);
  }, [me]);

  useOrdersSocket(me?.tenant_id ?? null, (event) => {
    if (event.type === "order_created" || event.type === "order_assigned") {
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

  async function toggleDuty() {
    setDutyLoading(true);
    try {
      const next = !onDuty;
      const result = await api.put("/api/dashboard/delivery/duty", { on_duty: next });
      setOnDuty(result.on_duty);
      if (result.claimed_orders > 0) {
        api.get("/api/dashboard/orders").then(setOrders).catch(() => {});
      }
    } catch {
      // no-op
    } finally {
      setDutyLoading(false);
    }
  }

  const active = orders.filter((o) => !["consegnata", "annullato"].includes(o.status));
  const done = orders.filter((o) => ["consegnata", "annullato"].includes(o.status));

  const routeStops: RouteStop[] = active
    .filter((o) => o.status === "in_consegna" && o.delivery_lat != null && o.delivery_lng != null)
    .map((o) => ({ orderId: o.id, label: `#${o.order_number} — ${o.customer_name || "cliente"} — ${o.delivery_address}`, lat: o.delivery_lat as number, lng: o.delivery_lng as number }));
  const route = useDeliveryRoute(me?.role === "delivery" ? routeStops : []);

  return (
    <div>
      <h1>{TITLE_BY_ROLE[me?.role || "owner"] || "Ordini in arrivo"}</h1>

      {me?.role === "delivery" && (
        <div className="card" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <div>
            <strong>{onDuty ? "🟢 In servizio" : "⚪ Non in servizio"}</strong>
            <div className="muted">{onDuty ? "Ricevi nuove consegne assegnate automaticamente." : "Non ricevi nuove consegne finché non ti metti in servizio."}</div>
          </div>
          <button className={onDuty ? "secondary" : ""} disabled={dutyLoading} onClick={toggleDuty}>
            {dutyLoading ? "..." : onDuty ? "Vai fuori servizio" : "Vai in servizio"}
          </button>
        </div>
      )}

      {me?.role === "delivery" && onDuty && locationStatus !== "idle" && (
        <p className={locationStatus === "sharing" ? "muted" : "error"} style={{ marginTop: -8, marginBottom: 16 }}>
          {LOCATION_STATUS_LABEL[locationStatus]}
        </p>
      )}

      {me?.role === "delivery" && routeStops.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Percorso consegne</h2>
          {route.status === "loading" && <p className="muted">Calcolo il percorso più efficiente...</p>}
          {route.status !== "loading" && (
            <>
              <ol style={{ paddingLeft: 20, margin: "8px 0" }}>
                {route.orderedStops.map((s) => <li key={s.orderId}>{s.label}</li>)}
              </ol>
              {route.navigationUrl && (
                <a href={route.navigationUrl} target="_blank" rel="noopener noreferrer">
                  <button type="button">🧭 Avvia navigazione</button>
                </a>
              )}
            </>
          )}
        </div>
      )}

      {active.length === 0 && <p className="muted">Nessun ordine attivo al momento.</p>}
      {active.map((o) => (
        <div key={o.id} className="order-card">
          <div>
            <strong>#{o.order_number}</strong> <span className={`badge ${o.status}`}>{o.status.replace("_", " ")}</span>
            <div className="muted">
              {o.channel === "voice" ? "📞" : "💬"} {o.order_type} — {o.customer_name || "cliente"} {o.customer_phone && `(${o.customer_phone})`}
            </div>
            <div className="muted">🕐 Arrivato alle {new Date(o.created_at).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })}</div>
            {o.order_type === "delivery" && o.delivery_address && <div className="muted">📍 {o.delivery_address}</div>}
            {me?.role === "owner" && o.order_type === "delivery" && (
              <div className="muted">{o.assigned_to_email ? `🛵 assegnato a ${o.assigned_to_email}` : "🛵 nessun fattorino assegnato"}</div>
            )}
            <ul style={{ margin: "8px 0", paddingLeft: 20 }}>
              {o.items.map((item, idx) => (
                <li key={idx}>
                  {item.quantity}× {item.name}
                  {item.notes && (
                    <span style={{ color: "var(--accent)", fontWeight: 600 }}> — {item.notes}</span>
                  )}
                </li>
              ))}
            </ul>
            <div>{(o.total_cents / 100).toFixed(2)} €</div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8 }}>
            <ElapsedMinutes createdAt={o.created_at} />
            <div style={{ display: "flex", gap: 8 }}>
              {(NEXT_STATUS[o.status] || []).map((next) => (
                <button key={next.status} onClick={() => changeStatus(o.id, next.status)}>{next.label}</button>
              ))}
            </div>
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
