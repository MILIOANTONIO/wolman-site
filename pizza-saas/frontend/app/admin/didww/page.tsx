"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Status = { type: "ok" | "error"; text: string } | null;

type Settings = { suspend_grace_days: number; terminate_after_days: number; auto_enforcement_enabled: boolean };

type TenantRow = {
  tenant_id: string; business_name: string; tenant_status: string; billing_status: string;
  prepaid_balance_cents: number; past_due_since: string | null; suspended_at: string | null;
  phone_number: string | null; activation_status: string | null;
  verification_status: string | null; verification_reject_reason: string | null;
  numbers: { e164_number: string; status: string }[];
};

type Category = { key: string; title: string; icon: string; rows: TenantRow[] };

const BILLING_LABEL: Record<string, { icon: string; label: string }> = {
  trial: { icon: "🆕", label: "Trial" },
  active: { icon: "✅", label: "Attivo" },
  past_due: { icon: "⚠️", label: "Insoluto" },
  suspended: { icon: "⛔", label: "Sospeso" },
};

const ACTIVATION_LABEL: Record<string, string> = {
  non_ordinato: "Numero scelto, non ancora ordinato",
  in_elaborazione: "Ordine in elaborazione",
  in_verifica: "In revisione DIDWW",
  attivo: "Attivo",
  bloccato: "Bloccato",
  scaduto: "Scaduto/cancellato",
};

function StatusInline({ status }: { status: Status }) {
  if (!status) return null;
  return (
    <span style={{ marginLeft: 12, fontWeight: 600, fontSize: "0.9rem", color: status.type === "ok" ? "var(--success)" : "var(--accent)" }}>
      {status.type === "ok" ? "✓ " : "⚠ "}{status.text}
    </span>
  );
}

function formatNumber(n: string | null): string {
  if (!n) return "—";
  const digits = n.replace(/^\+/, "");
  return digits.startsWith("39") ? `+${digits.slice(0, 2)} ${digits.slice(2)}` : n;
}

function categorize(rows: TenantRow[]): Category[] {
  const buckets: Record<string, TenantRow[]> = {
    suspended: [], past_due: [], rejected: [], blocked_expired: [], in_review: [], active: [], not_ordered: [],
  };
  for (const r of rows) {
    if (r.billing_status === "suspended") buckets.suspended.push(r);
    else if (r.billing_status === "past_due") buckets.past_due.push(r);
    else if (r.verification_status === "rejected") buckets.rejected.push(r);
    else if (r.activation_status === "bloccato" || r.activation_status === "scaduto") buckets.blocked_expired.push(r);
    else if (r.activation_status === "in_verifica" || r.activation_status === "in_elaborazione") buckets.in_review.push(r);
    else if (r.activation_status === "attivo") buckets.active.push(r);
    else buckets.not_ordered.push(r);
  }
  return [
    { key: "suspended", title: "Sospesi (mancato pagamento)", icon: "⛔", rows: buckets.suspended },
    { key: "past_due", title: "Insoluti (in periodo di grazia)", icon: "⚠️", rows: buckets.past_due },
    { key: "rejected", title: "Verifica documenti respinta", icon: "🚫", rows: buckets.rejected },
    { key: "blocked_expired", title: "Bloccati o scaduti", icon: "🔒", rows: buckets.blocked_expired },
    { key: "in_review", title: "In revisione DIDWW", icon: "🕓", rows: buckets.in_review },
    { key: "active", title: "Attivi", icon: "✅", rows: buckets.active },
    { key: "not_ordered", title: "Numero scelto, ordine non ancora inviato", icon: "📋", rows: buckets.not_ordered },
  ];
}

