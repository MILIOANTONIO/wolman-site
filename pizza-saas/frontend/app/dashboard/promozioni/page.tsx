"use client";
import { useEffect, useState } from "react";
import { api, API_URL } from "@/lib/api";

type ScheduleDay = { enabled: boolean; from: string; to: string };
type Schedule = Record<string, ScheduleDay>;

type PromoType = "buy_x_get_y" | "percent_discount" | "fixed_discount";

type Promotion = {
  id: string; title: string; promo_type: PromoType;
  buy_qty: number | null; get_qty: number | null;
  discount_percent: number | null; discount_cents: number | null;
  min_order_cents: number | null; applies_to_group: string | null;
  offering_ids: string[];
  schedule: Schedule; is_active: boolean;
};

type OfferingOption = { id: string; name: string; group_name: string | null; image_url: string | null };

type Status = { type: "ok" | "error"; text: string } | null;

const DAYS: { key: string; label: string }[] = [
  { key: "lun", label: "Lunedì" }, { key: "mar", label: "Martedì" }, { key: "mer", label: "Mercoledì" },
  { key: "gio", label: "Giovedì" }, { key: "ven", label: "Venerdì" }, { key: "sab", label: "Sabato" }, { key: "dom", label: "Domenica" },
];
const EMPTY_DAY: ScheduleDay = { enabled: false, from: "", to: "" };
const EMPTY_SCHEDULE: Schedule = Object.fromEntries(DAYS.map((d) => [d.key, { ...EMPTY_DAY }]));

const PROMO_TYPES: { value: PromoType; label: string; example: string }[] = [
  { value: "buy_x_get_y", label: "Paghi X, ricevi Y", example: "es. 2x3, 3x4, 1x2" },
  { value: "percent_discount", label: "Sconto percentuale", example: "es. 10% sopra i 25 €" },
  { value: "fixed_discount", label: "Sconto importo fisso", example: "es. 5 € sopra i 30 €" },
];

type Draft = {
  title: string; promo_type: PromoType;
  buy_qty: string; get_qty: string;
  discount_percent: string; discount_cents: string;
  min_order_cents: string; applies_to_group: string;
  offering_ids: string[];
  schedule: Schedule; is_active: boolean;
};

const EMPTY_DRAFT: Draft = {
  title: "", promo_type: "buy_x_get_y",
  buy_qty: "", get_qty: "", discount_percent: "", discount_cents: "",
  min_order_cents: "", applies_to_group: "",
  offering_ids: [],
  schedule: EMPTY_SCHEDULE, is_active: true,
};

function StatusInline({ status }: { status: Status }) {
  if (!status) return null;
  return (
    <span style={{ marginLeft: 12, fontWeight: 600, fontSize: "0.9rem", color: status.type === "ok" ? "var(--success)" : "var(--accent)" }}>
      {status.type === "ok" ? "✓ " : "⚠ "}{status.text}
    </span>
  );
}

function promoToDraft(p: Promotion): Draft {
  return {
    title: p.title, promo_type: p.promo_type,
    buy_qty: p.buy_qty != null ? String(p.buy_qty) : "",
    get_qty: p.get_qty != null ? String(p.get_qty) : "",
    discount_percent: p.discount_percent != null ? String(p.discount_percent) : "",
    discount_cents: p.discount_cents != null ? (p.discount_cents / 100).toFixed(2).replace(".", ",") : "",
    min_order_cents: p.min_order_cents != null ? (p.min_order_cents / 100).toFixed(2).replace(".", ",") : "",
    applies_to_group: p.applies_to_group || "",
    offering_ids: p.offering_ids || [],
    schedule: { ...EMPTY_SCHEDULE, ...p.schedule },
    is_active: p.is_active,
  };
}

