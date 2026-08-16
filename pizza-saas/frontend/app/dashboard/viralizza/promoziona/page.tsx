"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type SocialLinks = { instagram_url: string | null; facebook_url: string | null; tiktok_url: string | null };
type Promotion = {
  id: string; title: string; promo_type: string; buy_qty: number | null; get_qty: number | null;
  discount_percent: number | null; discount_cents: number | null; is_active: boolean;
};
type Status = { type: "ok" | "error"; text: string } | null;

function promoLine(p: Promotion): string {
  if (p.promo_type === "buy_x_get_y" && p.buy_qty && p.get_qty) return `Paghi ${p.buy_qty}, ricevi ${p.get_qty}`;
  if (p.promo_type === "percent_discount" && p.discount_percent) return `${p.discount_percent}% di sconto`;
  if (p.promo_type === "fixed_discount" && p.discount_cents) return `${(p.discount_cents / 100).toFixed(2)} € di sconto`;
  return "";
}

function StatusInline({ status }: { status: Status }) {
  if (!status) return null;
  return (
    <span style={{ marginLeft: 12, fontWeight: 600, fontSize: "0.9rem", color: status.type === "ok" ? "var(--success)" : "var(--accent)" }}>
      {status.type === "ok" ? "✓ " : "⚠ "}{status.text}
    </span>
  );
}

export default function PromozionaPage() {
  const [businessName, setBusinessName] = useState<string | null>(null);
  const [siteUrl, setSiteUrl] = useState<string | null>(null);
  const [social, setSocial] = useState<SocialLinks | null>(null);
  const [promotions, setPromotions] = useState<Promotion[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<Status>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  function reload() {
    setError(null);
    api.get("/api/onboarding/tenant").then((t) => {
      setBusinessName(t.business_name);
      if (typeof window !== "undefined") setSiteUrl(`${window.location.origin}/site/${t.slug}`);
    }).catch((e) => setError(e.message));
    api.get("/api/onboarding/social-links").then(setSocial).catch((e) => setError(e.message));
    api.get("/api/onboarding/promotions").then((rows: Promotion[]) => setPromotions(rows.filter((p) => p.is_active))).catch((e) => setError(e.message));
  }

  useEffect(reload, []);

  async function saveSocial() {
    if (!social) return;
    setSaving(true);
    setStatus(null);
    try {
      const updated = await api.put("/api/onboarding/social-links", social);
      setSocial(updated);
      setStatus({ type: "ok", text: "Link salvati" });
    } catch (err) {
      setStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSaving(false);
    }
  }

  function copyText(id: string, text: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    });
  }

  const inviteText = businessName && siteUrl
    ? `${businessName} è online! Ordina comodamente da qui: ${siteUrl}`
    : null;

  if (!social || !promotions) {
    return (
      <div>
        {error ? (
          <div className="error">
            {error}
            <div style={{ marginTop: 12 }}><button onClick={reload}>Riprova</button></div>
          </div>
        ) : (
          "Caricamento..."
        )}
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 900 }}>
      <h1>Promoziona</h1>
      <p className="muted">I tuoi social e testi pronti da condividere per far conoscere la pizzeria e le promozioni attive.</p>

      <div className="card" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0 }}>Libreria contenuti</h2>
          <p className="muted" style={{ margin: "4px 0 0" }}>Foto e video sorgente per creare i Reel — nuovo.</p>
        </div>
        <Link href="/dashboard/viralizza/promoziona/libreria">
          <button type="button">Apri libreria →</button>
        </Link>
      </div>

      <div className="card" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0 }}>Crea Reel</h2>
          <p className="muted" style={{ margin: "4px 0 0" }}>Trasforma una foto in un video promozionale — nuovo.</p>
        </div>
        <Link href="/dashboard/viralizza/promoziona/crea">
          <button type="button">Crea Reel →</button>
        </Link>
      </div>

      <div className="card">
        <h2>I tuoi social</h2>
        <p className="muted">Colleghiamo questi link alla tua pagina pubblica, così chi ti trova online può seguirti anche lì.</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 480 }}>
          <div>
            <label>Instagram</label>
            <input
              placeholder="https://instagram.com/tuapizzeria"
              value={social.instagram_url || ""}
              onChange={(e) => setSocial({ ...social, instagram_url: e.target.value })}
            />
          </div>
          <div>
            <label>Facebook</label>
            <input
              placeholder="https://facebook.com/tuapizzeria"
              value={social.facebook_url || ""}
              onChange={(e) => setSocial({ ...social, facebook_url: e.target.value })}
            />
          </div>
          <div>
            <label>TikTok</label>
            <input
              placeholder="https://tiktok.com/@tuapizzeria"
              value={social.tiktok_url || ""}
              onChange={(e) => setSocial({ ...social, tiktok_url: e.target.value })}
            />
          </div>
        </div>
        <div style={{ marginTop: 14, display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={saveSocial} disabled={saving}>{saving ? "Salvataggio..." : "Salva"}</button>
          <StatusInline status={status} />
        </div>
      </div>

      {inviteText && (
        <div className="card">
          <h2>Invita i tuoi clienti</h2>
          <p className="muted">Testo pronto da incollare in una storia, un post o una chat.</p>
          <div style={{ display: "flex", alignItems: "center", gap: 10, border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px" }}>
            <span style={{ flex: 1, fontSize: "0.92rem" }}>{inviteText}</span>
            <button className="secondary" onClick={() => copyText("invite", inviteText)}>{copiedId === "invite" ? "Copiato ✓" : "Copia"}</button>
          </div>
        </div>
      )}

      <div className="card">
        <h2>Promozioni attive</h2>
        {promotions.length === 0 ? (
          <p className="muted">Nessuna promozione attiva al momento — creane una nella pagina Promozioni per avere qui un testo pronto da condividere.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {promotions.map((p) => {
              const line = promoLine(p);
              const text = `${businessName || "La nostra pizzeria"}: ${p.title}${line ? ` — ${line}` : ""}!${siteUrl ? ` Ordina qui: ${siteUrl}` : ""}`;
              return (
                <div key={p.id} style={{ border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px" }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>{p.title}{line && <span className="muted" style={{ fontWeight: 400 }}> — {line}</span>}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ flex: 1, fontSize: "0.88rem" }} className="muted">{text}</span>
                    <button className="secondary" onClick={() => copyText(p.id, text)}>{copiedId === p.id ? "Copiato ✓" : "Copia"}</button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
