"use client";
import { useEffect, useState } from "react";
import { api, API_URL, uploadFile } from "@/lib/api";

type Asset = { id: string; type: "image" | "video"; source_url: string; thumbnail_url: string | null; caption: string | null; status: string };
type Status = { type: "ok" | "error"; text: string } | null;

function StatusInline({ status }: { status: Status }) {
  if (!status) return null;
  return (
    <span style={{ marginLeft: 12, fontWeight: 600, fontSize: "0.9rem", color: status.type === "ok" ? "var(--success)" : "var(--accent)" }}>
      {status.type === "ok" ? "✓ " : "⚠ "}{status.text}
    </span>
  );
}

export default function LibreriaPage() {
  const [assets, setAssets] = useState<Asset[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState<Status>(null);

  function reload() {
    setError(null);
    api.get("/api/promoziona/content/assets").then(setAssets).catch((e) => setError(e.message));
  }

  useEffect(reload, []);

  async function uploadAsset(file: File) {
    setUploading(true);
    setStatus(null);
    try {
      const created = await uploadFile("/api/promoziona/content/assets", file);
      setAssets((prev) => [created, ...(prev || [])]);
      setStatus({ type: "ok", text: "Contenuto caricato" });
    } catch (err) {
      setStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setUploading(false);
    }
  }

  async function onFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files ? Array.from(e.target.files) : [];
    for (const file of files) await uploadAsset(file);
    e.target.value = "";
  }

  async function removeAsset(id: string) {
    await api.delete(`/api/promoziona/content/assets/${id}`);
    setAssets((prev) => (prev || []).filter((a) => a.id !== id));
  }

  if (!assets) {
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
    <div style={{ maxWidth: 900 }}>
      <h1>Libreria contenuti</h1>
      <p className="muted">
        Foto e video sorgente per i tuoi Reel — carica qui la materia prima (piatti, ambiente, momenti al lavoro), poi la useremo
        per creare i video promozionali.
      </p>

      <div className="card">
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
          <input
            type="file"
            multiple
            accept=".jpg,.jpeg,.png,.webp,.mp4,.mov,.webm"
            onChange={onFileInput}
            disabled={uploading}
            style={{ width: "auto" }}
          />
          {uploading && <span className="muted">Caricamento...</span>}
          <StatusInline status={status} />
        </div>

        {assets.length === 0 ? (
          <p className="muted">Nessun contenuto ancora — caricane uno sopra.</p>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12 }}>
            {assets.map((a) => (
              <div key={a.id} style={{ position: "relative" }}>
                {a.type === "video" ? (
                  <video
                    src={`${API_URL}${a.source_url}`}
                    style={{ width: "100%", aspectRatio: "1 / 1", objectFit: "cover", borderRadius: 8, border: "1px solid var(--border)", background: "#000" }}
                    muted
                    controls
                  />
                ) : (
                  <img
                    src={`${API_URL}${a.source_url}`}
                    alt={a.caption || "Contenuto"}
                    style={{ width: "100%", aspectRatio: "1 / 1", objectFit: "cover", borderRadius: 8, border: "1px solid var(--border)" }}
                  />
                )}
                <span
                  className="badge"
                  style={{ position: "absolute", top: 6, left: 6, fontSize: "0.7rem", padding: "1px 7px" }}
                >
                  {a.type === "video" ? "🎬 video" : "🖼 foto"}
                </span>
                <button
                  className="secondary"
                  onClick={() => removeAsset(a.id)}
                  style={{ position: "absolute", top: 6, right: 6, padding: "2px 8px", fontSize: "0.75rem" }}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