export default function DidwwAdminPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsStatus, setSettingsStatus] = useState<Status>(null);

  const [rows, setRows] = useState<TenantRow[]>([]);
  const [loadingRows, setLoadingRows] = useState(true);
  const [actingOn, setActingOn] = useState<string | null>(null);

  function loadAll() {
    api.get("/api/admin/didww/settings").then(setSettings).catch(() => {});
    setLoadingRows(true);
    api.get("/api/admin/didww/overview").then(setRows).catch(() => {}).finally(() => setLoadingRows(false));
  }

  useEffect(loadAll, []);

  async function saveSettings(e: React.FormEvent) {
    e.preventDefault();
    if (!settings) return;
    setSavingSettings(true);
    setSettingsStatus(null);
    try {
      await api.put("/api/admin/didww/settings", settings);
      setSettingsStatus({ type: "ok", text: "Salvato" });
    } catch (err) {
      setSettingsStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSavingSettings(false);
    }
  }

  async function act(tenantId: string, action: "suspend-now" | "reactivate-now" | "terminate-now") {
    if (action === "terminate-now" && !confirm("Cancellare davvero il numero? Non è reversibile.")) return;
    setActingOn(tenantId + action);
    try {
      await api.post(`/api/admin/tenants/${tenantId}/didww/${action}`, {});
      loadAll();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Errore");
    } finally {
      setActingOn(null);
    }
  }

  const categories = categorize(rows);

  return (
    <div>
      <h1>DIDWW — numeri e fatturazione</h1>
      <p className="muted">Comportamento automatico in caso di mancato pagamento del canone: sospensione, poi cancellazione definitiva del numero.</p>

      {settings && (
        <div className="card">
          <h2>Impostazioni</h2>
          <form onSubmit={saveSettings}>
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox" style={{ width: "auto" }}
                checked={settings.auto_enforcement_enabled}
                onChange={(e) => setSettings({ ...settings, auto_enforcement_enabled: e.target.checked })}
              />
              Automazione attiva
            </label>
            <p className="muted" style={{ fontSize: "0.8rem", marginTop: 2 }}>Se disattivata, nessuna sospensione o cancellazione avviene da sola — solo le azioni manuali qui sotto.</p>

            <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
              <div style={{ flex: 1 }}>
                <label>Giorni di grazia prima della sospensione</label>
                <input
                  type="number" min={0} value={settings.suspend_grace_days}
                  onChange={(e) => setSettings({ ...settings, suspend_grace_days: parseInt(e.target.value) || 0 })}
                />
              </div>
              <div style={{ flex: 1 }}>
                <label>Giorni da sospeso prima della cancellazione</label>
                <input
                  type="number" min={0} value={settings.terminate_after_days}
                  onChange={(e) => setSettings({ ...settings, terminate_after_days: parseInt(e.target.value) || 0 })}
                />
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", marginTop: 16 }}>
              <button type="submit" disabled={savingSettings}>{savingSettings ? "Salvataggio..." : "Salva impostazioni"}</button>
              <StatusInline status={settingsStatus} />
            </div>
          </form>
        </div>
      )}

      {loadingRows && <p className="muted">Caricamento...</p>}

      {!loadingRows && (
        <div className="stat-grid">
          {categories.map((c) => (
            <div key={c.key} className="stat-tile">
              <div>
                <div className="value">{c.rows.length}</div>
                <div className="label">{c.title}</div>
              </div>
              <div className="stat-icon">{c.icon}</div>
            </div>
          ))}
        </div>
      )}

      {!loadingRows && rows.length === 0 && (
        <div className="card"><p className="muted">Nessuna pizzeria ha ancora un numero DIDWW in corso.</p></div>
      )}

      {!loadingRows && categories.filter((c) => c.rows.length > 0).map((cat) => (
        <div key={cat.key} className="card">
          <h2>{cat.icon} {cat.title}</h2>
          {cat.rows.map((r) => {
            const b = BILLING_LABEL[r.billing_status] || { icon: "❔", label: r.billing_status };
            return (
              <div key={r.tenant_id} className="order-card" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                  <div>
                    <strong>{r.business_name}</strong>
                    <span className="badge" style={{ marginLeft: 8 }}>{b.icon} {b.label}</span>
                    <span className="muted" style={{ marginLeft: 8 }}>{formatNumber(r.phone_number)}</span>
                  </div>
                  <div className="muted">saldo: {(r.prepaid_balance_cents / 100).toFixed(2)} €</div>
                </div>
                <div className="muted" style={{ fontSize: "0.85rem" }}>
                  {r.activation_status && `Numero: ${ACTIVATION_LABEL[r.activation_status] || r.activation_status}`}
                  {r.numbers.length > 0 && ` — ${r.numbers.map((n) => `${n.e164_number} (${n.status})`).join(", ")}`}
                </div>
                {r.verification_reject_reason && <div className="error" style={{ fontSize: "0.8rem" }}>Motivo rifiuto: {r.verification_reject_reason}</div>}
                {r.past_due_since && <div className="muted" style={{ fontSize: "0.8rem" }}>Insoluto dal {new Date(r.past_due_since).toLocaleDateString("it-IT")}</div>}
                {r.suspended_at && <div className="muted" style={{ fontSize: "0.8rem" }}>Sospeso dal {new Date(r.suspended_at).toLocaleDateString("it-IT")}</div>}
                <div style={{ display: "flex", gap: 8 }}>
                  {r.billing_status !== "suspended" && (
                    <button className="secondary" disabled={actingOn === r.tenant_id + "suspend-now"} onClick={() => act(r.tenant_id, "suspend-now")}>
                      Sospendi ora
                    </button>
                  )}
                  {(r.billing_status === "past_due" || r.billing_status === "suspended") && (
                    <button disabled={actingOn === r.tenant_id + "reactivate-now"} onClick={() => act(r.tenant_id, "reactivate-now")}>
                      Riattiva ora
                    </button>
                  )}
                  {r.billing_status === "suspended" && (
                    <button className="secondary" disabled={actingOn === r.tenant_id + "terminate-now"} onClick={() => act(r.tenant_id, "terminate-now")}>
                      Cancella numero ora
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
