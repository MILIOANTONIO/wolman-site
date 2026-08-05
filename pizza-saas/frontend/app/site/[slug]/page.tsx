"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Script from "next/script";
import { api, API_URL } from "@/lib/api";

type Offering = { name: string; description: string | null; price_cents: number; unit: string | null; group_name: string | null; ingredients: string | null };
type Photo = { url: string; caption: string | null };
type PublicTenant = {
  business_name: string; category: string; address: string | null; city: string | null; province: string | null;
  logo_url: string | null; phone_number: string | null; elevenlabs_agent_id: string | null;
  business_hours: Record<string, string[]>; delivery_enabled: boolean; table_reservations_enabled: boolean;
  offerings: Offering[]; photos: Photo[];
  widget_avatar_url: string | null; widget_color_1: string; widget_color_2: string;
  widget_action_text: string; widget_variant: string; widget_placement: string; widget_dismissible: boolean;
};

const DAY_LABELS: Record<string, string> = {
  lun: "Lunedì", mar: "Martedì", mer: "Mercoledì", gio: "Giovedì", ven: "Venerdì", sab: "Sabato", dom: "Domenica",
};
const DAY_ORDER = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"];

export default function PublicSitePage() {
  const params = useParams<{ slug: string }>();
  const [data, setData] = useState<PublicTenant | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    api.get(`/api/public/${params.slug}`).then(setData).catch(() => setNotFound(true));
  }, [params.slug]);

  if (notFound) {
    return (
      <div style={S.page}>
        <div style={S.center}>
          <p>Pagina non trovata.</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div style={S.page}>
        <div style={S.center}>
          <p>Caricamento...</p>
        </div>
      </div>
    );
  }

  const groups = Array.from(new Set(data.offerings.map((o) => o.group_name || "Menu")));
  const whatsappHref = data.phone_number ? `https://wa.me/${data.phone_number.replace(/[^\d]/g, "")}` : null;
  const telHref = data.phone_number ? `tel:${data.phone_number}` : null;

  return (
    <div style={S.page}>
      <Script src="https://unpkg.com/@elevenlabs/convai-widget-embed" strategy="afterInteractive" />

      <header style={S.hero}>
        {data.logo_url && <img src={`${API_URL}${data.logo_url}`} alt={data.business_name} style={S.logo} />}
        <h1 style={S.h1}>{data.business_name}</h1>
        <p style={S.subtitle}>
          {data.category}
          {data.city ? ` · ${data.city}${data.province ? ` (${data.province})` : ""}` : ""}
        </p>
        {data.address && <p style={S.muted}>{data.address}</p>}
        <div style={S.ctaRow}>
          {telHref && <a href={telHref} style={{ ...S.btn, ...S.btnPrimary }}>📞 Chiama ora</a>}
          {whatsappHref && <a href={whatsappHref} target="_blank" rel="noopener noreferrer" style={{ ...S.btn, ...S.btnSecondary }}>💬 WhatsApp</a>}
        </div>
      </header>

      {data.elevenlabs_agent_id && (
        <section style={S.section}>
          <h2 style={S.h2}>Parla con il nostro assistente</h2>
          <p style={S.muted}>Fai una domanda o prenota direttamente da qui, senza chiamare.</p>
          <div style={S.widgetBox}>
            <elevenlabs-convai
              agent-id={data.elevenlabs_agent_id}
              avatar-image-url={data.widget_avatar_url ? `${API_URL}${data.widget_avatar_url}` : undefined}
              avatar-orb-color-1={data.widget_avatar_url ? undefined : data.widget_color_1}
              avatar-orb-color-2={data.widget_avatar_url ? undefined : data.widget_color_2}
              action-text={data.widget_action_text}
              variant={data.widget_variant}
              placement={data.widget_placement}
              dismissible={data.widget_dismissible ? "true" : "false"}
            ></elevenlabs-convai>
          </div>
        </section>
      )}

      {data.photos.length > 0 && (
        <section style={S.section}>
          <h2 style={S.h2}>Foto</h2>
          <div style={S.gallery}>
            {data.photos.map((p, i) => (
              <img key={i} src={`${API_URL}${p.url}`} alt={p.caption || data.business_name} style={S.galleryImg} />
            ))}
          </div>
        </section>
      )}

      {data.offerings.length > 0 && (
        <section style={S.section}>
          <h2 style={S.h2}>Menu</h2>
          {groups.map((g) => (
            <div key={g} style={{ marginBottom: 20 }}>
              <h3 style={S.h3}>{g}</h3>
              {data.offerings.filter((o) => (o.group_name || "Menu") === g).map((o) => (
                <div key={o.name} style={S.menuRow}>
                  <div>
                    <div style={S.menuName}>{o.name}</div>
                    {o.description && <div style={S.muted}>{o.description}</div>}
                    {o.ingredients && <div style={S.ingredients}>{o.ingredients}</div>}
                  </div>
                  <div style={S.price}>{(o.price_cents / 100).toFixed(2)} €</div>
                </div>
              ))}
            </div>
          ))}
        </section>
      )}

      {Object.keys(data.business_hours).length > 0 && (
        <section style={S.section}>
          <h2 style={S.h2}>Orari</h2>
          {DAY_ORDER.filter((d) => data.business_hours[d]).map((d) => (
            <div key={d} style={S.hoursRow}>
              <span>{DAY_LABELS[d]}</span>
              <span style={S.muted}>{data.business_hours[d].length ? data.business_hours[d].join(", ") : "Chiuso"}</span>
            </div>
          ))}
        </section>
      )}

      <footer style={S.footer}>
        <span style={S.muted}>{data.business_name}</span>
      </footer>
    </div>
  );
}