function draftToBody(d: Draft) {
  const parseEuro = (s: string) => (s.trim() ? Math.round(parseFloat(s.replace(",", ".")) * 100) : null);
  return {
    title: d.title,
    promo_type: d.promo_type,
    buy_qty: d.promo_type === "buy_x_get_y" ? parseInt(d.buy_qty, 10) || null : null,
    get_qty: d.promo_type === "buy_x_get_y" ? parseInt(d.get_qty, 10) || null : null,
    discount_percent: d.promo_type === "percent_discount" ? parseFloat(d.discount_percent.replace(",", ".")) || null : null,
    discount_cents: d.promo_type === "fixed_discount" ? parseEuro(d.discount_cents) : null,
    min_order_cents: parseEuro(d.min_order_cents),
    applies_to_group: d.applies_to_group || null,
    offering_ids: d.offering_ids,
    schedule: d.schedule,
    is_active: d.is_active,
  };
}

function scheduleSummary(schedule: Schedule): string {
  const active = DAYS.filter((d) => schedule[d.key]?.enabled);
  if (active.length === 0) return "nessun giorno configurato";
  if (active.length === 7) {
    const { from, to } = schedule[DAYS[0].key];
    return from && to ? `Tutti i giorni, ${from}-${to}` : "Tutti i giorni";
  }
  return active.map((d) => {
    const { from, to } = schedule[d.key];
    return from && to ? `${d.label} ${from}-${to}` : d.label;
  }).join(", ");
}

function promoSummary(p: Promotion | Draft): string {
  if (p.promo_type === "buy_x_get_y") {
    const buy = "buy_qty" in p ? p.buy_qty : parseInt((p as Draft).buy_qty, 10);
    const get = "get_qty" in p ? p.get_qty : parseInt((p as Draft).get_qty, 10);
    return buy && get ? `Paghi ${buy}, ricevi ${get}` : "Paghi X, ricevi Y";
  }
  if (p.promo_type === "percent_discount") {
    const pct = "discount_percent" in p ? p.discount_percent : parseFloat((p as Draft).discount_percent.replace(",", "."));
    return pct ? `${pct}% di sconto` : "Sconto percentuale";
  }
  const cents = "discount_cents" in p && typeof p.discount_cents === "number" ? p.discount_cents : null;
  if (cents != null) return `${(cents / 100).toFixed(2)} € di sconto`;
  return "Sconto importo fisso";
}

