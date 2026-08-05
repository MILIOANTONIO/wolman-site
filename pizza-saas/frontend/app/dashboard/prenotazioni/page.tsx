"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Reservation = {
  id: string; customer_name: string | null; customer_phone: string | null;
  party_size: number | null; starts_at: string; status: string; notes: string | null;
};
type ShiftCapacity = { tables?: number; seats?: number };
type ReservationsData = {
  table_capacity: Record<string, { pranzo?: ShiftCapacity; cena?: ShiftCapacity }>;
  reservations: Reservation[];
};

const DAY_KEYS = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"];
const JS_DAY_TO_KEY = [DAY_KEYS[6], DAY_KEYS[0], DAY_KEYS[1], DAY_KEYS[2], DAY_KEYS[3], DAY_KEYS[4], DAY_KEYS[5]];

function shiftOf(iso: string): "pranzo" | "cena" {
  return new Date(iso).getHours() < 17 ? "pranzo" : "cena";
}

const NEXT_STATUS: Record<string, { label: string; status: string; danger?: boolean }[]> = {
  richiesta: [{ label: "Conferma", status: "confermata" }, { label: "Annulla", status: "annullata", danger: true }],
  confermata: [{ label: "Completata", status: "completata" }, { label: "No-show", status: "no_show", danger: true }, { label: "Annulla", status: "annullata", danger: true }],
  completata: [],
  no_show: [],
  annullata: [],
};

export default function PrenotazioniPage() {
  const [data, setData] = useState<ReservationsData | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    api.get("/api/dashboard/reservations").then(setData).catch((e) => setError(e.message));
  }

  useEffect(reload, []);

  async function changeStatus(id: string, status: string) {
    try {
      await api.post(`/api/dashboard/reservations/${id}/status`, { status });
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore");
    }
  }

  if (!data) {
    return (
      <div>
        {error ? (
          <div className="error">
            {error}
            <div style={{ marginTop: 12 }}>
              <button onClick={reload}>Riprova</button>
            </div>
          </div>
        ) : (
          "Caricamento..."
        )}
      </div>
    );
  }

  const byDate: Record<string, Reservation[]> = {};
  for (const r of data.reservations) {
    const dateKey = r.starts_at.slice(0, 10);
    (byDate[dateKey] ||= []).push(r);
  }
  const sortedDates = Object.keys(byDate).sort();

  return (
    <div>
      <h1>Prenotazioni</h1>
      <p className="muted">Prenotazioni dei prossimi 30 giorni, con capacità configurata per turno.</p>
      {error && <div className="error">{error}</div>}

      {sortedDates.length === 0 && <p className="muted">Nessuna prenotazione al momento.</p>}

      {sortedDates.map((dateKey) => {
        const dayReservations = [...byDate[dateKey]].sort((a, b) => a.starts_at.localeCompare(b.starts_at));
        const jsDay = new Date(dateKey + "T00:00:00").getDay();
        const dayKey = JS_DAY_TO_KEY[jsDay];
        const capacity = data.table_capacity[dayKey] || {};
        const dateLabel = new Date(dateKey + "T00:00:00").toLocaleDateString("it-IT", { weekday: "long", day: "2-digit", month: "2-digit" });

        return (
          <div key={dateKey} className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 8 }}>
              <h2 style={{ textTransform: "capitalize", margin: 0 }}>{dateLabel}</h2>
              <div className="muted" style={{ fontSize: "0.8rem" }}>
                {(["pranzo", "cena"] as const).map((shift) => {
                  const shiftReservations = dayReservations.filter((r) => shiftOf(r.starts_at) === shift && r.status !== "annullata");
                  const occupiedSeats = shiftReservations.reduce((sum, r) => sum + (r.party_size || 0), 0);
                  const cap = capacity[shift];
                  if (!cap?.seats && !cap?.tables && shiftReservations.length === 0) return null;
                  return (
                    <span key={shift} style={{ marginLeft: 12 }}>
                      {shift === "pranzo" ? "Pranzo" : "Cena"}: {shiftReservations.length}{cap?.tables ? `/${cap.tables} tavoli` : " tavoli"}, {occupiedSeats}{cap?.seats ? `/${cap.seats} posti` : " posti"}
                    </span>
                  );
                })}
              </div>
            </div>

            {dayReservations.map((r) => (
              <div key={r.id} className="order-card" style={{ marginTop: 12 }}>
                <div>
                  <strong>{new Date(r.starts_at).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })}</strong>{" "}
                  <span className="badge">{r.status}</span>
                  <div className="muted">
                    {r.customer_name || "cliente"} {r.customer_phone && `(${r.customer_phone})`} — {r.party_size ?? "?"} persone
                  </div>
                  {r.notes && <div className="muted">Note: {r.notes}</div>}
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  {(NEXT_STATUS[r.status] || []).map((next) => (
                    <button key={next.status} className={next.danger ? "secondary" : ""} onClick={() => changeStatus(r.id, next.status)}>
                      {next.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
