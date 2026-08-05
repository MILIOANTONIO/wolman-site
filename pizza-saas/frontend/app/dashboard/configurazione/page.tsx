"use client";
import { useEffect, useState } from "react";
import { api, API_URL, uploadFile } from "@/lib/api";
import { CameraButton } from "@/lib/CameraCapture";
import { useGooglePlacesAutocomplete } from "@/lib/useGooglePlaces";
import PhoneNumberWizard from "@/lib/PhoneNumberWizard";

type Status = { type: "ok" | "error"; text: string } | null;
type ShiftCapacity = { tables: string; seats: string };
const EMPTY_SHIFT: ShiftCapacity = { tables: "", seats: "" };

const CATEGORY_PRESETS = ["pizzeria", "ristorante", "pizzeria e ristorante", "kebab", "hamburgheria", "trattoria"];

const DAYS: { key: string; label: string }[] = [
  { key: "lun", label: "Lunedì" }, { key: "mar", label: "Martedì" }, { key: "mer", label: "Mercoledì" },
  { key: "gio", label: "Giovedì" }, { key: "ven", label: "Venerdì" }, { key: "sab", label: "Sabato" }, { key: "dom", label: "Domenica" },
];

function StatusInline({ status }: { status: Status }) {
  if (!status) return null;
  return (
    <span style={{ marginLeft: 12, fontWeight: 600, fontSize: "0.9rem", color: status.type === "ok" ? "var(--success)" : "var(--accent)" }}>
      {status.type === "ok" ? "✓ " : "⚠ "}{status.text}
    </span>
  );
}