const S: Record<string, React.CSSProperties> = {
  page: { maxWidth: 640, margin: "0 auto", padding: "0 20px 60px", fontFamily: "-apple-system, 'Segoe UI', Arial, sans-serif", color: "#1a1a1a", background: "#fff" },
  center: { minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center" },
  hero: { textAlign: "center", padding: "48px 0 32px", borderBottom: "1px solid #eee" },
  logo: { width: 88, height: 88, borderRadius: 16, objectFit: "cover", marginBottom: 16 },
  h1: { fontSize: "1.8rem", margin: "0 0 6px" },
  h2: { fontSize: "1.25rem", margin: "0 0 4px" },
  h3: { fontSize: "1rem", margin: "0 0 10px", color: "#e5533f" },
  subtitle: { textTransform: "capitalize", color: "#666", margin: "0 0 4px" },
  muted: { color: "#777", fontSize: "0.9rem" },
  ctaRow: { display: "flex", gap: 10, justifyContent: "center", marginTop: 20, flexWrap: "wrap" },
  btn: { padding: "10px 20px", borderRadius: 24, textDecoration: "none", fontWeight: 600, fontSize: "0.95rem" },
  btnPrimary: { background: "#e5533f", color: "#fff" },
  btnSecondary: { background: "#25d366", color: "#fff" },
  section: { padding: "32px 0", borderBottom: "1px solid #eee" },
  widgetBox: { marginTop: 16, minHeight: 60 },
  gallery: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 10, marginTop: 16 },
  galleryImg: { width: "100%", aspectRatio: "1 / 1", objectFit: "cover", borderRadius: 10 },
  menuRow: { display: "flex", justifyContent: "space-between", gap: 16, padding: "8px 0" },
  menuName: { fontWeight: 600 },
  ingredients: { color: "#999", fontSize: "0.82rem", marginTop: 2 },
  price: { fontWeight: 600, whiteSpace: "nowrap" },
  hoursRow: { display: "flex", justifyContent: "space-between", padding: "4px 0" },
  footer: { textAlign: "center", padding: "24px 0" },
};
