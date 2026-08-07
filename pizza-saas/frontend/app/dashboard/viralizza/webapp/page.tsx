"use client";
import { useEffect, useState } from "react";
import { api, API_URL, uploadFile } from "@/lib/api";
import { CameraButton } from "@/lib/CameraCapture";

type Photo = { id: string; category: string; url: string; caption: string | null; position: number };
type Status = { type: "ok" | "error"; text: string } | null;
type PageDesign = { public_page_template: string; public_page_headline: string | null; public_page_tagline: string | null };

const TEMPLATE_OPTIONS: { id: string; name: string; desc: string; bg: string; accent: string; ink: string; font: string }[] = [
  { id: "rustico", name: "Forno a Legna", desc: "Calda e artigianale, stile trattoria", bg: "#F4EAD9", accent: "#B23A2E", ink: "#2C1B10", font: "Georgia, serif" },
  { id: "moderna", name: "Napoletana Moderna", desc: "Minimal ed editoriale", bg: "#FAFAF8", accent: "#C4351E", ink: "#17140F", font: "-apple-system, sans-serif" },
  { id: "notte", name: "Notte Italiana", desc: "Scura ed elegante, oro su nero", bg: "#14100D", accent: "#C99A4E", ink: "#F1E6D6", font: "Georgia, serif" },
  { id: "vivace", name: "Vivace", desc: "Colorata e giocosa, per i social", bg: "#FFF7EA", accent: "#E2472A", ink: "#21160D", font: "-apple-system, sans-serif" },
];
type WidgetSettings = {
  widget_avatar_url: string | null;
  widget_color_1: string;
  widget_color_2: string;
  widget_action_text: string;
  widget_variant: string;
  widget_placement: string;
  widget_dismissible: boolean;
};

function StatusInline({ status }: { status: Status }) {
  if (!status) return null;
  return (
    <span style={{ marginLeft: 12, fontWeight: 600, fontSize: "0.9rem", color: status.type === "ok" ? "var(--success)" : "var(--accent)" }}>
      {status.type === "ok" ? "✓ " : "⚠ "}{status.text}
    </span>
  );
}

function buildEmbedCode(agentId: string, w: WidgetSettings): string {
  const attrs = [
    `agent-id="${agentId}"`,
    w.widget_avatar_url
      ? `avatar-image-url="${API_URL}${w.widget_avatar_url}"`
      : `avatar-orb-color-1="${w.widget_color_1}" avatar-orb-color-2="${w.widget_color_2}"`,
    `action-text="${w.widget_action_text}"`,
    `variant="${w.widget_variant}"`,
    `placement="${w.widget_placement}"`,
    w.widget_dismissible ? `dismissible="true"` : `dismissible="false"`,
  ].join("\n  ");
  return `<elevenlabs-convai\n  ${attrs}\n></elevenlabs-convai>\n<script src="https://unpkg.com/@elevenlabs/convai-widget-embed" async type="text/javascript"></script>`;
}

