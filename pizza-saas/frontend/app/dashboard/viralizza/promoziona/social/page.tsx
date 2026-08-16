"use client";
import { useEffect, useState } from "react";
import { api, API_URL } from "@/lib/api";

type Provider = { provider: string; label: string; available: boolean };
type Connection = { id: string; provider: string; account_name: string | null; status: string };
type SocialAccountRow = {
  id: string; connection_id: string; provider: string; type: string; external_id: string;
  name: string | null; username: string | null; is_selected: boolean;
};

const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  page: "Pagina Facebook",
  instagram_business: "Instagram",
  ad_account: "Account pubblicitario",
};

export default function SocialPage() {
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [connections, setConnections] = useState<Connection[] | null>(null);
  const [accounts, setAccounts] = useState<SocialAccountRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);
  const [metaConnected, setMetaConnected] = useState(false);
  const [metaError, setMetaError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setMetaConnected(params.get("meta_connected") === "1");
    setMetaError(params.get("meta_error"));
  }, []);

  function reload() {
    setError(null);
    api.get("/api/promoziona/social/providers").then(setProviders).catch((e) => setError(e.message));
    api.get("/api/promoziona/social/connections").then(setConnections).catch((e) => setError(e.message));
    api.get("/api/promoziona/social/accounts").then(setAccounts).catch((e) => setError(e.message));
  }

  useEffect(reload, []);

  async function toggleAccount(id: string) {
    setToggling(id);
    try {
      await api.post(`/api/promoziona/social/accounts/${id}/select`);
      reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setToggling(null);
    }
  }

  async function disconnect(id: string) {
    if (!confirm("Scollegare questo account? Le pagine/Instagram collegati non saranno più utilizzabili per pubblicare finché non riconnetti.")) return;
    setDisconnecting(id);
    try {
      await api.delete(`/api/promoziona/social/connections/${id}`);
      reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDisconnecting(null);
    }
  }

  if (!providers || !connections || !accounts) {
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
    <div style={{ maxWidth: 700 }}>
      <h1>Social</h1>
      <p className="muted">Collega i tuoi account per pubblicare i Reel e promuoverli direttamente da qui.</p>

      {metaConnected && (
        <div className="card" style={{ marginBottom: 16, borderColor: "var(--accent)" }}>
          Account Meta collegato con successo.
        </div>
      )}
      {metaError && (
        <div className="error" style={{ marginBottom: 16 }}>
          Connessione non riuscita: {metaError}
        </div>
      )}
      {error && <div className="error" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="card">
        {providers.map((p) => {
          const conn = connections.find((c) => c.provider === p.provider);
          return (
            <div
              key={p.provider}
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "14px 0", borderBottom: "1px solid var(--border)",
              }}
            >
              <div>
                <div style={{ fontWeight: 600 }}>{p.label}</div>
                <div className="muted" style={{ fontSize: "0.85rem" }}>
                  {conn ? `Connesso — ${conn.account_name || conn.status}` : p.available ? "Non connesso" : "In arrivo"}
                </div>
              </div>
              {conn ? (
                <button
                  type="button"
                  className="secondary"
                  disabled={disconnecting === conn.id}
                  onClick={() => disconnect(conn.id)}
                >
                  {disconnecting === conn.id ? "..." : "Scollega"}
                </button>
              ) : p.available ? (
                <a href={`${API_URL}/api/promoziona/social/connect/${p.provider}`} className="secondary" style={{ textDecoration: "none" }}>
                  Connetti
                </a>
              ) : (
                <button type="button" className="secondary" disabled title="Non ancora disponibile">
                  Connetti
                </button>
              )}
            </div>
          );
        })}
      </div>

      {accounts.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3 style={{ marginTop: 0 }}>Pagine e account collegati</h3>
          <p className="muted" style={{ fontSize: "0.85rem" }}>
            Scegli quali usare per pubblicare i Reel e gestire le inserzioni. Puoi cambiarli in qualsiasi momento.
          </p>
          {accounts.map((a) => (
            <label
              key={a.id}
              style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "10px 0", borderBottom: "1px solid var(--border)", cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={a.is_selected}
                disabled={toggling === a.id}
                onChange={() => toggleAccount(a.id)}
              />
              <div>
                <div style={{ fontWeight: 600 }}>{a.name || a.username || a.external_id}{a.username ? ` (@${a.username})` : ""}</div>
                <div className="muted" style={{ fontSize: "0.8rem" }}>{ACCOUNT_TYPE_LABELS[a.type] || a.type}</div>
              </div>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
