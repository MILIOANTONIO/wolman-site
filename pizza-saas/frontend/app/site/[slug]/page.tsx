"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Script from "next/script";
import { Playfair_Display, Inter } from "next/font/google";
import { api, API_URL } from "@/lib/api";
import "./public.css";

const playfair = Playfair_Display({ subsets: ["latin"], weight: ["700", "900"], variable: "--font-playfair" });
const inter = Inter({ subsets: ["latin"], weight: ["400", "600", "800"], variable: "--font-inter" });

type Offering = { name: string; description: string | null; price_cents: number; unit: string | null; group_name: string | null; ingredients: string | null };
type Photo = { url: string; caption: string | null };
type PublicTenant = {
  business_name: string; category: string; address: string | null; city: string | null; province: string | null;
  logo_url: string | null; phone_number: string | null; elevenlabs_agent_id: string | null;
  business_hours: Record<string, string[]>; delivery_enabled: boolean; pickup_enabled: boolean; table_reservations_enabled: boolean;
  offerings: Offering[]; photos: Photo[];
  widget_avatar_url: string | null; widget_color_1: string; widget_color_2: string;
  widget_action_text: string; widget_variant: string; widget_placement: string; widget_dismissible: boolean;
  public_page_template: string; public_page_headline: string | null; public_page_tagline: string | null;
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

  if (notFound) return <div className="pub-container" style={{ padding: 60, textAlign: "center" }}>Pagina non trovata.</div>;
  if (!data) return <div className="pub-container" style={{ padding: 60, textAlign: "center" }}>Caricamento...</div>;

  const groups = Array.from(new Set(data.offerings.map((o) => o.group_name || "Menu")));
  const whatsappHref = data.phone_number ? `https://wa.me/${data.phone_number.replace(/[^\d]/g, "")}` : null;
  const telHref = data.phone_number ? `tel:${data.phone_number}` : null;
  const orderLabel = data.delivery_enabled || data.pickup_enabled ? "Ordina ora" : "Prenota ora";
  const heroPhoto = data.photos[0] || null;
  const galleryPhotos = data.photos.slice(1);
  const headline = data.public_page_headline || `Benvenuto da ${data.business_name}`;
  const tagline = data.public_page_tagline || [data.category, data.city].filter(Boolean).join(" · ");
  const template = data.public_page_template || "moderna";

  const nav = (
    <>
      <input type="checkbox" id="pub-menu" className="pub-menu-toggle" />
      <div className="pub-nav">
        <div className="pub-brand">{data.business_name}</div>
        <label htmlFor="pub-menu" className="pub-hamburger">☰</label>
      </div>
      <label htmlFor="pub-menu" className="pub-drawer-overlay"></label>
      <nav className="pub-drawer">
        <label htmlFor="pub-menu" className="pub-drawer-close">✕</label>
        <a href="#menu">Menu</a>
        {Object.keys(data.business_hours).length > 0 && <a href="#orari">Orari</a>}
        {data.photos.length > 0 && <a href="#foto">Foto</a>}
        {telHref && <a href={telHref} className="pub-drawer-cta">📞 {orderLabel}</a>}
      </nav>
    </>
  );

  const menuSection = data.offerings.length > 0 && (
    <section className="pub-section" id="menu">
      {template === "moderna" ? (
        <>
          <h2 className="pub-h2">Menu</h2>
          <div className="pub-menu-grid">
            {data.offerings.map((o) => (
              <div key={o.name} className="pub-item">
                <span className="pub-item-n">{o.name}</span>
                {o.description && <div className="pub-item-d">{o.description}</div>}
                <span className="pub-item-p">{(o.price_cents / 100).toFixed(2)} €</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        groups.map((g) => (
          <div key={g} style={{ marginBottom: 26 }}>
            <h2 className="pub-h2">{g}</h2>
            {data.offerings.filter((o) => (o.group_name || "Menu") === g).map((o) => (
              <div key={o.name} className="pub-item">
                <div>
                  <div className="pub-item-n">{o.name}</div>
                  {o.description && <div className="pub-item-d">{o.description}</div>}
                  {o.ingredients && <div className="pub-item-d">{o.ingredients}</div>}
                </div>
                <div className="pub-item-p">{(o.price_cents / 100).toFixed(2)} €</div>
              </div>
            ))}
          </div>
        ))
      )}
    </section>
  );

  const gallerySection = galleryPhotos.length > 0 && (
    <section className="pub-section" id="foto">
      <h2 className="pub-h2">Foto</h2>
      <div className="pub-gal">
        {galleryPhotos.map((p, i) => (
          <div key={i} className="pub-gal-img"><img src={`${API_URL}${p.url}`} alt={p.caption || data.business_name} /></div>
        ))}
      </div>
    </section>
  );

  const hoursSection = Object.keys(data.business_hours).length > 0 && (
    <section className="pub-section" id="orari">
      <h2 className="pub-h2">Orari</h2>
      {DAY_ORDER.filter((d) => data.business_hours[d]).map((d) => (
        <div key={d} className="pub-hours-row">
          <span>{DAY_LABELS[d]}</span>
          <span className="pub-muted-txt">{data.business_hours[d].length ? data.business_hours[d].join(", ") : "Chiuso"}</span>
        </div>
      ))}
    </section>
  );

  const widgetSection = data.elevenlabs_agent_id && (
    <section className="pub-section">
      <h2 className="pub-h2">Parla con noi</h2>
      <p className="pub-muted-txt">Fai una domanda o ordina direttamente da qui, senza chiamare.</p>
      <div className="pub-widget-box">
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
  );

  const footer = (
    <footer className="pub-foot">
      <div className="pub-soc-row">📷 📘 💬</div>
      <span className="pub-muted-txt">
        {data.business_name}{data.address ? ` — ${data.address}` : ""}{data.city ? `, ${data.city}${data.province ? ` (${data.province})` : ""}` : ""}
      </span>
    </footer>
  );

  const rootClass = `pub-root t-${template} ${playfair.variable} ${inter.variable}`;

  return (
    <div className={rootClass}>
      <Script src="https://unpkg.com/@elevenlabs/convai-widget-embed" strategy="afterInteractive" />
      {nav}

      {template === "moderna" ? (
        <div className="pub-hero">
          <div className="pub-hero-photo">
            {heroPhoto ? <img src={`${API_URL}${heroPhoto.url}`} alt={data.business_name} /> : <div className="pub-hero-fallback" />}
          </div>
          <h1 className="pub-h1 pub-reveal pub-r1">{headline}</h1>
          {tagline && <p className="pub-tagline pub-reveal pub-r2">{tagline}</p>}
          {telHref && <a href={telHref} className="pub-cta pub-reveal pub-r3">{orderLabel} →</a>}
        </div>
      ) : (
        <div className="pub-hero">
          {heroPhoto ? <img src={`${API_URL}${heroPhoto.url}`} alt={data.business_name} /> : <div className="pub-hero-fallback" />}
          {template === "vivace" && <span className="pub-badge">🍕</span>}
          <div className="pub-hero-txt">
            {template === "notte" && <div className="pub-rule"></div>}
            {template === "rustico" && data.city && <div className="pub-kicker">{data.city}</div>}
            <h1 className="pub-h1">{headline}</h1>
            {tagline && <p className="pub-tagline">{tagline}</p>}
            {telHref && <a href={telHref} className="pub-cta">{template === "rustico" ? `📞 ${orderLabel}` : orderLabel}</a>}
          </div>
        </div>
      )}

      {template === "moderna" ? (
        whatsappHref && (
          <div className="pub-ticker-wrap">
            <div className="pub-ticker">
              <span>{orderLabel} — {data.business_name}</span>
              <span>💬 WhatsApp disponibile</span>
              <span>{orderLabel} — {data.business_name}</span>
              <span>💬 WhatsApp disponibile</span>
            </div>
          </div>
        )
      ) : (
        whatsappHref && <div className="pub-promo">💬 Scrivici su WhatsApp</div>
      )}

      {menuSection}
      {gallerySection}
      {hoursSection}
      {widgetSection}
      {footer}
    </div>
  );
}
