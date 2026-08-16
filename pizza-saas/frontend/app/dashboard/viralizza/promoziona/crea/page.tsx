"use client";
import { useEffect, useRef, useState } from "react";
import { api, API_URL } from "@/lib/api";

type Asset = { id: string; type: "image" | "video"; source_url: string; thumbnail_url: string | null; caption: string | null };
type Template = { id: string; name: string; category: string; duration: number; ken_burns: string; text_position: string; accent_color: string };
type Reel = {
  id: string; template_id: string; status: string; duration: number;
  video_url: string | null; thumbnail_url: string | null; caption: string | null; created_at: string;
};
type Status = { type: "ok" | "error"; text: string } | null;

const STATUS_LABEL: Record<string, string> = {
  draft: "Bozza", queued: "In coda", rendering: "In lavorazione...", ready: "Pronto", failed: "Errore",
};

function StatusInline({ status }: { status: Status }) {
  if (!status) return null;
  return (
    <span style={{ marginLeft: 12, fontWeight: 600, fontSize: "0.9rem", color: status.type === "ok" ? "var(--success)" : "var(--accent)" }}>
      {status.type === "ok" ? "✓ " : "⚠ "}{status.text}
    </span>
  );
}

export default function CreaReelPage() {
  const [assets, setAssets] = useState<Asset[] | null>(null);
  const [templates, setTemplates] = useState<Template[] | null>(null);
  const [reels, setReels] = useState<Reel[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [selectedAsset, setSelectedAsset] = useState<string | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [caption, setCaption] = useState("");
  const [generating, setGenerating] = useState(false);
  const [status, setStatus] = useState<Status>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function reload() {
    setError(null);
    api.get("/api/promoziona/content/assets").then((all: Asset[]) => setAssets(all.filter((a) => a.type === "image"))).catch((e) => setError(e.message));
    api.get("/api/promoziona/templates").then(setTemplates).catch((e) => setError(e.message));
    api.get("/api/promoziona/reels").then(setReels).catch((e) => setError(e.message));
  }

  useEffect(reload, []);
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  function pollReel(reelId: string) {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      const updated: Reel = await api.get(`/api/promoziona/reels/${reelId}`);
      setReels((prev) => (prev || []).map((r) => (r.id === reelId ? updated : r)));
      if (updated.status === "ready" || updated.status === "failed") {
        if (pollRef.current) clearInterval(pollRef.current);
        setGenerating(false);
        setStatus(
          updated.status === "ready"
            ? { type: "ok", text: "Reel pronto!" }
            : { type: "error", text: "Generazione fallita, riprova" }
        );
      }
    }, 1500);
  }

  async function createAndGenerate() {
    if (!selectedAsset || !selectedTemplate) return;
    setGenerating(true);
    setStatus(null);
    try {
      const draft: Reel = await api.post("/api/promoziona/reels", {
        template_id: selectedTemplate, source_asset_id: selectedAsset, caption: caption || null,
      });
      setReels((prev) => [draft, ...(prev || [])]);
      const queued: Reel = await api.post(`/api/promoziona/reels/${draft.id}/generate`);
      setReels((prev) => (prev || []).map((r) => (r.id === draft.id ? queued : r)));
      pollReel(draft.id);
    } catch (err) {
      setGenerating(false);
      setStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    }
  }

  async function removeReel(id: string) {
    await api.delete(`/api/promoziona/reels/${id}`);
    setReels((prev) => (prev || []).filter((r) => r.id !== id));
  }

  if (!assets || !templates || !reels) {
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
      <h1>Crea Reel</h1>
      <p className="muted">Scegli una foto dalla libreria e uno stile — il video viene creato in automatico, senza bisogno di editing.</p>

      <div className="card">
        <h2>1. Scegli la foto</h2>
        {assets.length === 0 ? (
          <p className="muted">
            Nessuna foto in libreria — <a href="/dashboard/viralizza/promoziona/libreria">caricane una qui</a>.
          </p>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: 10 }}>
            {assets.map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => setSelectedAsset(a.id)}
                style={{
                  padding: 0, border: selectedAsset === a.id ? "3px solid var(--accent)" : "1px solid var(--border)",
                  borderRadius: 8, overflow: "hidden", background: "transparent", cursor: "pointer",
                }}
              >
                <img src={`${API_URL}${a.source_url}`} alt="" style={{ width: "100%", aspectRatio: "1 / 1", objectFit: "cover", display: "block" }} />
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <h2>2. Scegli lo stile</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 10 }}>
          {templates.map((t) => (
            <button
              key={t.id}
              type="button"
              className={selectedTemplate === t.id ? "" : "secondary"}
              onClick={() => setSelectedTemplate(t.id)}
              style={{ textAlign: "left" }}
            >
              <div>{t.name}</div>
              <div className="muted" style={{ fontSize: "0.75rem", fontWeight: 400 }}>{t.duration}s · {t.category}</div>
            </button>
          ))}
        </div>

        <label style={{ marginTop: 16 }}>Testo sul video (opzionale)</label>
        <input placeholder='es. "Margherita fatta a mano"' value={caption} onChange={(e) => setCaption(e.target.value)} maxLength={80} />

        <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 12 }}>
          <button type="button" disabled={!selectedAsset || !selectedTemplate || generating} onClick={createAndGenerate}>
            {generating ? "Creazione in corso..." : "Crea Reel"}
          </button>
          <StatusInline status={status} />
        </div>
      </div>

      <div className="card">
        <h2>I tuoi Reel</h2>
        {reels.length === 0 ? (
          <p className="muted">Nessun Reel ancora — crealo qui sopra.</p>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 14 }}>
            {reels.map((r) => (
              <div key={r.id}>
                {r.status === "ready" && r.video_url ? (
                  <video
                    src={`${API_URL}${r.video_url}`}
                    poster={r.thumbnail_url ? `${API_URL}${r.thumbnail_url}` : undefined}
                    controls
                    style={{ width: "100%", aspectRatio: "9 / 16", objectFit: "cover", borderRadius: 8, background: "#000" }}
                  />
                ) : (
                  <div
                    style={{
                      width: "100%", aspectRatio: "9 / 16", borderRadius: 8, background: "var(--card-hover)",
                      display: "flex", alignItems: "center", justifyContent: "center", textAlign: "center", padding: 12,
                    }}
                  >
                    <span className="muted">{r.status === "failed" ? "⚠ Generazione fallita" : STATUS_LABEL[r.status] || r.status}</span>
                  </div>
                )}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 6 }}>
                  <span className="muted" style={{ fontSize: "0.8rem" }}>{r.caption || "—"}</span>
                  <button className="secondary" onClick={() => removeReel(r.id)} style={{ padding: "2px 8px", fontSize: "0.75rem" }}>
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