export default function PromozioniPage() {
  const [promotions, setPromotions] = useState<Promotion[] | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [offerings, setOfferings] = useState<OfferingOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [saving, setSaving] = useState(false);

  function reload() {
    setError(null);
    api.get("/api/onboarding/promotions").then(setPromotions).catch((e) => setError(e.message));
    api.get("/api/onboarding/offerings").then((items: OfferingOption[]) => {
      const names = Array.from(new Set(items.map((o) => o.group_name).filter((g): g is string => !!g)));
      setCategories(names);
      setOfferings(items);
    }).catch(() => {});
  }

  useEffect(reload, []);

  function openNew() {
    setEditingId(null);
    setDraft(EMPTY_DRAFT);
    setFormOpen(true);
    setStatus(null);
  }

  function openEdit(p: Promotion) {
    setEditingId(p.id);
    setDraft(promoToDraft(p));
    setFormOpen(true);
    setStatus(null);
  }

  function closeForm() {
    setFormOpen(false);
    setEditingId(null);
  }

  function setDay(key: string, field: keyof ScheduleDay, value: string | boolean) {
    setDraft({ ...draft, schedule: { ...draft.schedule, [key]: { ...draft.schedule[key], [field]: value } } });
  }

  function applyAllDays() {
    const first = draft.schedule[DAYS[0].key];
    const filled: Schedule = Object.fromEntries(DAYS.map((d) => [d.key, { enabled: true, from: first.from, to: first.to }]));
    setDraft({ ...draft, schedule: filled });
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setStatus(null);
    try {
      const body = draftToBody(draft);
      if (editingId) {
        const updated = await api.put(`/api/onboarding/promotions/${editingId}`, body);
        setPromotions((prev) => (prev || []).map((p) => (p.id === editingId ? updated : p)));
        setStatus({ type: "ok", text: `"${updated.title}" aggiornata` });
      } else {
        const created = await api.post("/api/onboarding/promotions", body);
        setPromotions((prev) => [created, ...(prev || [])]);
        setStatus({ type: "ok", text: `"${created.title}" creata` });
      }
      closeForm();
    } catch (err) {
      setStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(p: Promotion) {
    const updated = await api.put(`/api/onboarding/promotions/${p.id}`, { ...draftToBody(promoToDraft(p)), is_active: !p.is_active });
    setPromotions((prev) => (prev || []).map((x) => (x.id === p.id ? updated : x)));
  }

  async function remove(p: Promotion) {
    await api.delete(`/api/onboarding/promotions/${p.id}`);
    setPromotions((prev) => (prev || []).filter((x) => x.id !== p.id));
    setStatus({ type: "ok", text: `"${p.title}" rimossa` });
  }

  if (!promotions) {
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
      <h1>Promozioni</h1>
      <p className="muted">
        Sconti e offerte che l&apos;agente AI propone ai clienti al telefono e su WhatsApp — il totale con lo sconto viene sempre
        ricalcolato automaticamente, l&apos;agente non fa mai i conti da solo.
      </p>

      {!formOpen && (
        <div style={{ marginBottom: 16 }}>
          <button onClick={openNew}>+ Nuova promozione</button>
          <StatusInline status={status} />
        </div>
      )}

      {formOpen && (
        <div className="card">
          <h2>{editingId ? "Modifica promozione" : "Nuova promozione"}</h2>
          <form onSubmit={save}>
            <label>Titolo</label>
            <input
              placeholder='es. "2x3 su tutte le pizze del martedì"'
              value={draft.title}
              onChange={(e) => setDraft({ ...draft, title: e.target.value })}
              required
            />

            <label style={{ marginTop: 12 }}>Tipo di promozione</label>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {PROMO_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  className={draft.promo_type === t.value ? "" : "secondary"}
                  style={{ flex: "1 1 200px", textAlign: "left" }}
                  onClick={() => setDraft({ ...draft, promo_type: t.value })}
                >
                  <div>{t.label}</div>
                  <div className="muted" style={{ fontSize: "0.75rem", fontWeight: 400 }}>{t.example}</div>
                </button>
              ))}
            </div>

            {draft.promo_type === "buy_x_get_y" && (
              <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
                <div style={{ flex: 1 }}>
                  <label>Paghi</label>
                  <input type="number" min={1} value={draft.buy_qty} onChange={(e) => setDraft({ ...draft, buy_qty: e.target.value })} required />
                </div>
                <div style={{ flex: 1 }}>
                  <label>Ricevi</label>
                  <input type="number" min={1} value={draft.get_qty} onChange={(e) => setDraft({ ...draft, get_qty: e.target.value })} required />
                </div>
              </div>
            )}
            {draft.promo_type === "percent_discount" && (
              <div style={{ marginTop: 12 }}>
                <label>Percentuale di sconto (%)</label>
                <input type="number" min={1} max={100} value={draft.discount_percent} onChange={(e) => setDraft({ ...draft, discount_percent: e.target.value })} required />
              </div>
            )}
            {draft.promo_type === "fixed_discount" && (
              <div style={{ marginTop: 12 }}>
                <label>Sconto (€)</label>
                <input placeholder="5,00" value={draft.discount_cents} onChange={(e) => setDraft({ ...draft, discount_cents: e.target.value })} required />
              </div>
            )}

            <div style={{ display: "flex", gap: 12, marginTop: 12, flexWrap: "wrap" }}>
              <div style={{ flex: "1 1 200px" }}>
                <label>Spesa minima ordine (€, opzionale)</label>
                <input placeholder="lascia vuoto se nessuna soglia" value={draft.min_order_cents} onChange={(e) => setDraft({ ...draft, min_order_cents: e.target.value })} />
              </div>
              <div style={{ flex: "1 1 200px" }}>
                <label>Valida solo su categoria (opzionale)</label>
                <select value={draft.applies_to_group} onChange={(e) => setDraft({ ...draft, applies_to_group: e.target.value })}>
                  <option value="">Tutto il menu</option>
                  {categories.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            </div>

            <div style={{ marginTop: 16 }}>
              <label>Pizze da mostrare in vetrina per questa promo (opzionale)</label>
              <p className="muted" style={{ margin: "0 0 8px", fontSize: "0.8rem" }}>
                Le foto scelte qui compaiono nel riquadro promozione della pagina pubblica. Se non scegli nulla, viene usata una foto generica.
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {offerings.length === 0 && <span className="muted" style={{ fontSize: "0.85rem" }}>Nessun piatto nel menu ancora.</span>}
                {offerings.map((o) => {
                  const checked = draft.offering_ids.includes(o.id);
                  return (
                    <button
                      key={o.id}
                      type="button"
                      onClick={() =>
                        setDraft({
                          ...draft,
                          offering_ids: checked ? draft.offering_ids.filter((id) => id !== o.id) : [...draft.offering_ids, o.id],
                        })
                      }
                      className={checked ? "" : "secondary"}
                      style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 12px 6px 6px", fontSize: "0.85rem" }}
                    >
                      {o.image_url ? (
                        <img src={`${API_URL}${o.image_url}`} alt="" style={{ width: 28, height: 28, objectFit: "cover", borderRadius: 5 }} />
                      ) : (
                        <span style={{ width: 28, height: 28, borderRadius: 5, background: "rgba(120,100,80,0.18)", display: "inline-block" }} />
                      )}
                      {o.name}
                    </button>
                  );
                })}
              </div>
            </div>

            <div style={{ marginTop: 16, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <label style={{ margin: 0 }}>Validità: giorni e orari</label>
              <button type="button" className="secondary" style={{ padding: "4px 10px", fontSize: "0.8rem" }} onClick={applyAllDays}>
                Applica a tutti i giorni
              </button>
            </div>
            {DAYS.map((d) => {
              const row = draft.schedule[d.key] || EMPTY_DAY;
              return (
                <div key={d.key} style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 8, flexWrap: "wrap" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: 6, flex: "0 1 130px", margin: 0 }}>
                    <input type="checkbox" style={{ width: "auto" }} checked={row.enabled} onChange={(e) => setDay(d.key, "enabled", e.target.checked)} />
                    {d.label}
                  </label>
                  <input
                    type="time" value={row.from} disabled={!row.enabled}
                    onChange={(e) => setDay(d.key, "from", e.target.value)}
                    style={{ flex: "0 1 130px" }}
                  />
                  <span className="muted">-</span>
                  <input
                    type="time" value={row.to} disabled={!row.enabled}
                    onChange={(e) => setDay(d.key, "to", e.target.value)}
                    style={{ flex: "0 1 130px" }}
                  />
                  <span className="muted" style={{ fontSize: "0.8rem" }}>(vuoto = tutto il giorno)</span>
                </div>
              );
            })}

            <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 12 }}>
              <button type="submit" disabled={saving}>{saving ? "Salvataggio..." : "Salva promozione"}</button>
              <button type="button" className="secondary" onClick={closeForm}>Annulla</button>
              <StatusInline status={status} />
            </div>
          </form>
        </div>
      )}

      {promotions.length === 0 && !formOpen && <p className="muted">Nessuna promozione ancora — creane una sopra.</p>}

      {promotions.map((p) => (
        <div key={p.id} className="card" style={{ opacity: p.is_active ? 1 : 0.6 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 8 }}>
            <div>
              <h2 style={{ margin: 0 }}>{p.title}</h2>
              <p className="muted" style={{ margin: "4px 0 0" }}>
                {promoSummary(p)}
                {p.min_order_cents ? ` — da ${(p.min_order_cents / 100).toFixed(2)} €` : ""}
                {p.applies_to_group ? ` — solo su ${p.applies_to_group}` : ""}
              </p>
              <p className="muted" style={{ margin: "4px 0 0", fontSize: "0.85rem" }}>{scheduleSummary(p.schedule)}</p>
            </div>
            <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
              <span className="badge">{p.is_active ? "Attiva" : "Disattivata"}</span>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button className="secondary" style={{ padding: "4px 10px", fontSize: "0.8rem" }} onClick={() => openEdit(p)}>Modifica</button>
            <button className="secondary" style={{ padding: "4px 10px", fontSize: "0.8rem" }} onClick={() => toggleActive(p)}>
              {p.is_active ? "Disattiva" : "Attiva"}
            </button>
            <button className="secondary" style={{ padding: "4px 10px", fontSize: "0.8rem" }} onClick={() => remove(p)}>Elimina</button>
          </div>
        </div>
      ))}
    </div>
  );
}
