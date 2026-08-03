"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Stats = {
  tenants_by_status: Record<string, number>;
  total_tenants: number;
  total_orders: number;
  total_topup_revenue_cents: number;
  total_charged_cents: number;
  active_minutes_used_this_period: number;
};

const STATUS_LABELS: Record<string, string> = {
  pending_kyc: "In onboarding",
  pending_admin_review: "In attesa di revisione",
  active: "Attivi",
  suspended: "Sospesi",
  rejected: "Rifiutati",
};

export default function AdminOverviewPage() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    api.get("/api/admin/stats").then(setStats).catch(() => {});
  }, []);

  if (!stats) return <div>Caricamento...</div>;

  return (
    <div>
      <h1>Panoramica</h1>
      <p className="muted">Vista d&apos;insieme della piattaforma.</p>

      <div className="stat-grid">
        <div className="stat-tile">
          <div className="value">{stats.total_tenants}</div>
          <div className="label">Pizzerie totali</div>
        </div>
        <div className="stat-tile">
          <div className="value">{stats.total_orders}</div>
          <div className="label">Ordini totali</div>
        </div>
        <div className="stat-tile">
          <div className="value">{(stats.total_topup_revenue_cents / 100).toFixed(2)} €</div>
          <div className="label">Ricariche totali (simulate)</div>
        </div>
        <div className="stat-tile">
          <div className="value">{(stats.total_charged_cents / 100).toFixed(2)} €</div>
          <div className="label">Addebitato (canoni + extra)</div>
        </div>
        <div className="stat-tile">
          <div className="value">{stats.active_minutes_used_this_period}</div>
          <div className="label">Minuti usati (tenant attivi, periodo corrente)</div>
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