export default function ViralizzaPage() {
  const [slug, setSlug] = useState<string | null>(null);
  const [businessName, setBusinessName] = useState<string | null>(null);
  const [agentId, setAgentId] = useState<string | null>(null);
  const [photos, setPhotos] = useState<Photo[] | null>(null);
  const [widget, setWidget] = useState<WidgetSettings | null>(null);
  const [design, setDesign] = useState<PageDesign | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState<Status>(null);
  const [widgetStatus, setWidgetStatus] = useState<Status>(null);
  const [savingWidget, setSavingWidget] = useState(false);
  const [savingDesign, setSavingDesign] = useState(false);
  const [designStatus, setDesignStatus] = useState<Status>(null);
  const [copied, setCopied] = useState(false);
  const [codeCopied, setCodeCopied] = useState(false);

  function reload() {
    setError(null);
    api.get("/api/onboarding/tenant").then((t) => { setSlug(t.slug); setAgentId(t.elevenlabs_agent_id); setBusinessName(t.business_name); }).catch((e) => setError(e.message));
    api.get("/api/onboarding/media-photos").then(setPhotos).catch((e) => setError(e.message));
    api.get("/api/onboarding/widget-settings").then(setWidget).catch((e) => setError(e.message));
    api.get("/api/onboarding/page-design").then(setDesign).catch((e) => setError(e.message));
  }

  async function saveDesign() {
    if (!design) return;
    setSavingDesign(true);
    setDesignStatus(null);
    try {
      const updated = await api.put("/api/onboarding/page-design", design);
      setDesign(updated);
      setDesignStatus({ type: "ok", text: "Aspetto salvato" });
    } catch (err) {
      setDesignStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSavingDesign(false);
    }
  }

  useEffect(reload, []);

  async function uploadPhoto(file: File) {
    setUploading(true);
    setStatus(null);
    try {
      const created = await uploadFile("/api/onboarding/media-photos", file);
      setPhotos((prev) => [...(prev || []), created]);
      setStatus({ type: "ok", text: "Foto caricata" });
    } catch (err) {
      setStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setUploading(false);
    }
  }

  async function onFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files ? Array.from(e.target.files) : [];
    for (const file of files) await uploadPhoto(file);
    e.target.value = "";
  }

  async function removePhoto(id: string) {
    await api.delete(`/api/onboarding/media-photos/${id}`);
    setPhotos((prev) => (prev || []).filter((p) => p.id !== id));
  }

  async function onAvatarInput(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setWidgetStatus(null);
    try {
      const result = await uploadFile("/api/onboarding/widget-avatar", file);
      setWidget((w) => (w ? { ...w, widget_avatar_url: result.widget_avatar_url } : w));
      setWidgetStatus({ type: "ok", text: "Avatar caricato" });
    } catch (err) {
      setWidgetStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    }
  }

  async function removeAvatar() {
    await api.delete("/api/onboarding/widget-avatar");
    setWidget((w) => (w ? { ...w, widget_avatar_url: null } : w));
  }

  async function saveWidget() {
    if (!widget) return;
    setSavingWidget(true);
    setWidgetStatus(null);
    try {
      const updated = await api.put("/api/onboarding/widget-settings", widget);
      setWidget(updated);
      setWidgetStatus({ type: "ok", text: "Impostazioni salvate" });
    } catch (err) {
      setWidgetStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSavingWidget(false);
    }
  }

  const siteUrl = slug && typeof window !== "undefined" ? `${window.location.origin}/site/${slug}` : null;

  function copyLink() {
    if (!siteUrl) return;
    navigator.clipboard.writeText(siteUrl).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  function copyEmbedCode() {
    if (!agentId || !widget) return;
    navigator.clipboard.writeText(buildEmbedCode(agentId, widget)).then(() => {
      setCodeCopied(true);
      setTimeout(() => setCodeCopied(false), 2000);
    });
  }

  if (!photos || !widget || !design) {
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
      <h1>Viralizza</h1>
      <p className="muted">La vetrina online della tua attività: foto, menu e assistente AI da mettere sui social o mandare ai clienti.</p>

      <div className="card">
        <h2>Pagina pubblica</h2>
        <p className="muted">
          Genera una pagina automaticamente con logo, menu, orari e foto — con dentro anche l&apos;assistente AI, così chi la visita può
          parlarci direttamente dal browser, senza chiamare.
        </p>
        {siteUrl ? (
          <div style={{ display: "flex", alignItems: "center", gap: 10, border: "1px solid var(--border)", borderRadius: 8, padding: "8px 12px", flexWrap: "wrap" }}>
            <span style={{ fontFamily: "monospace", fontSize: "0.9rem", flex: 1, minWidth: 200 }}>{siteUrl}</span>
            <button className="secondary" onClick={copyLink}>{copied ? "Copiato ✓" : "Copia link"}</button>
            <a href={siteUrl} target="_blank" rel="noopener noreferrer"><button>Apri</button></a>
          </div>
        ) : (
          <p className="muted">Caricamento link...</p>
        )}
      </div>

      <div className="card">
        <h2>Aspetto della pagina</h2>
        <p className="muted">Scegli lo stile e personalizza il titolo — la pagina pubblica usa già le tue foto e il tuo menu veri.</p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 12, marginBottom: 20 }}>
          {TEMPLATE_OPTIONS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setDesign({ ...design, public_page_template: t.id })}
              style={{
                textAlign: "left", padding: 0, border: design.public_page_template === t.id ? "2px solid var(--accent)" : "2px solid var(--border)",
                borderRadius: 10, overflow: "hidden", background: "none", cursor: "pointer",
              }}
            >
              <div style={{ background: t.bg, color: t.ink, padding: "16px 12px 14px", fontFamily: t.font }}>
                <div style={{ width: 22, height: 3, background: t.accent, borderRadius: 2, marginBottom: 8 }} />
                <div style={{ fontWeight: 700, fontSize: "0.95rem" }}>Aa</div>
                <div style={{ fontSize: "0.7rem", opacity: 0.7, marginTop: 4 }}>Pizzeria</div>
              </div>
              <div style={{ padding: "8px 10px", background: "var(--card)" }}>
                <div style={{ fontWeight: 600, fontSize: "0.84rem" }}>{t.name}{design.public_page_template === t.id && " ✓"}</div>
                <div className="muted" style={{ fontSize: "0.74rem" }}>{t.desc}</div>
              </div>
            </button>
          ))}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 480 }}>
          <div>
            <label>Titolo principale</label>
            <input
              placeholder={`Benvenuto da ${businessName || "..."}`}
              value={design.public_page_headline || ""}
              onChange={(e) => setDesign({ ...design, public_page_headline: e.target.value })}
              maxLength={200}
            />
          </div>
          <div>
            <label>Sottotitolo</label>
            <input
              placeholder="Pizzeria napoletana · Milazzo"
              value={design.public_page_tagline || ""}
              onChange={(e) => setDesign({ ...design, public_page_tagline: e.target.value })}
              maxLength={200}
            />
          </div>
        </div>
        <div style={{ marginTop: 14, display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={saveDesign} disabled={savingDesign}>{savingDesign ? "Salvataggio..." : "Salva aspetto"}</button>
          <StatusInline status={designStatus} />
        </div>
      </div>

      <div className="card">
        <h2>Foto attività</h2>
        <p className="muted">Foto del locale, dei piatti, dell&apos;ambiente — appaiono nella galleria della pagina pubblica.</p>

        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
          <input type="file" multiple accept=".jpg,.jpeg,.png,.webp" onChange={onFileInput} disabled={uploading} style={{ width: "auto" }} />
          <CameraButton onCapture={uploadPhoto} label="📷 Scatta foto" />
          {uploading && <span className="muted">Caricamento...</span>}
          <StatusInline status={status} />
        </div>

        {photos.length === 0 ? (
          <p className="muted">Nessuna foto ancora — caricane una sopra.</p>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 12 }}>
            {photos.map((p) => (
              <div key={p.id} style={{ position: "relative" }}>
                <img
                  src={`${API_URL}${p.url}`}
                  alt={p.caption || "Foto attività"}
                  style={{ width: "100%", aspectRatio: "1 / 1", objectFit: "cover", borderRadius: 8, border: "1px solid var(--border)" }}
                />
                <button
                  className="secondary"
                  onClick={() => removePhoto(p.id)}
                  style={{ position: "absolute", top: 6, right: 6, padding: "2px 8px", fontSize: "0.75rem" }}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <h2>Widget per il tuo sito</h2>
        <p className="muted">
          Il codice qui sotto apre l&apos;assistente AI su un sito esterno tuo (non solo sulla pagina pubblica sopra) — incollalo dove vuoi,
          es. nel tuo sito WordPress o altrove.
        </p>

        {!agentId ? (
          <p className="muted">L&apos;agente AI non è ancora attivo per questo account: il widget sarà disponibile dopo l&apos;attivazione.</p>
        ) : (
          <>
            <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginTop: 8 }}>
              <div style={{ flex: "1 1 260px" }}>
                <label>Avatar</label>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  {widget.widget_avatar_url ? (
                    <img src={`${API_URL}${widget.widget_avatar_url}`} alt="Avatar widget" style={{ width: 56, height: 56, borderRadius: "50%", objectFit: "cover", border: "1px solid var(--border)" }} />
                  ) : (
                    <div style={{
                      width: 56, height: 56, borderRadius: "50%",
                      background: `linear-gradient(135deg, ${widget.widget_color_1}, ${widget.widget_color_2})`,
                    }} />
                  )}
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <input type="file" accept=".jpg,.jpeg,.png,.webp" onChange={onAvatarInput} style={{ width: "auto", fontSize: "0.8rem" }} />
                    {widget.widget_avatar_url && (
                      <button type="button" className="secondary" style={{ padding: "2px 8px", fontSize: "0.75rem", width: "fit-content" }} onClick={removeAvatar}>
                        Rimuovi, usa colori
                      </button>
                    )}
                  </div>
                </div>
                <p className="muted" style={{ fontSize: "0.78rem", marginTop: 6 }}>Senza avatar personalizzato, il widget mostra una sfera con i due colori qui sotto.</p>

                <div style={{ display: "flex", gap: 16, marginTop: 12 }}>
                  <div>
                    <label>Colore 1</label>
                    <input type="color" value={widget.widget_color_1} onChange={(e) => setWidget({ ...widget, widget_color_1: e.target.value })} style={{ width: 48, padding: 2 }} />
                  </div>
                  <div>
                    <label>Colore 2</label>
                    <input type="color" value={widget.widget_color_2} onChange={(e) => setWidget({ ...widget, widget_color_2: e.target.value })} style={{ width: 48, padding: 2 }} />
                  </div>
                </div>
              </div>

              <div style={{ flex: "1 1 260px" }}>
                <label>Testo del pulsante</label>
                <input value={widget.widget_action_text} onChange={(e) => setWidget({ ...widget, widget_action_text: e.target.value })} maxLength={60} />

                <label style={{ marginTop: 12 }}>Formato</label>
                <select value={widget.widget_variant} onChange={(e) => setWidget({ ...widget, widget_variant: e.target.value })}>
                  <option value="full">Pulsante con testo (consigliato)</option>
                  <option value="expanded">Espanso</option>
                  <option value="tiny">Compatto (solo icona)</option>
                </select>

                <label style={{ marginTop: 12 }}>Posizione sullo schermo</label>
                <select value={widget.widget_placement} onChange={(e) => setWidget({ ...widget, widget_placement: e.target.value })}>
                  <option value="bottom-right">In basso a destra</option>
                  <option value="bottom-left">In basso a sinistra</option>
                </select>

                <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12 }}>
                  <input type="checkbox" style={{ width: "auto" }} checked={widget.widget_dismissible} onChange={(e) => setWidget({ ...widget, widget_dismissible: e.target.checked })} />
                  Il cliente può ridurre/chiudere il widget
                </label>
              </div>
            </div>

            <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 12 }}>
              <button onClick={saveWidget} disabled={savingWidget}>{savingWidget ? "Salvataggio..." : "Salva personalizzazione"}</button>
              <StatusInline status={widgetStatus} />
            </div>

            <div style={{ marginTop: 20 }}>
              <label>Codice da incollare sul tuo sito</label>
              <pre style={{
                background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 8,
                padding: 12, fontSize: "0.8rem", overflowX: "auto", whiteSpace: "pre",
              }}>
                {buildEmbedCode(agentId, widget)}
              </pre>
              <button className="secondary" onClick={copyEmbedCode}>{codeCopied ? "Copiato ✓" : "Copia codice"}</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
