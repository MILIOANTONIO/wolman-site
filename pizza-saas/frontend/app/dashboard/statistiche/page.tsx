"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  PieChart, Pie, Cell, Legend,
} from "recharts";

type DailyPoint = { date: string; orders: number; revenue_cents: number };

type Stats = {
  total_orders: number;
  total_revenue_cents: number;
  orders_by_status: Record<string, number>;
  orders_by_channel: Record<string, number>;
  daily_last_14_days: DailyPoint[];
};

type Reservation = {
  id: string; customer_name: string | null; customer_phone: string | null;
  party_size: number | null; starts_at: string; status: string; notes: string | null;
};
type ShiftCapacity = { tables?: number; seats?: number };
type ReservationsData = {
  table_capacity: Record<string, { pranzo?: ShiftCapacity; cena?: ShiftCapacity }>;
  reservations: Reservation[];
};

type TeamMember = {
  id: string; email: string; role: string; role_label: string;
  last_login_at: string | null; last_seen_at: string | null; online: boolean; on_duty: boolean | null;
};

function timeAgo(iso: string | null): string {
  if (!iso) return "mai";
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "adesso";
  if (minutes < 60) return `${minutes} min fa`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} ${hours === 1 ? "ora" : "ore"} fa`;
  const days = Math.floor(hours / 24);
  return `${days} ${days === 1 ? "giorno" : "giorni"} fa`;
}

const DAY_KEYS = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"];
// getDay(): 0=domenica...6=sabato -> indice nel nostro array che parte da lunedì
const JS_DAY_TO_KEY = [DAY_KEYS[6], DAY_KEYS[0], DAY_KEYS[1], DAY_KEYS[2], DAY_KEYS[3], DAY_KEYS[4], DAY_KEYS[5]];
const DAY_LABELS: Record<string, string> = {
  lun: "Lunedì", mar: "Martedì", mer: "Mercoledì", gio: "Giovedì", ven: "Venerdì", sab: "Sabato", dom: "Domenica",
};

function shiftOf(iso: string): "pranzo" | "cena" {
  const hour = new Date(iso).getHours();
  return hour < 17 ? "pranzo" : "cena";
}

const STATUS_LABELS: Record<string, string> = {
  ricevuto: "Ricevuti", in_forno: "In forno", pronta: "Pronti",
  in_consegna: "In consegna", consegnata: "Consegnati", annullato: "Annullati",
};
const CHANNEL_LABELS: Record<string, string> = { voice: "📞 Telefono", whatsapp: "💬 WhatsApp" };
const CHANNEL_COLORS: Record<string, string> = { voice: "#e5533f", whatsapp: "#3ecf8e" };

function fmtDay(iso: string) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("it-IT", { day: "2-digit", month: "2-digit" });
}

function ChartTooltip({ active, payload, label, money }: { active?: boolean; payload?: { value: number }[]; label?: string; money?: boolean }) {
  if (!active || !payload || !payload.length) return null;
  const value = payload[0].value;
  return (
    <div style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 8, padding: "6px 10px", fontSize: "0.85rem" }}>
      <div className="muted">{label ? fmtDay(label) : ""}</div>
      <div style={{ fontWeight: 700 }}>{money ? `${(value / 100).toFixed(2)} €` : value}</div>
    </div>
  );
}

export default function StatistichePage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [reservationsData, setReservationsData] = useState<ReservationsData | null>(null);
  const [team, setTeam] = useState<TeamMember[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    setError(null);
    api.get("/api/dashboard/stats").then(setStats).catch((e) => setError(e.message));
    api.get("/api/dashboard/reservations").then(setReservationsData).catch(() => {});
  }

  useEffect(() => {
    reload();
    const loadTeam = () => api.get("/api/dashboard/team-presence").then(setTeam).catch(() => {});
    loadTeam();
    const id = setInterval(loadTeam, 30_000);
    return () => clearInterval(id);
  }, []);

  if (!stats) {
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

  const channelData = Object.entries(CHANNEL_LABELS)
    .map(([code, label]) => ({ code, label, value: stats.orders_by_channel[code] || 0 }))
    .filter((d) => d.value > 0);

  // Raggruppa le prenotazioni per giorno solare (data leggibile) e calcola
  // quanto occupato è ciascun turno pranzo/cena rispetto alla capacità
  // configurata in Configurazione, per lo stesso giorno della settimana.
  const reservationsByDate: Record<string, Reservation[]> = {};
  for (const r of reservationsData?.reservations || []) {
    const dateKey = r.starts_at.slice(0, 10);
    (reservationsByDate[dateKey] ||= []).push(r);
  }
  const sortedDates = Object.keys(reservationsByDate).sort();
  const capacityByDay = reservationsData?.table_capacity || {};
  const hasTablePlanning = sortedDates.length > 0 || Object.values(capacityByDay).some((d) => d?.pranzo?.seats || d?.cena?.seats || d?.pranzo?.tables || d?.cena?.tables);

  return (
    <div>
      <h1>Statistiche</h1>
      <p className="muted">Andamento ordini della tua pizzeria.</p>

      <div className="stat-grid">
        <div className="stat-tile">
          <div>
            <div className="value">{stats.total_orders}</div>
            <div className="label">Ordini totali</div>
          </div>
          <div className="stat-icon">🛒</div>
        </div>
        <div className="stat-tile">
          <div>
            <div className="value">{(stats.total_revenue_cents / 100).toFixed(2)} €</div>
            <div className="label">Fatturato totale</div>
          </div>
          <div className="stat-icon success">💶</div>
        </div>
        <div className="stat-tile">
          <div>
            <div className="value">{stats.total_orders > 0 ? (stats.total_revenue_cents / stats.total_orders / 100).toFixed(2) : "0.00"} €</div>
            <div className="label">Scontrino medio</div>
          </div>
          <div className="stat-icon info">🧾</div>
        </div>
      </div>

      {team && team.length > 0 && (
        <div className="card">
          <h2>Team</h2>
          {team.map((m) => (
            <div key={m.id} className="order-card">
              <div>
                <span style={{ color: m.online ? "var(--success)" : "var(--muted)", marginRight: 8 }}>●</span>
                <strong>{m.email}</strong>
                <span className="badge" style={{ marginLeft: 8 }}>{m.role_label}</span>
                {m.on_duty !== null && (
                  <span className="muted" style={{ marginLeft: 8 }}>{m.on_duty ? "🛵 in servizio" : "⚪ non in servizio"}</span>
                )}
              </div>
              <div className="muted" style={{ fontSize: "0.85rem", textAlign: "right" }}>
                <div>{m.online ? "Online ora" : `Visto ${timeAgo(m.last_seen_at)}`}</div>
                <div>Ultimo accesso: {timeAgo(m.last_login_at)}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="chart-card">
        <h2>Ordini per giorno (ultimi 14 giorni)</h2>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={stats.daily_last_14_days} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="ordersGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.4} />
                <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis dataKey="date" tickFormatter={fmtDay} stroke="var(--muted)" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis allowDecimals={false} stroke="var(--muted)" fontSize={12} tickLine={false} axisLine={false} width={30} />
            <Tooltip content={<ChartTooltip />} />
            <Area type="monotone" dataKey="orders" stroke="var(--accent)" strokeWidth={2} fill="url(#ordersGradient)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h2>Fatturato per giorno (ultimi 14 giorni)</h2>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={stats.daily_last_14_days} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis dataKey="date" tickFormatter={fmtDay} stroke="var(--muted)" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke="var(--muted)" fontSize={12} tickLine={false} axisLine={false} width={30} tickFormatter={(v) => `${(v / 100).toFixed(0)}€`} />
            <Tooltip content={<ChartTooltip money />} />
            <Bar dataKey="revenue_cents" fill="var(--success)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        <div className="chart-card" style={{ flex: "1 1 280px" }}>
          <h2>Ordini per canale</h2>
          {channelData.length === 0 ? (
            <p className="muted">Ancora nessun ordine.</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={channelData} dataKey="value" nameKey="label" innerRadius={55} outerRadius={80} paddingAngle={3}>
                  {channelData.map((d) => <Cell key={d.code} fill={CHANNEL_COLORS[d.code]} />)}
                </Pie>
                <Legend />
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card" style={{ flex: "1 1 280px" }}>
          <h2>Ordini per stato</h2>
          {Object.entries(STATUS_LABELS).map(([code, label]) => (
            <div key={code} className="order-card">
              <span>{label}</span>
              <span className="badge">{stats.orders_by_status[code] || 0}</span>
            </div>
          ))}
        </div>
      </div>

      {hasTablePlanning && (
        <div className="card">
          <h2>Planning tavoli</h2>
          <p className="muted">Prenotazioni dei prossimi giorni, con occupazione stimata rispetto alla capacità configurata per turno.</p>

          {sortedDates.length === 0 && <p className="muted">Nessuna prenotazione nei prossimi 30 giorni.</p>}

          {sortedDates.map((dateKey) => {
            const dayReservations = [...reservationsByDate[dateKey]].sort((a, b) => a.starts_at.localeCompare(b.starts_at));
            const jsDay = new Date(dateKey + "T00:00:00").getDay();
            const dayKey = JS_DAY_TO_KEY[jsDay];
            const capacity = capacityByDay[dayKey] || {};
            const dateLabel = new Date(dateKey + "T00:00:00").toLocaleDateString("it-IT", { weekday: "long", day: "2-digit", month: "2-digit" });

            return (
              <div key={dateKey} style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 8 }}>
                  <div style={{ fontWeight: 700, textTransform: "capitalize" }}>{dateLabel}</div>
                  <div className="muted" style={{ fontSize: "0.8rem" }}>
                    {(["pranzo", "cena"] as const).map((shift) => {
                      const shiftReservations = dayReservations.filter((r) => shiftOf(r.starts_at) === shift);
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

                {dayReservations.length === 0 ? (
                  <p className="muted" style={{ marginTop: 8 }}>Nessuna prenotazione.</p>
                ) : (
                  <table className="responsive-table" style={{ marginTop: 8 }}>
                    <thead>
                      <tr><th>Ora</th><th>Cliente</th><th>Telefono</th><th>Persone</th><th>Stato</th></tr>
                    </thead>
                    <tbody>
                      {dayReservations.map((r) => (
                        <tr key={r.id}>
                          <td data-label="Ora">{new Date(r.starts_at).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })}</td>
                          <td data-label="Cliente">{r.customer_name || "—"}</td>
                          <td data-label="Telefono">{r.customer_phone || "—"}</td>
                          <td data-label="Persone">{r.party_size ?? "—"}</td>
                          <td data-label="Stato"><span className="badge">{r.status}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
