"use client";
import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Script from "next/script";
import { Playfair_Display, Inter, Caveat, Oswald } from "next/font/google";
import { api, API_URL } from "@/lib/api";
import "./public.css";

const playfair = Playfair_Display({ subsets: ["latin"], weight: ["700", "900"], variable: "--font-playfair" });
const inter = Inter({ subsets: ["latin"], weight: ["400", "600", "800"], variable: "--font-inter" });
const caveat = Caveat({ subsets: ["latin"], weight: ["600", "700"], variable: "--font-caveat" });
const oswald = Oswald({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-oswald" });

type Offering = { name: string; description: string | null; price_cents: number; unit: string | null; group_name: string | null; ingredients: string | null; image_url: string | null; is_featured: boolean };
type Photo = { url: string; caption: string | null };
type PromotionInfo = {
  title: string; description: string; promo_type: string;
  discount_percent: number | null; discount_cents: number | null; buy_qty: number | null; get_qty: number | null;
  photo_urls: string[];
  offerings: Offering[];
};
type PublicTenant = {
  business_name: string; category: string; address: string | null; city: string | null; province: string | null;
  logo_url: string | null; phone_number: string | null; elevenlabs_agent_id: string | null;
  business_hours: Record<string, string[]>; delivery_enabled: boolean; pickup_enabled: boolean; table_reservations_enabled: boolean;
  offerings: Offering[]; photos: Photo[]; promotions: PromotionInfo[];
  widget_avatar_url: string | null; widget_color_1: string; widget_color_2: string;
  widget_action_text: string; widget_variant: string; widget_placement: string; widget_dismissible: boolean;
  public_page_template: string; public_page_headline: string | null; public_page_tagline: string | null;
};

const DAY_ORDER = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"];

/* Multilingua: le stringhe fisse del template sono tradotte on-demand via DeepL (endpoint /api/public/translate,
   con cache lato server) quando il visitatore cambia lingua. I nomi dei piatti e i testi del tenant vengono
   raccolti a runtime e tradotti nello stesso modo — la lingua "it" non chiama mai l'API, mostra il testo originale. */
type Lang = "it" | "en" | "fr" | "de" | "es";
/* Bandiere disegnate in SVG invece che emoji: su Windows/Chrome le emoji bandiera spesso non
   si vedono (nessun glifo nel font di sistema) e restano cerchi vuoti. */
const FlagIT = () => (<svg viewBox="0 0 30 20" width="100%" height="100%"><rect width="30" height="20" fill="#fff" /><rect width="10" height="20" fill="#009246" /><rect x="20" width="10" height="20" fill="#CE2B37" /></svg>);
const FlagGB = () => (
  <svg viewBox="0 0 30 20" width="100%" height="100%">
    <rect width="30" height="20" fill="#00247D" />
    <path d="M0 0 L30 20 M30 0 L0 20" stroke="#fff" strokeWidth="4" />
    <path d="M0 0 L30 20 M30 0 L0 20" stroke="#CF142B" strokeWidth="1.6" />
    <path d="M15 0 V20 M0 10 H30" stroke="#fff" strokeWidth="6" />
    <path d="M15 0 V20 M0 10 H30" stroke="#CF142B" strokeWidth="3.2" />
  </svg>
);
const FlagFR = () => (<svg viewBox="0 0 30 20" width="100%" height="100%"><rect width="30" height="20" fill="#fff" /><rect width="10" height="20" fill="#0055A4" /><rect x="20" width="10" height="20" fill="#EF4135" /></svg>);
const FlagDE = () => (<svg viewBox="0 0 30 20" width="100%" height="100%"><rect width="30" height="20" fill="#FFCE00" /><rect width="30" height="6.67" fill="#000" /><rect y="6.67" width="30" height="6.67" fill="#DD0000" /></svg>);
const FlagES = () => (<svg viewBox="0 0 30 20" width="100%" height="100%"><rect width="30" height="20" fill="#AA151B" /><rect y="5" width="30" height="10" fill="#F1BF00" /></svg>);

const LANGS: { code: Lang; Flag: () => JSX.Element; label: string }[] = [
  { code: "it", Flag: FlagIT, label: "IT" },
  { code: "en", Flag: FlagGB, label: "EN" },
  { code: "fr", Flag: FlagFR, label: "FR" },
  { code: "de", Flag: FlagDE, label: "DE" },
  { code: "es", Flag: FlagES, label: "ES" },
];

const UI_IT = {
  menu: "Menu", hours: "Orari", photos: "Foto", talk: "Parla con noi",
  order_now: "Ordina ora", book_now: "Prenota ora",
  specialties: "Le nostre specialità", follow_social: "Seguici sui social", opening_hours: "Quando siamo aperti",
  h_fresh_t: "Ingredienti selezionati", h_fresh_d: "Materie prime scelte, lavorate ogni giorno.",
  h_now_t: "Fatto al momento", h_now_d: "Ogni ordine preparato quando arriva, non prima.",
  h_delivery_t: "Consegna rapida", h_delivery_d: "Direttamente a casa tua, caldo e in tempo.",
  h_pickup_t: "Pronto per il ritiro", h_pickup_d: "Ordina e passa a ritirare quando vuoi.",
  h_love_t: "Fatta con passione", h_love_d: "Ogni piatto preparato con cura, non in serie.",
  story_eyebrow: "La nostra storia", story_title: "Passione che si sente\nal primo morso",
  story_born: "nasce dalla passione per la buona cucina", story_heart: "nel cuore di",
  story_close: "Ogni giorno lavoriamo con ingredienti selezionati per offrirti un'esperienza di gusto che si ricorda.",
  story_cta: "Scopri di più",
  cta_hungry: "Hai fame?", cta_ready: "è pronta a prepararti qualcosa di buono.", cta_whatsapp: "WhatsApp",
  footer_links: "Link utili", footer_location: "Dove siamo",
  widget_prompt: "Fai una domanda o ordina direttamente da qui, senza chiamare.",
  not_found: "Pagina non trovata.", loading: "Caricamento...", closed: "Chiuso",
  stat_dishes: "piatti nel menu", stat_delivery: "Consegna a domicilio", stat_pickup: "Asporto disponibile",
  gallery_open: "Apri foto", gallery_close: "Chiudi", gallery_prev: "Foto precedente", gallery_next: "Foto successiva",
  day_lun: "Lunedì", day_mar: "Martedì", day_mer: "Mercoledì", day_gio: "Giovedì", day_ven: "Venerdì", day_sab: "Sabato", day_dom: "Domenica",
  welcome_from: "Benvenuto da",
  ticker_whatsapp: "WhatsApp disponibile", promo_whatsapp: "Scrivici su WhatsApp",
  promo_eyebrow: "Offerta speciale", promotions_title: "Promozioni", promo_off: "Sconto",
  directions: "Portami qui", book_table: "Prenota un tavolo",
  featured_eyebrow: "Il nostro menu", featured_title: "Scelti per te", filter_all: "Tutti",
};
type UIKey = keyof typeof UI_IT;

function useUiTranslation(lang: Lang) {
  const [cache, setCache] = useState<Partial<Record<Lang, Record<string, string>>>>({});
  useEffect(() => {
    if (lang === "it" || cache[lang]) return;
    const keys = Object.keys(UI_IT) as UIKey[];
    const texts = keys.map((k) => UI_IT[k]);
    api
      .post("/api/public/translate", { texts, target_lang: lang })
      .then((res: { translations: string[] }) => {
        const dict: Record<string, string> = {};
        keys.forEach((k, i) => { dict[UI_IT[k]] = res.translations[i] || UI_IT[k]; });
        setCache((c) => ({ ...c, [lang]: dict }));
      })
      .catch(() => {});
  }, [lang, cache]);
  return (key: UIKey) => cache[lang]?.[UI_IT[key]] || UI_IT[key];
}

/* Traduce un elenco di testi dinamici del tenant (piatti, headline...) in blocchi da 100 per non superare il limite lato server. */
function useContentTranslation_UNUSED(lang: Lang, texts: string[]) {
  const [dict, setDict] = useState<Record<string, string>>({});
  const key = texts.join("");
  useEffect(() => {
    if (lang === "it" || !texts.length) { setDict({}); return; }
    let cancelled = false;
    const unique = Array.from(new Set(texts.filter((t) => t && t.trim())));
    const chunks: string[][] = [];
    for (let i = 0; i < unique.length; i += 80) chunks.push(unique.slice(i, i + 80));
    Promise.all(
      chunks.map((chunk) =>
        api
          .post("/api/public/translate", { texts: chunk, target_lang: lang })
          .then((res: { translations: string[] }) => ({ chunk, translations: res.translations }))
      )
    )
      .then((results) => {
        if (cancelled) return;
        const merged: Record<string, string> = {};
        results.forEach(({ chunk, translations }) => chunk.forEach((t, i) => { merged[t] = translations[i] || t; }));
        setDict(merged);
      })
      .catch(() => {});
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang, key]);
  return (text: string | null | undefined) => (text && dict[text]) || text || "";
}

function LangSwitcher({ lang, onChange }: { lang: Lang; onChange: (l: Lang) => void }) {
  return (
    <div className="pub-lang-switch">
      {LANGS.map((l) => (
        <button
          type="button"
          key={l.code}
          className={l.code === lang ? "pub-lang-btn pub-lang-active" : "pub-lang-btn"}
          onClick={() => onChange(l.code)}
          aria-label={l.label}
          title={l.label}
        >
          <span className="pub-lang-flag"><l.Flag /></span>
        </button>
      ))}
    </div>
  );
}

/* Icone decorative disegnate a mano (non foto): motivi da pizzeria per dare vita all'hero senza dipendere dalle foto caricate dal tenant. */
const DecorSlice = () => (
  <svg viewBox="0 0 48 48" width="100%" height="100%"><path d="M24 4 L44 40 A24 24 0 0 1 4 40 Z" fill="currentColor" opacity="0.9" />
    <circle cx="22" cy="24" r="2.6" fill="#fff" opacity="0.85" /><circle cx="30" cy="30" r="2.2" fill="#fff" opacity="0.85" /><circle cx="18" cy="33" r="2" fill="#fff" opacity="0.85" />
    <path d="M6 39 A22 22 0 0 1 42 39" fill="none" stroke="#fff" strokeWidth="2" opacity="0.55" /></svg>
);
const DecorLeaf = () => (
  <svg viewBox="0 0 32 32" width="100%" height="100%"><path d="M4 28 C4 12 14 4 28 4 C28 18 20 28 4 28 Z" fill="currentColor" opacity="0.85" />
    <path d="M6 26 C12 18 18 12 27 5" fill="none" stroke="#fff" strokeWidth="1.4" opacity="0.5" /></svg>
);
const DecorChili = () => (
  <svg viewBox="0 0 40 24" width="100%" height="100%"><path d="M2 6 C10 2 16 4 16 4 C24 4 34 8 38 14 C34 20 22 20 16 16 C10 20 2 18 2 14 C2 11 2 8 2 6 Z" fill="currentColor" opacity="0.88" />
    <path d="M4 6 C6 4 9 3 12 3" fill="none" stroke="#3F7D4A" strokeWidth="2" strokeLinecap="round" /></svg>
);
const DecorSteam = () => (
  <svg viewBox="0 0 24 40" width="100%" height="100%" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" opacity="0.5">
    <path d="M8 38 C2 30 14 26 8 18 C2 10 14 6 10 2" /><path d="M18 38 C12 30 22 27 17 19 C12 11 22 7 18 2" /></svg>
);
const DecorSpark = () => (
  <svg viewBox="0 0 24 24" width="100%" height="100%"><path d="M12 0 L14.5 9.5 L24 12 L14.5 14.5 L12 24 L9.5 14.5 L0 12 L9.5 9.5 Z" fill="currentColor" opacity="0.8" /></svg>
);

/* Rivela un elemento con un'animazione quando entra nello schermo scorrendo, invece che tutto insieme al caricamento. */
function Reveal({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { setInView(true); obs.disconnect(); }
    }, { threshold: 0.2 });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return <div ref={ref} className={`${className}${inView ? " pub-inview" : ""}`}>{children}</div>;
}

/* Titolo animato parola per parola invece di un unico blocco fermo: ogni parola entra con un piccolo ritardo in cascata. */
function AnimatedHeadline({ text, className = "", baseDelay = 0 }: { text: string; className?: string; baseDelay?: number }) {
  const words = text.split(" ");
  return (
    <h1 className={`pub-h1 ${className}`}>
      {words.map((w, i) => (
        <span className="pub-word" style={{ animationDelay: `${baseDelay + i * 0.09}s` }} key={i}>{w}&nbsp;</span>
      ))}
    </h1>
  );
}

function SectionTitle({ eyebrow, children }: { eyebrow?: string; children: React.ReactNode }) {
  return (
    <Reveal className="pub-section-title">
      <span className="pub-section-title-icon"><DecorSlice /></span>
      {eyebrow && <span className="pub-section-eyebrow">{eyebrow}</span>}
      <h2 className="pub-h2">{children}</h2>
    </Reveal>
  );
}

type DecorSpec = { Icon: () => JSX.Element; size: number; top?: string; bottom?: string; left?: string; right?: string; duration: number; delay: number; rotate: number; color: string };

function HeroDecor({ items }: { items: DecorSpec[] }) {
  return (
    <div className="pub-decor" aria-hidden="true">
      {items.map((d, i) => (
        <span
          key={i}
          className="pub-decor-item"
          style={{
            width: d.size, height: d.size, top: d.top, bottom: d.bottom, left: d.left, right: d.right,
            color: d.color, animationDuration: `${d.duration}s`, animationDelay: `${d.delay}s`,
            ["--rot" as string]: `${d.rotate}deg`,
          }}
        >
          <d.Icon />
        </span>
      ))}
    </div>
  );
}

export default function PublicSitePage() {
  const params = useParams<{ slug: string }>();
  const [data, setData] = useState<PublicTenant | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const [lang, setLang] = useState<Lang>("it");
  const [featuredFilter, setFeaturedFilter] = useState<string | null>(null);

  useEffect(() => {
    // Il contenuto del tenant (piatti, headline, tagline, categoria) arriva gia' tradotto dal
    // backend per la lingua richiesta - vedi offering_translations/tenant_translations, generate
    // in scrittura quando il tenant salva - non c'e' nessuna chiamata di traduzione dal browser.
    api.get(`/api/public/${params.slug}?lang=${lang}`).then(setData).catch(() => setNotFound(true));
  }, [params.slug, lang]);

  useEffect(() => {
    if (lightboxIndex === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLightboxIndex(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [lightboxIndex]);

  const t = useUiTranslation(lang);

  if (notFound) return <div className="pub-container" style={{ padding: 60, textAlign: "center" }}>{t("not_found")}</div>;
  if (!data) return <div className="pub-container" style={{ padding: 60, textAlign: "center" }}>{t("loading")}</div>;

  const groups = Array.from(new Set(data.offerings.map((o) => o.group_name || "Menu")));
  const whatsappHref = data.phone_number ? `https://wa.me/${data.phone_number.replace(/[^\d]/g, "")}` : null;
  const telHref = data.phone_number ? `tel:${data.phone_number}` : null;
  const orderLabel = data.delivery_enabled || data.pickup_enabled ? t("order_now") : t("book_now");
  // Google Maps "portami qui": stessa logica del sito di Montalbano — indirizzo completo come query di ricerca.
  const directionsHref = data.address
    ? `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent([data.address, data.city, data.province].filter(Boolean).join(", "))}`
    : null;
  // Se prenota anche tavoli oltre a consegna/asporto, mostra un pulsante dedicato invece di
  // confonderlo con l'azione principale (che altrimenti diventa gia' "Prenota ora" da sola).
  const showBookTable = data.table_reservations_enabled && (data.delivery_enabled || data.pickup_enabled) && !!telHref;
  const heroPhoto = data.photos[0] || null;
  const storyPhoto = data.photos[1] || heroPhoto;
  const galleryPhotos = data.photos.slice(1).filter((p) => p !== storyPhoto);
  const headline = data.public_page_headline || `${t("welcome_from")} ${data.business_name}`;
  const tagline = data.public_page_tagline || [data.category, data.city].filter(Boolean).join(" · ");
  const template = data.public_page_template || "moderna";

  const modernaDecor: DecorSpec[] = [
    { Icon: DecorSlice, size: 46, top: "2%", left: "-6%", duration: 7, delay: 0, rotate: -12, color: "#C4351E" },
    { Icon: DecorLeaf, size: 30, bottom: "14%", right: "-4%", duration: 6, delay: 0.6, rotate: 20, color: "#3F7D4A" },
    { Icon: DecorChili, size: 34, top: "8%", right: "2%", duration: 8, delay: 1.2, rotate: -8, color: "#E7C08C" },
    { Icon: DecorSpark, size: 18, top: "40%", left: "-3%", duration: 5, delay: 0.3, rotate: 0, color: "#C4351E" },
    { Icon: DecorSteam, size: 26, bottom: "4%", left: "6%", duration: 6.5, delay: 0.9, rotate: 0, color: "#C4351E" },
  ];
  const statChips = [
    data.offerings.length > 0 ? { icon: "🍕", label: `${data.offerings.length} ${t("stat_dishes")}` } : null,
    data.delivery_enabled ? { icon: "🛵", label: t("stat_delivery") } : null,
    data.pickup_enabled ? { icon: "🥡", label: t("stat_pickup") } : null,
    data.city ? { icon: "📍", label: data.city } : null,
  ].filter(Boolean) as { icon: string; label: string }[];

  const nav = (
    <>
      <input type="checkbox" id="pub-menu" className="pub-menu-toggle" />
      <div className="pub-nav">
        <div className="pub-brand">
          {data.logo_url ? (
            <img className="pub-logo" src={`${API_URL}${data.logo_url}`} alt={data.business_name} />
          ) : (
            data.business_name
          )}
        </div>
        <div className="pub-nav-right">
          <LangSwitcher lang={lang} onChange={setLang} />
          <label htmlFor="pub-menu" className="pub-hamburger">☰</label>
        </div>
      </div>
      <label htmlFor="pub-menu" className="pub-drawer-overlay"></label>
      <nav className="pub-drawer">
        <label htmlFor="pub-menu" className="pub-drawer-close">✕</label>
        <a href="#menu">{t("menu")}</a>
        {Object.keys(data.business_hours).length > 0 && <a href="#orari">{t("hours")}</a>}
        {data.photos.length > 0 && <a href="#foto">{t("photos")}</a>}
        {telHref && <a href={telHref} className="pub-drawer-cta">📞 {orderLabel}</a>}
      </nav>
    </>
  );

  const menuSection = data.offerings.length > 0 && (
    <section className="pub-section" id="menu">
      {template === "moderna" ? (
        <>
          <SectionTitle eyebrow={t("specialties")}>{t("menu")}</SectionTitle>
          <div className="pub-menu-grid">
            {data.offerings.map((o) => (
              <div key={o.name} className={o.image_url ? "pub-item pub-item-photo" : "pub-item"}>
                {o.image_url && <div className="pub-item-img"><img src={`${API_URL}${o.image_url}`} alt={o.name} /></div>}
                <div className="pub-item-body">
                  <span className="pub-item-n">{o.name}</span>
                  {o.description && <div className="pub-item-d">{o.description}</div>}
                  {o.ingredients && <div className="pub-item-d">{o.ingredients}</div>}
                  <span className="pub-item-p">{(o.price_cents / 100).toFixed(2)} €</span>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        groups.map((g) => (
          <div key={g} style={{ marginBottom: 26 }}>
            <SectionTitle>{g}</SectionTitle>
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
      <SectionTitle eyebrow={t("follow_social")}>{t("photos")}</SectionTitle>
      <div className="pub-gal">
        {galleryPhotos.map((p, i) => (
          <button type="button" key={i} className="pub-gal-img" onClick={() => setLightboxIndex(i)} aria-label={`${t("gallery_open")} ${i + 1}`}>
            <img src={`${API_URL}${p.url}`} alt={p.caption || data.business_name} />
          </button>
        ))}
      </div>
    </section>
  );

  const lightbox = lightboxIndex !== null && galleryPhotos[lightboxIndex] && (
    <div className="pub-lightbox" onClick={() => setLightboxIndex(null)}>
      <button type="button" className="pub-lightbox-close" onClick={() => setLightboxIndex(null)} aria-label={t("gallery_close")}>✕</button>
      {galleryPhotos.length > 1 && (
        <button
          type="button"
          className="pub-lightbox-nav pub-lightbox-prev"
          aria-label={t("gallery_prev")}
          onClick={(e) => { e.stopPropagation(); setLightboxIndex((lightboxIndex - 1 + galleryPhotos.length) % galleryPhotos.length); }}
        >‹</button>
      )}
      <img
        src={`${API_URL}${galleryPhotos[lightboxIndex].url}`}
        alt={galleryPhotos[lightboxIndex].caption || data.business_name}
        onClick={(e) => e.stopPropagation()}
      />
      {galleryPhotos.length > 1 && (
        <button
          type="button"
          className="pub-lightbox-nav pub-lightbox-next"
          aria-label={t("gallery_next")}
          onClick={(e) => { e.stopPropagation(); setLightboxIndex((lightboxIndex + 1) % galleryPhotos.length); }}
        >›</button>
      )}
    </div>
  );

  const highlights = [
    { icon: "🌿", title: t("h_fresh_t"), text: t("h_fresh_d") },
    { icon: "🔥", title: t("h_now_t"), text: t("h_now_d") },
    data.delivery_enabled
      ? { icon: "🛵", title: t("h_delivery_t"), text: t("h_delivery_d") }
      : { icon: "🥡", title: t("h_pickup_t"), text: t("h_pickup_d") },
    { icon: "❤", title: t("h_love_t"), text: t("h_love_d") },
  ];
  const highlightsSection = (
    <section className="pub-section pub-highlights">
      {highlights.map((h, i) => (
        <div className="pub-highlight-card pub-reveal" style={{ animationDelay: `${0.05 + i * 0.1}s` }} key={i}>
          <span className="pub-highlight-icon">{h.icon}</span>
          <div><h3>{h.title}</h3><p>{h.text}</p></div>
        </div>
      ))}
    </section>
  );

  const storySection = (
    <section className="pub-story">
      <div className="pub-story-img">{storyPhoto && <img src={`${API_URL}${storyPhoto.url}`} alt={data.business_name} />}</div>
      <div className="pub-story-copy">
        <span className="pub-section-eyebrow">{t("story_eyebrow")}</span>
        <h2 className="pub-h2">
          {t("story_title").split("\n").map((line, i, arr) => (
            <span key={i}>{line}{i < arr.length - 1 && <br />}</span>
          ))}
        </h2>
        <p>
          {data.business_name} {t("story_born")}{data.city ? ` ${t("story_heart")} ${data.city}` : ""}.
          {" "}{t("story_close")}
        </p>
        {telHref && <a href={telHref} className="pub-cta">{t("story_cta")}</a>}
      </div>
    </section>
  );

  const activePromo = data.promotions[0] || null;
  const promoBig =
    activePromo?.promo_type === "percent_discount" && activePromo.discount_percent
      ? { big: `${activePromo.discount_percent % 1 === 0 ? activePromo.discount_percent : activePromo.discount_percent.toFixed(1)}`, unit: "%" }
      : activePromo?.promo_type === "fixed_discount" && activePromo.discount_cents
        ? { big: `${(activePromo.discount_cents / 100).toFixed(2)}`, unit: "€" }
        : activePromo?.promo_type === "buy_x_get_y" && activePromo.buy_qty && activePromo.get_qty
          ? { big: `${activePromo.buy_qty}x${activePromo.get_qty}`, unit: "" }
          : null;

  const featuredAll = data.offerings.filter((o) => o.is_featured);
  const featuredGroups = Array.from(new Set(featuredAll.map((o) => o.group_name || t("menu"))));
  const featuredShown = featuredFilter ? featuredAll.filter((o) => (o.group_name || t("menu")) === featuredFilter) : featuredAll;

  // Pizze scelte dal titolare come protagoniste della promo attiva (non le stesse dei piatti "in
  // evidenza" generici, sono due vetrine diverse anche se il piatto puo' comparire in entrambe).
  const promoOfferings = activePromo?.offerings || [];
  const promoGrid = promoOfferings.length > 0 && (
    <div className="pub-featured-grid pub-promo-grid" style={{ gridTemplateColumns: `repeat(${Math.min(promoOfferings.length, 5)}, 1fr)` }}>
      {promoOfferings.map((o) => (
        <div key={o.name} className="pub-featured-card">
          <div className="pub-featured-img">
            {o.image_url ? <img src={`${API_URL}${o.image_url}`} alt={o.name} /> : <div className="pub-hero-fallback" />}
          </div>
          <div className="pub-featured-body">
            <span className="pub-item-n">{o.name}</span>
            {o.ingredients && <div className="pub-item-d">{o.ingredients}</div>}
            <span className="pub-featured-price">{(o.price_cents / 100).toFixed(2)} €</span>
          </div>
        </div>
      ))}
    </div>
  );

  const promoCard = activePromo && (
    <div className="pub-promo-panel">
      <div className="pub-promo-copy">
        <span className="pub-promo-eyebrow">{t("promo_eyebrow")}</span>
        {promoBig ? (
          <>
            <div className="pub-promo-big"><span className="pub-promo-big-num">{promoBig.big}</span><span className="pub-promo-big-unit">{promoBig.unit}</span></div>
            {activePromo.promo_type !== "buy_x_get_y" && <div className="pub-promo-off">{t("promo_off")}</div>}
          </>
        ) : (
          <h2 className="pub-h2">{activePromo.title}</h2>
        )}
        <p className="pub-promo-desc">{activePromo.description}</p>
        {telHref && <a href={telHref} className="pub-cta">{orderLabel} →</a>}
      </div>
      <img className="pub-promo-tag-big" src="/promo-tag.png" alt="" />
    </div>
  );

  const featuredSection = featuredAll.length > 0 && (
    <section className="pub-section pub-featured">
      <SectionTitle eyebrow={t("featured_eyebrow")}>{t("featured_title")}</SectionTitle>
      {featuredGroups.length > 1 && (
        <div className="pub-filter-pills">
          <button type="button" className={featuredFilter === null ? "pub-pill pub-pill-active" : "pub-pill"} onClick={() => setFeaturedFilter(null)}>{t("filter_all")}</button>
          {featuredGroups.map((g) => (
            <button type="button" key={g} className={featuredFilter === g ? "pub-pill pub-pill-active" : "pub-pill"} onClick={() => setFeaturedFilter(g)}>{g}</button>
          ))}
        </div>
      )}
      <div className="pub-featured-grid">
        {featuredShown.map((o) => (
          <div key={o.name} className="pub-featured-card">
            <div className="pub-featured-img">
              {o.image_url ? <img src={`${API_URL}${o.image_url}`} alt={o.name} /> : <div className="pub-hero-fallback" />}
            </div>
            <div className="pub-featured-body">
              <span className="pub-item-n">{o.name}</span>
              {o.ingredients && <div className="pub-item-d">{o.ingredients}</div>}
              <span className="pub-featured-price">{(o.price_cents / 100).toFixed(2)} €</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );

  // Sezione promozione: solo se c'e' una promo attiva (nessuna promo = sezione non pubblicata, niente
  // fallback generico). Le pizze scelte per la promo affiancano il box con foto grande e sconto.
  const promoSection = activePromo && (
    <section className="pub-section pub-promo-section">
      <SectionTitle eyebrow={t("promo_eyebrow")}>{t("promotions_title")}</SectionTitle>
      <div className="pub-showcase">
        {promoGrid && <div className="pub-showcase-menu">{promoGrid}</div>}
        <div className="pub-showcase-promo">{promoCard}</div>
      </div>
    </section>
  );

  const ctaBanner = telHref && (
    <section className="pub-cta-banner">
      <h2>{t("cta_hungry")}</h2>
      <p>{data.business_name} {t("cta_ready")}</p>
      <div className="pub-cta-banner-actions">
        <a href={telHref} className="pub-cta">📞 {orderLabel}</a>
        {showBookTable && <a href={telHref!} className="pub-cta pub-cta-ghost">📅 {t("book_table")}</a>}
        {whatsappHref && <a href={whatsappHref} className="pub-cta pub-cta-ghost">💬 {t("cta_whatsapp")}</a>}
      </div>
    </section>
  );

  const hoursSection = Object.keys(data.business_hours).length > 0 && (
    <section className="pub-section" id="orari">
      <SectionTitle eyebrow={t("opening_hours")}>{t("hours")}</SectionTitle>
      {DAY_ORDER.filter((d) => data.business_hours[d]).map((d) => (
        <div key={d} className="pub-hours-row">
          <span>{t(`day_${d}` as UIKey)}</span>
          <span className="pub-muted-txt">{data.business_hours[d].length ? data.business_hours[d].join(", ") : t("closed")}</span>
        </div>
      ))}
    </section>
  );

  const widgetSection = data.elevenlabs_agent_id && (
    <section className="pub-section">
      <SectionTitle>{t("talk")}</SectionTitle>
      <p className="pub-muted-txt">{t("widget_prompt")}</p>
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

  const footer = template === "moderna" ? (
    <footer className="pub-foot pub-foot-rich">
      <div className="pub-foot-grid">
        <div>
          <div className="pub-brand">{data.business_name}</div>
          <p>{[data.category, data.city].filter(Boolean).join(" · ")}</p>
        </div>
        <div>
          <h4>{t("footer_links")}</h4>
          <ul>
            <li><a href="#menu">{t("menu")}</a></li>
            {Object.keys(data.business_hours).length > 0 && <li><a href="#orari">{t("hours")}</a></li>}
            {data.photos.length > 1 && <li><a href="#foto">{t("photos")}</a></li>}
          </ul>
        </div>
        {Object.keys(data.business_hours).length > 0 && (
          <div>
            <h4>{t("hours")}</h4>
            {DAY_ORDER.filter((d) => data.business_hours[d]).slice(0, 3).map((d) => (
              <p key={d}>{t(`day_${d}` as UIKey)}: {data.business_hours[d].length ? data.business_hours[d].join(", ") : t("closed")}</p>
            ))}
          </div>
        )}
        <div>
          <h4>{t("footer_location")}</h4>
          {data.address && <p>{data.address}{data.city ? `, ${data.city}` : ""}</p>}
          {data.phone_number && <p><a href={telHref!} className="pub-foot-phone">📞 {data.phone_number}</a></p>}
          {directionsHref && <a href={directionsHref} target="_blank" rel="noopener noreferrer" className="pub-directions-link">📍 {t("directions")}</a>}
        </div>
      </div>
      <div className="pub-soc-row">📷 📘 💬</div>
      <div className="pub-foot-copy">{data.business_name}</div>
    </footer>
  ) : (
    <footer className="pub-foot">
      <div className="pub-soc-row">📷 📘 💬</div>
      <span className="pub-muted-txt">
        {data.business_name}{data.address ? ` — ${data.address}` : ""}{data.city ? `, ${data.city}${data.province ? ` (${data.province})` : ""}` : ""}
      </span>
    </footer>
  );

  const rootClass = `pub-root t-${template} ${playfair.variable} ${inter.variable} ${caveat.variable} ${oswald.variable}`;

  return (
    <div className={rootClass}>
      <Script src="https://unpkg.com/@elevenlabs/convai-widget-embed" strategy="afterInteractive" />
      {nav}

      {template === "moderna" ? (
        <div className="pub-hero">
          <div className="pub-hero-photo">
            {heroPhoto ? <img src={`${API_URL}${heroPhoto.url}`} alt={data.business_name} /> : <div className="pub-hero-fallback" />}
          </div>
          <HeroDecor items={modernaDecor} />
          <div className="pub-hero-inner">
            <div className="pub-hero-copy">
              {data.category && <span className="pub-section-eyebrow pub-reveal pub-r1">{data.category}</span>}
              <AnimatedHeadline text={headline} baseDelay={0.25} />
              {tagline && <p className="pub-tagline pub-reveal pub-r3">{tagline}</p>}
              <div className="pub-hero-actions pub-reveal pub-r4">
                {telHref && <a href={telHref} className="pub-cta">{orderLabel} →</a>}
                {showBookTable && <a href={telHref!} className="pub-cta pub-cta-ghost">📅 {t("book_table")}</a>}
                {whatsappHref && <a href={whatsappHref} className="pub-cta pub-cta-ghost">💬 WhatsApp</a>}
              </div>
              {statChips.length > 0 && (
                <div className="pub-stats pub-reveal pub-r5">
                  {statChips.map((s, i) => (
                    <span className="pub-stat-chip" key={i}><span>{s.icon}</span>{s.label}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
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
              <span>💬 {t("ticker_whatsapp")}</span>
              <span>{orderLabel} — {data.business_name}</span>
              <span>💬 {t("ticker_whatsapp")}</span>
            </div>
          </div>
        )
      ) : (
        whatsappHref && <div className="pub-promo">💬 {t("promo_whatsapp")}</div>
      )}

      {highlightsSection}
      {featuredSection}
      {menuSection}
      {promoSection}
      {template === "moderna" && storySection}
      {gallerySection}
      {hoursSection}
      {widgetSection}
      {ctaBanner}
      {footer}
      {lightbox}
    </div>
  );
}
