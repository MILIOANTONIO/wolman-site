"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Transaction = {
  id: string; type: string; amount_cents: number; balance_after_cents: number;
  description: string | null; created_at: string;
};

type Billing = {
  plan_code: string; plan_name: string; plan_price_cents: number;
  included_minutes: number; minutes_used: number; overage_minutes: number;
  overage_cents_per_minute: number; prepaid_balance_cents: number;
  current_period_started_at: string | null; transactions: Transaction[];
};

const TX_LABELS: Record<string, string> = {
  topup: "Ricarica",
  plan_charge: "Canone piano",
  overage_charge: "Extra oltre soglia",
  manual_adjustment: "Rettifica",
};

const PRESET_AMOUNTS = [5000, 10000, 20000, 50000];

export default function ConsumiPage() {
  const [billing, setBilling] = useState<Billing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toppingUp, setToppingUp] = useState(false);

  function reload() {
    api.get("/api/dashboard/billing").then(setBilling).catch((e) => setError(e.message));
  }

  useEffect(reload, []);

  async function topup(amountCents: number) {
    setToppingUp(true);
    setError(null);
    try {
      await api.post("/api/dashboard/billing/topup", { amount_cents: amountCents });
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore");
    } finally {
      setToppingUp(false);
    }
  }

  if (!billing) return <div className="page">{error ? <div className="error">{error}</div> : "Caricamento..."}</div>;

  const usagePct = billing.included_minutes > 0 ? Math.min(100, (billing.minutes_used / billing.included_minutes) * 100) : 0;
  const balanceLow = billing.prepaid_balance_cents < billing.plan_price_cents;

  return (
    <div className="page" style={{ maxWidth: 800 }}>
      <nav>
        <a href="/dashboard">Ordini</a>
        <a href="/dashboard/consumi">Consumi</a>
        <a href="/onboarding">Impostazioni</a>
      </nav>
      <h1>Consumi e fatturazione</h1>
      <p className="muted">Modello prepagato: ricarica il credito, canone e minuti extra si scalano automaticamente. Nessun addebito a sorpresa dopo l&apos;uso.</p>
      {error && <div className="error">{error}</div>}

      <div className="card">
        <h2>Saldo credito</h2>
        <div style={{ fontSize: "2rem", fontWeight: 700, color: balanceLow ? "var(--accent)" : "var(--text)" }}>
          {(billing.prepaid_balance_cents / 100).toFixed(2)} €
        </div>
        {balanceLow && <p style={{ color: "var(--accent)" }}>Saldo basso: potrebbe non bastare per il prossimo rinnovo del piano ({(billing.plan_price_cents / 100).toFixed(2)} €).</p>}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
          {PRESET_AMOUNTS.map((amount) => (
            <button key={amount} onClick={() => topup(amount)} disabled={toppingUp}>
              + {(amount / 100).toFixed(0)} €
            </button>
          ))}
        </div>
        <p className="muted" style={{ marginTop: 8 }}>Ricarica simulata: nessun pagamento reale finché non colleghiamo un gateway di pagamento vero.</p>
      </div>

      <div className="card">
        <h2>Piano attuale — {billing.plan_name}</h2>
        <p>{(billing.plan_price_cents / 100).toFixed(2)} €/mese, {billing.included_minutes} minuti inclusi</p>
        <div style={{ background: "var(--border)", borderRadius: 8, height: 10, overflow: "hidden", marginTop: 8 }}>
          <div style={{ width: `${usagePct}%`, background: usagePct >= 100 ? "var(--accent)" : "var(--success)", height: "100%" }} />
        </div>
        <p className="muted" style={{ marginTop: 6 }}>
          {billing.minutes_used} / {billing.included_minutes} minuti usati in questo periodo
          {billing.overage_minutes > 0 && ` — ${billing.overage_minutes} minuti extra a ${(billing.overage_cents_per_minute / 100).toFixed(2)} €/min`}
        </p>
        {billing.current_period_started_at && (
          <p className="muted">Periodo iniziato il {new Date(billing.current_period_started_at).toLocaleDateString("it-IT")}</p>
        )}
      </div>

      <div className="card">
        <h2>Movimenti</h2>
        {billing.transactions.length === 0 && <p className="muted">Nessun movimento ancora.</p>}
        <table>
          <thead>
            <tr><th>Data</th><th>Tipo</th><th>Importo</th><th>Saldo dopo</th><th>Descrizione</th></tr>
          </thead>
          <tbody>
            {billing.transactions.map((t) => (
              <tr key={t.id}>
                <td>{new Date(t.created_at).toLocaleString("it-IT")}</td>
                <td>{TX_LABELS[t.type] || t.type}</td>
                <td style={{ color: t.amount_cents < 0 ? "var(--accent)" : "var(--success)" }}>
                  {t.amount_cents >= 0 ? "+" : ""}{(t.amount_cents / 100).toFixed(2)} €
                </td>
                <td>{(t.balance_after_cents / 100).toFixed(2)} €</td>
                <td className="muted">{t.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
