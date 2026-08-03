"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type TenantSummary = { id: string; business_name: string; category: string; status: string; city: string | null; created_at: string };

export default function AdminTenantsPage() {
  const [tenants, setTenants] = useState<TenantSummary[] | null>(null);
  const [filter, setFilter] = useState("pending_admin_review");

  useEffect(() => {
    api.get(`/api/admin/tenants?status=${filter}`).then(setTenants).catch(() => setTenants(null));
  }, [filter]);

  return (
    <div>
      <h1>Pizzerie</h1>
      <label>Filtra per stato</label>
      <select value={filter} onChange={(e) => setFilter(e.target.value)} style={{ marginBottom: 20, maxWidth: 320 }}>
        <option value="pending_admin_review">In attesa di revisione</option>
        <option value="pending_kyc">In onboarding (KYC incompleto)</option>
        <option value="active">Attivi</option>
        <option value="rejected">Rifiutati</option>
      </select>

      {tenants?.length === 0 && <p className="muted">Nessun tenant in questo stato.</p>}
      {tenants?.map((t) => (
        <Link key={t.id} href={`/admin/tenants/${t.id}`} style={{ textDecoration: "none" }}>
          <div className="order-card">
            <div>
              <strong>{t.business_name || "(nome non impostato)"}</strong>
              <div className="muted">{t.category} — {t.city || "città non impostata"}</div>
            </div>
            <span className="badge">{t.status}</span>
          </div>
        </Link>
      ))}
    </div>
  );
}
