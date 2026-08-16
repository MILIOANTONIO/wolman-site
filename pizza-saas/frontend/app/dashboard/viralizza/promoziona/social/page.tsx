"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Provider = { provider: string; label: string; available: boolean };
type Connection = { id: string; provider: string; account_name: string | null; status: string };

export default function SocialPage() {
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [connections, setConnections] = useState<Connection[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    setError(null);
    api.get("/api/promoziona/social/providers").then(setProviders).catch((e) => setError(e.message));
    api.get("/api/promoziona/social/connections").then(setConnections).catch((e) => setError(e.message));
  }

  useEffect(reload, []);

  if (!providers || !connections) {
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
              <button type="button" className="secondary" disabled title={p.available ? undefined : "Non ancora disponibile"}>
                Connetti
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
