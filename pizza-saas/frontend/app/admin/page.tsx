"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ResponsiveContainer, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";

type DailyPoint = { date: string; new_tenants: number; orders: number };

type Stats = {
  tenants_by_status: Record<string, number>;
  total_tenants: number;
  total_orders: number;
  total_topup_revenue_cents: number;
  total_charged_cents: number;
  active_minutes_used_this_period: number;
  daily_last_14_days: DailyPoint[];
};

const STATUS_LABELS: Record<string, string> = {
  pending_kyc: "In onboarding",
  pending_admin_review: "In attesa di revisione",
  active: "Attivi",
  suspended: "Sospesi",
  rejected: "Rifiutati",
};

function fmtDay(iso: string) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("it-IT", { day: "2-digit", month: "2-digit" });
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number; name: string; color: string }[]; label?: string }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 8, padding: "6px 10px", fontSize: "0.85rem" }}>
      <div className="muted">{label ? fmtDay(label) : ""}</div>
      {payload.map((p) => (
        <div key={p.name} style={{ color: p.color, fontWeight: 700 }}>{p.value} {p.name}</div>
      ))}
    </div>
  );
}

export default function AdminOverviewPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    setError(null);
    api.get("/api/admin/stats").then(setStats).catch((e) => setError(e.message));
  }

  useEffect(reload, []);

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

  return (
    <div>
      <h1>Panoramica</h1>
      <p className="muted">Vista d&apos;insieme della piattaforma.</p>

      <div className="stat-grid">
        <div className="stat-tile">
          <div>
            <div className="value">{stats.total_tenants}</div>
            <div className="label">Pizzerie totali</div>
          </div>
          <div className="stat-icon">🍕</div>
        </div>
        <div className="stat-tile">
          <div>
            <div className="value">{stats.total_orders}</div>
            <div className="label">Ordini totali</div>
          </div>
          <div className="stat-icon info">🛒</div>
        </div>
        <div className="stat-tile">
          <div>
            <div className="value">{(stats.total_topup_revenue_cents / 100).toFixed(2)} €</div>
            <div className="label">Ricariche totali (simulate)</div>
          </div>
          <div className="stat-icon success">💶</div>
        </div>
        <div className="stat-tile">
          <div>
            <div className="value">{(stats.total_charged_cents / 100).toFixed(2)} €</div>
            <div className="label">Addebitato (canoni + extra)</div>
          </div>
          <div className="stat-icon warning">🧾</div>
        </div>
        <div className="stat-tile">
          <div>
            <div className="value">{stats.active_minutes_used_this_period}</div>
            <div className="label">Minuti usati (attivi, periodo corrente)</div>
          </div>
          <div className="stat-icon info">⏱️</div>
        </div>
      </div>

      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        <div className="chart-card" style={{ flex: "1 1 380px" }}>
          <h2>Nuove pizzerie (ultimi 14 giorni)</h2>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={stats.daily_last_14_days} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="tenantsGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="date" tickFormatter={fmtDay} stroke="var(--muted)" fontSize={12} tickLine={false} axisLine={false} />
              <YAxis allowDecimals={false} stroke="var(--muted)" fontSize={12} tickLine={false} axisLine={false} width={30} />
              <Tooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="new_tenants" name="nuove pizzerie" stroke="var(--accent)" strokeWidth={2} fill="url(#tenantsGradient)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card" style={{ flex: "1 1 380px" }}>
          <h2>Ordini piattaforma (ultimi 14 giorni)</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={stats.daily_last_14_days} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="date" tickFormatter={fmtDay} stroke="var(--muted)" fontSize={12} tickLine={false} axisLine={false} />
              <YAxis allowDecimals={false} stroke="var(--muted)" fontSize={12} tickLine={false} axisLine={false} width={30} />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="orders" name="ordini" fill="var(--info)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card">
        <h2>Pizzerie per stato</h2>
        {Object.entries(STATUS_LABELS).map(([code, label]) => (
          <div key={code} className="order-card">
            <span>{label}</span>
            <span className="badge">{stats.tenants_by_status[code] || 0}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