export default function ConfigurazionePage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [businessName, setBusinessName] = useState("");
  const [category, setCategory] = useState("pizzeria");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [province, setProvince] = useState("");
  const [status, setStatus] = useState<string>("");
  const [savingBusiness, setSavingBusiness] = useState(false);
  const [businessStatus, setBusinessStatus] = useState<Status>(null);

  const { containerRef: placesContainerRef, status: placesStatus } = useGooglePlacesAutocomplete((parsed) => {
    if (parsed.address) setAddress(parsed.address);
    if (parsed.city) setCity(parsed.city);
    if (parsed.province) setProvince(parsed.province.toUpperCase());
  });

  const [hours, setHours] = useState<Record<string, string>>({});   // key -> testo tipo "12:00-14:30, 19:00-23:00" (vuoto = chiuso)
  const [savingHours, setSavingHours] = useState(false);
  const [hoursStatus, setHoursStatus] = useState<Status>(null);
  const [hoursOpen, setHoursOpen] = useState(false);

  const [deliveryRadius, setDeliveryRadius] = useState("");
  const [deliveryNotes, setDeliveryNotes] = useState("");
  const [savingDelivery, setSavingDelivery] = useState(false);
  const [deliveryStatus, setDeliveryStatus] = useState<Status>(null);

  const [deliveryEnabled, setDeliveryEnabled] = useState(true);
  const [pickupEnabled, setPickupEnabled] = useState(true);
  const [tableReservationsEnabled, setTableReservationsEnabled] = useState(false);
  const [savingServices, setSavingServices] = useState(false);
  const [servicesStatus, setServicesStatus] = useState<Status>(null);

  const [tableCapacity, setTableCapacity] = useState<Record<string, { pranzo: ShiftCapacity; cena: ShiftCapacity }>>({});
  const [savingCapacity, setSavingCapacity] = useState(false);
  const [capacityStatus, setCapacityStatus] = useState<Status>(null);
  const [capacityOpen, setCapacityOpen] = useState(false);

  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [logoStatus, setLogoStatus] = useState<Status>(null);

  const [identityDocType, setIdentityDocType] = useState("owner_id");
  const [uploadedDocs, setUploadedDocs] = useState<string[]>([]);
  const [uploadingIdentityDocs, setUploadingIdentityDocs] = useState(false);
  const [uploadingAddressDocs, setUploadingAddressDocs] = useState(false);
  const [identityDocsStatus, setIdentityDocsStatus] = useState<Status>(null);
  const [addressDocsStatus, setAddressDocsStatus] = useState<Status>(null);

  function loadTenant() {
    setLoading(true);
    setError(null);
    api.get("/api/onboarding/tenant").then((t) => {
      setBusinessName(t.business_name || "");
      setCategory(t.category || "pizzeria");
      setAddress(t.address || "");
      setCity(t.city || "");
      setProvince(t.province || "");
      setLogoUrl(t.logo_url);
      setStatus(t.status);
      const businessHours: Record<string, string[]> = t.business_hours || {};
      const hoursText: Record<string, string> = {};
      for (const d of DAYS) hoursText[d.key] = (businessHours[d.key] || []).join(", ");
      setHours(hoursText);
      setDeliveryRadius(t.delivery_radius_km != null ? String(t.delivery_radius_km) : "");
      setDeliveryNotes(t.delivery_notes || "");
      setDeliveryEnabled(t.delivery_enabled ?? true);
      setPickupEnabled(t.pickup_enabled ?? true);
      setTableReservationsEnabled(t.table_reservations_enabled ?? false);
      const capacity: Record<string, { pranzo?: { tables?: number; seats?: number }; cena?: { tables?: number; seats?: number } }> = t.table_capacity || {};
      const toShift = (s?: { tables?: number; seats?: number }): ShiftCapacity => ({
        tables: s?.tables != null ? String(s.tables) : "", seats: s?.seats != null ? String(s.seats) : "",
      });
      const capacityText: Record<string, { pranzo: ShiftCapacity; cena: ShiftCapacity }> = {};
      for (const d of DAYS) {
        const c = capacity[d.key] || {};
        capacityText[d.key] = { pranzo: toShift(c.pranzo), cena: toShift(c.cena) };
      }
      setTableCapacity(capacityText);
    }).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }

  useEffect(loadTenant, []);

  async function saveHours() {
    setSavingHours(true);
    setHoursStatus(null);
    try {
      const businessHours: Record<string, string[]> = {};
      for (const d of DAYS) {
        const ranges = hours[d.key]?.split(",").map((r) => r.trim()).filter(Boolean) || [];
        businessHours[d.key] = ranges;
      }
      await api.put("/api/onboarding/business-hours", { business_hours: businessHours });
      setHoursStatus({ type: "ok", text: "Orari salvati" });
    } catch (err) {
      setHoursStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSavingHours(false);
    }
  }

  async function saveTableCapacity() {
    setSavingCapacity(true);
    setCapacityStatus(null);
    try {
      const toInt = (v: string) => parseInt(v, 10) || 0;
      const payload: Record<string, { pranzo: { tables: number; seats: number }; cena: { tables: number; seats: number } }> = {};
      for (const d of DAYS) {
        const c = tableCapacity[d.key] || { pranzo: EMPTY_SHIFT, cena: EMPTY_SHIFT };
        payload[d.key] = {
          pranzo: { tables: toInt(c.pranzo.tables), seats: toInt(c.pranzo.seats) },
          cena: { tables: toInt(c.cena.tables), seats: toInt(c.cena.seats) },
        };
      }
      await api.put("/api/onboarding/table-capacity", { table_capacity: payload });
      setCapacityStatus({ type: "ok", text: "Capacità salvata" });
    } catch (err) {
      setCapacityStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSavingCapacity(false);
    }
  }

  async function saveBusiness(e: React.FormEvent) {
    e.preventDefault();
    setSavingBusiness(true);
    setBusinessStatus(null);
    try {
      await api.put("/api/onboarding/business", { business_name: businessName, category: category || "pizzeria", address, city, province: province || null, timezone: "Europe/Rome" });
      setBusinessStatus({ type: "ok", text: "Salvato" });
    } catch (err) {
      setBusinessStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSavingBusiness(false);
    }
  }

  async function saveDeliveryZone() {
    setSavingDelivery(true);
    setDeliveryStatus(null);
    try {
      const radius = deliveryRadius.trim() ? parseFloat(deliveryRadius.replace(",", ".")) : null;
      await api.put("/api/onboarding/delivery-zone", { delivery_radius_km: radius, delivery_notes: deliveryNotes || null });
      setDeliveryStatus({ type: "ok", text: "Zona di consegna salvata" });
    } catch (err) {
      setDeliveryStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSavingDelivery(false);
    }
  }

  async function saveServices(next: { deliveryEnabled: boolean; pickupEnabled: boolean; tableReservationsEnabled: boolean }) {
    setSavingServices(true);
    setServicesStatus(null);
    try {
      await api.put("/api/onboarding/services", {
        delivery_enabled: next.deliveryEnabled,
        pickup_enabled: next.pickupEnabled,
        table_reservations_enabled: next.tableReservationsEnabled,
      });
      setServicesStatus({ type: "ok", text: "Salvato" });
    } catch (err) {
      setServicesStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSavingServices(false);
    }
  }

  function toggleDelivery() {
    const next = !deliveryEnabled;
    setDeliveryEnabled(next);
    saveServices({ deliveryEnabled: next, pickupEnabled, tableReservationsEnabled });
  }

  function togglePickup() {
    const next = !pickupEnabled;
    setPickupEnabled(next);
    saveServices({ deliveryEnabled, pickupEnabled: next, tableReservationsEnabled });
  }

  function toggleTableReservations() {
    const next = !tableReservationsEnabled;
    setTableReservationsEnabled(next);
    saveServices({ deliveryEnabled, pickupEnabled, tableReservationsEnabled: next });
  }

  async function handleLogoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingLogo(true);
    setLogoStatus(null);
    try {
      const result = await uploadFile("/api/onboarding/logo", file);
      setLogoUrl(result.logo_url);
      setLogoStatus({ type: "ok", text: "Logo caricato" });
    } catch (err) {
      setLogoStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setUploadingLogo(false);
      e.target.value = "";
    }
  }

  async function uploadDocs(files: FileList | File[] | null, docType: string, label: string, setUploading: (v: boolean) => void, setDocStatus: (s: Status) => void) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setDocStatus(null);
    try {
      let count = 0;
      for (const file of Array.from(files)) {
        await uploadFile("/api/onboarding/kyc-documents", file, { doc_type: docType });
        setUploadedDocs((prev) => [...prev, `${label}: ${file.name}`]);
        count += 1;
      }
      setDocStatus({ type: "ok", text: `${count} file caricati` });
    } catch (err) {
      setDocStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setUploading(false);
    }
  }

  if (loading || error) {
    return (
      <div>
        {error ? (
          <div className="error">
            {error}
            <div style={{ marginTop: 12 }}>
              <button onClick={loadTenant}>Riprova</button>
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
      <h1>Configurazione</h1>
      <p className="muted">Stato attuale: <strong>{status}</strong></p>

      <div className="card">
        <h2>Logo</h2>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {logoUrl ? (
            <img src={`${API_URL}${logoUrl}`} alt="Logo" style={{ width: 72, height: 72, objectFit: "contain", borderRadius: 8, border: "1px solid var(--border)", background: "white" }} />
          ) : (
            <div style={{ width: 72, height: 72, borderRadius: 8, border: "1px dashed var(--border)", display: "flex", alignItems: "center", justifyContent: "center" }} className="muted">nessuno</div>
          )}
          <input type="file" accept=".png,.jpg,.jpeg,.webp,.svg" onChange={handleLogoUpload} disabled={uploadingLogo} />
          {uploadingLogo && <span className="muted">Caricamento...</span>}
          <StatusInline status={logoStatus} />
        </div>
      </div>

      <div className="card">
        <h2>Dati attività</h2>
        <form onSubmit={saveBusiness}>
          <label>Nome attività</label>
          <input value={businessName} onChange={(e) => setBusinessName(e.target.value)} required />
          <label>Tipo di attività</label>
          <select
            value={CATEGORY_PRESETS.includes(category) ? category : "altro"}
            onChange={(e) => setCategory(e.target.value === "altro" ? "" : e.target.value)}
          >
            <option value="pizzeria">Pizzeria</option>
            <option value="ristorante">Ristorante</option>
            <option value="pizzeria e ristorante">Pizzeria e ristorante</option>
            <option value="kebab">Kebab</option>
            <option value="hamburgheria">Hamburgheria</option>
            <option value="trattoria">Trattoria</option>
            <option value="altro">Altro (specifica tu)</option>
          </select>
          {!CATEGORY_PRESETS.includes(category) && (
            <input
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="es. hamburgheseria, gastronomia, gelateria..."
              style={{ marginTop: 8 }}
            />
          )}
          <p className="muted" style={{ fontSize: "0.8rem", marginTop: 2 }}>Lo dice ai clienti l&apos;agente AI durante ordini e prenotazioni.</p>
          <label style={{ display: placesStatus === "ready" ? "block" : "none" }}>Cerca indirizzo</label>
          <div ref={placesContainerRef} className="places-autocomplete" style={{ display: placesStatus === "ready" ? "block" : "none" }} />
          {placesStatus === "ready" && (
            <p className="muted" style={{ fontSize: "0.8rem", marginTop: 2 }}>Scegli un suggerimento per compilare automaticamente indirizzo, città e provincia.</p>
          )}
          <label>Indirizzo</label>
          <input value={address} onChange={(e) => setAddress(e.target.value)} autoComplete="off" />
          {placesStatus === "unavailable" && (
            <p className="muted" style={{ fontSize: "0.8rem", marginTop: 2 }}>Suggerimenti indirizzo non disponibili al momento — inserisci a mano.</p>
          )}
          <div style={{ display: "flex", gap: 12 }}>
            <div style={{ flex: 2 }}>
              <label>Città</label>
              <input value={city} onChange={(e) => setCity(e.target.value)} />
            </div>
            <div style={{ flex: 1 }}>
              <label>Provincia</label>
              <input value={province} placeholder="es. MI" maxLength={10} onChange={(e) => setProvince(e.target.value.toUpperCase())} />
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", marginTop: 16 }}>
            <button type="submit" disabled={savingBusiness}>{savingBusiness ? "Salvataggio..." : "Salva"}</button>
            <StatusInline status={businessStatus} />
          </div>
        </form>
      </div>

      <div className="card">
        <h2>Numero di telefono</h2>
        <PhoneNumberWizard />
      </div>

      <div className="card">
        <h2>Servizi offerti</h2>
        <p className="muted">Cosa può proporre l&apos;agente AI ai clienti durante l&apos;ordine. Cambia subito il comportamento di chiamate e WhatsApp.</p>

        <div className="toggle-row">
          <div>
            <div className="toggle-label">Consegna a domicilio</div>
            <div className="toggle-desc">Se disattiva, l&apos;agente propone solo l&apos;asporto.</div>
          </div>
          <label className="switch">
            <input type="checkbox" checked={deliveryEnabled} disabled={savingServices} onChange={toggleDelivery} />
            <span className="slider" />
          </label>
        </div>

        <div className="toggle-row">
          <div>
            <div className="toggle-label">Asporto</div>
            <div className="toggle-desc">Se disattiva, l&apos;agente non propone piu' il ritiro in negozio.</div>
          </div>
          <label className="switch">
            <input type="checkbox" checked={pickupEnabled} disabled={savingServices} onChange={togglePickup} />
            <span className="slider" />
          </label>
        </div>

        <div className="toggle-row">
          <div>
            <div className="toggle-label">Prenotazione tavoli</div>
            <div className="toggle-desc">Se attiva, l&apos;agente può prendere prenotazioni per il locale (nome, persone, data e ora).</div>
          </div>
          <label className="switch">
            <input type="checkbox" checked={tableReservationsEnabled} disabled={savingServices} onChange={toggleTableReservations} />
            <span className="slider" />
          </label>
        </div>

        <div style={{ marginTop: 8 }}>
          <StatusInline status={servicesStatus} />
        </div>
      </div>

      {tableReservationsEnabled && (() => {
        const configuredDays = DAYS.filter((d) => {
          const row = tableCapacity[d.key];
          return row && (Number(row.pranzo.seats) || Number(row.pranzo.tables) || Number(row.cena.seats) || Number(row.cena.tables));
        });
        const totalSeats = DAYS.reduce((sum, d) => {
          const row = tableCapacity[d.key];
          if (!row) return sum;
          return sum + (Number(row.pranzo.seats) || 0) + (Number(row.cena.seats) || 0);
        }, 0);

        return (
          <div className="card">
            <h2>Capacità sala</h2>
            <p className="muted">Numero di tavoli e posti a sedere totali per pranzo e cena, per ogni giorno. Lascia 0 per i giorni/turni chiusi. L&apos;agente lo usa come indicazione di massima quando prende le prenotazioni.</p>

            <div style={{ display: "flex", alignItems: "center", gap: 10, border: "1px solid var(--border)", borderRadius: 8, padding: "8px 12px" }}>
              <span style={{ fontSize: "0.95rem", flex: 1 }}>
                {configuredDays.length === 0
                  ? "Non ancora configurata"
                  : `${configuredDays.length} ${configuredDays.length === 1 ? "giorno configurato" : "giorni configurati"} — ${totalSeats} posti/settimana`}
              </span>
              <button type="button" className="secondary" onClick={() => setCapacityOpen((o) => !o)} style={{ padding: "4px 10px", flexShrink: 0 }}>
                {capacityOpen ? "Chiudi" : "Modifica capacità"}
              </button>
            </div>

            {capacityOpen && (
              <>
                {DAYS.map((d) => {
                  const row = tableCapacity[d.key] || { pranzo: EMPTY_SHIFT, cena: EMPTY_SHIFT };
                  const setShift = (shift: "pranzo" | "cena", field: "tables" | "seats", value: string) => {
                    setTableCapacity({
                      ...tableCapacity,
                      [d.key]: { ...row, [shift]: { ...row[shift], [field]: value } },
                    });
                  };
                  return (
                    <div key={d.key} style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--border)" }}>
                      <div style={{ fontWeight: 600, marginBottom: 6 }}>{d.label}</div>
                      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
                        {(["pranzo", "cena"] as const).map((shift) => (
                          <div key={shift} style={{ flex: "1 1 200px" }}>
                            <div className="muted" style={{ fontSize: "0.8rem", marginBottom: 2, textTransform: "capitalize" }}>{shift}</div>
                            <div style={{ display: "flex", gap: 8 }}>
                              <div style={{ flex: 1 }}>
                                <label style={{ margin: "0 0 2px", fontSize: "0.75rem", fontWeight: 400 }}>Tavoli</label>
                                <input type="number" min={0} placeholder="0" value={row[shift].tables} onChange={(e) => setShift(shift, "tables", e.target.value)} />
                              </div>
                              <div style={{ flex: 1 }}>
                                <label style={{ margin: "0 0 2px", fontSize: "0.75rem", fontWeight: 400 }}>Posti</label>
                                <input type="number" min={0} placeholder="0" value={row[shift].seats} onChange={(e) => setShift(shift, "seats", e.target.value)} />
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
                <div style={{ display: "flex", alignItems: "center", marginTop: 16 }}>
                  <button onClick={saveTableCapacity} disabled={savingCapacity}>{savingCapacity ? "Salvataggio..." : "Salva capacità"}</button>
                  <StatusInline status={capacityStatus} />
                </div>
              </>
            )}
          </div>
        );
      })()}

      {deliveryEnabled && (
        <div className="card">
          <h2>Zona di consegna (delivery)</h2>
          <p className="muted">Raggio approssimativo entro cui consegnate a domicilio, calcolato dall&apos;indirizzo del locale. L&apos;agente AI lo userà per avvisare i clienti fuori zona.</p>
          <label>Raggio di consegna (km)</label>
          <input value={deliveryRadius} placeholder="es. 5" onChange={(e) => setDeliveryRadius(e.target.value)} />
          <label>Note (opzionale)</label>
          <textarea rows={3} placeholder="es. non consegniamo oltre il ponte, o elenco quartieri/CAP" value={deliveryNotes} onChange={(e) => setDeliveryNotes(e.target.value)} />
          <div style={{ display: "flex", alignItems: "center", marginTop: 16 }}>
            <button onClick={saveDeliveryZone} disabled={savingDelivery}>{savingDelivery ? "Salvataggio..." : "Salva zona"}</button>
            <StatusInline status={deliveryStatus} />
          </div>
        </div>
      )}

      {(() => {
        const openDays = DAYS.filter((d) => (hours[d.key] || "").trim() !== "");
        return (
          <div className="card">
            <h2>Orari di apertura</h2>
            <p className="muted">Per ogni giorno: lascia vuoto per "chiuso", oppure scrivi le fasce orarie separate da virgola (es. <code>12:00-14:30, 19:00-23:00</code> per pranzo e cena).</p>

            <div style={{ display: "flex", alignItems: "center", gap: 10, border: "1px solid var(--border)", borderRadius: 8, padding: "8px 12px" }}>
              <span style={{ fontSize: "0.95rem", flex: 1 }}>
                {openDays.length === 0 ? "Non ancora configurati" : `${openDays.length} giorni aperti, ${7 - openDays.length} chiusi`}
              </span>
              <button type="button" className="secondary" onClick={() => setHoursOpen((o) => !o)} style={{ padding: "4px 10px", flexShrink: 0 }}>
                {hoursOpen ? "Chiudi" : "Modifica orari"}
              </button>
            </div>

            {hoursOpen && (
              <>
                {DAYS.map((d) => (
                  <div key={d.key} style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 8 }}>
                    <label style={{ margin: 0, width: 90, flexShrink: 0 }}>{d.label}</label>
                    <input
                      placeholder="chiuso"
                      value={hours[d.key] || ""}
                      onChange={(e) => setHours({ ...hours, [d.key]: e.target.value })}
                    />
                  </div>
                ))}
                <div style={{ display: "flex", alignItems: "center", marginTop: 16 }}>
                  <button onClick={saveHours} disabled={savingHours}>{savingHours ? "Salvataggio..." : "Salva orari"}</button>
                  <StatusInline status={hoursStatus} />
                </div>
              </>
            )}
          </div>
        );
      })()}

      <div className="card">
        <h2>Documenti (KYC)</h2>
        <p className="muted">Servono per l&apos;attivazione/rinnovo del numero di telefono.</p>

        <div style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 16 }}>
          <h3 style={{ marginTop: 0, fontSize: "1rem" }}>Documento d&apos;identità o dell&apos;attività</h3>
          <label>Tipo</label>
          <select value={identityDocType} onChange={(e) => setIdentityDocType(e.target.value)}>
            <option value="owner_id">Documento d&apos;identità titolare</option>
            <option value="business_registration">Visura camerale / registrazione attività</option>
          </select>
          <label>File (uno o più) o scatta una foto</label>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <input type="file" multiple disabled={uploadingIdentityDocs} onChange={(e) => uploadDocs(e.target.files, identityDocType, "Identità/attività", setUploadingIdentityDocs, setIdentityDocsStatus)} style={{ width: "auto" }} />
            <CameraButton onCapture={(file) => uploadDocs([file], identityDocType, "Identità/attività", setUploadingIdentityDocs, setIdentityDocsStatus)} />
            {uploadingIdentityDocs && <span className="muted">Caricamento...</span>}
            <StatusInline status={identityDocsStatus} />
          </div>
        </div>

        <div style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12 }}>
          <h3 style={{ marginTop: 0, fontSize: "1rem" }}>Prova di indirizzo</h3>
          <label>File (uno o più) o scatta una foto</label>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <input type="file" multiple disabled={uploadingAddressDocs} onChange={(e) => uploadDocs(e.target.files, "address_proof", "Indirizzo", setUploadingAddressDocs, setAddressDocsStatus)} style={{ width: "auto" }} />
            <CameraButton onCapture={(file) => uploadDocs([file], "address_proof", "Indirizzo", setUploadingAddressDocs, setAddressDocsStatus)} />
            {uploadingAddressDocs && <span className="muted">Caricamento...</span>}
            <StatusInline status={addressDocsStatus} />
          </div>
        </div>

        {uploadedDocs.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <strong style={{ fontSize: "0.9rem" }}>File caricati in questa sessione:</strong>
            <ul>{uploadedDocs.map((d, i) => <li key={i}>{d}</li>)}</ul>
          </div>
        )}
      </div>

      <TeamManager />

      {status === "pending_kyc" && (
        <div className="card">
          <h2>Invia per revisione</h2>
          <p className="muted">Quando hai completato menu, agente e documenti, invia la tua pizzeria per l&apos;approvazione.</p>
          <SubmitForReview onDone={(s) => setStatus(s)} />
        </div>
      )}
    </div>
  );
}

type TeamMember = { id: string; email: string; role: string; role_label: string };
const TEAM_ROLES = [
  { value: "cuoco", label: "Cuoco/pizzaiolo — riceve le comande e aggiorna lo stato" },
  { value: "receptionista", label: "Receptionist — gestisce le prenotazioni tavoli" },
  { value: "delivery", label: "Delivery — vede e aggiorna le consegne" },
];

function TeamManager() {
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("cuoco");
  const [saving, setSaving] = useState(false);
  const [teamStatus, setTeamStatus] = useState<Status>(null);

  function reload() {
    api.get("/api/team").then(setMembers).catch(() => {});
  }

  useEffect(reload, []);

  async function addMember(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setTeamStatus(null);
    try {
      await api.post("/api/team", { email, password, role });
      setEmail("");
      setPassword("");
      setTeamStatus({ type: "ok", text: "Account creato" });
      reload();
    } catch (err) {
      setTeamStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSaving(false);
    }
  }

  async function removeMember(id: string, memberEmail: string) {
    try {
      await api.delete(`/api/team/${id}`);
      setMembers(members.filter((m) => m.id !== id));
      setTeamStatus({ type: "ok", text: `Rimosso ${memberEmail}` });
    } catch (err) {
      setTeamStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    }
  }

  return (
    <div className="card">
      <h2>Team</h2>
      <p className="muted">Crea accessi separati per il personale: ognuno vede solo la propria sezione (comande, prenotazioni o consegne), non il resto della gestione.</p>

      {members.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          {members.map((m) => (
            <div key={m.id} className="order-card">
              <div>
                <strong>{m.email}</strong>
                <div className="muted">{m.role_label}</div>
              </div>
              <button className="secondary" style={{ padding: "4px 10px", fontSize: "0.8rem" }} onClick={() => removeMember(m.id, m.email)}>
                Rimuovi
              </button>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={addMember}>
        <label>Ruolo</label>
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          {TEAM_ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>
        <label>Email</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <label>Password (almeno 8 caratteri)</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
        <div style={{ display: "flex", alignItems: "center", marginTop: 16 }}>
          <button type="submit" disabled={saving}>{saving ? "Creazione..." : "Crea accesso"}</button>
          <StatusInline status={teamStatus} />
        </div>
      </form>
    </div>
  );
}

function SubmitForReview({ onDone }: { onDone: (status: string) => void }) {
  const [submitting, setSubmitting] = useState(false);
  const [reviewStatus, setReviewStatus] = useState<Status>(null);

  async function submit() {
    setSubmitting(true);
    setReviewStatus(null);
    try {
      const result = await api.post("/api/onboarding/submit-for-review");
      setReviewStatus({ type: "ok", text: `Inviato! Stato: ${result.status}` });
      onDone(result.status);
    } catch (err) {
      setReviewStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ display: "flex", alignItems: "center" }}>
      <button onClick={submit} disabled={submitting}>{submitting ? "Invio..." : "Invia per revisione"}</button>
      <StatusInline status={reviewStatus} />
    </div>
  );
}
