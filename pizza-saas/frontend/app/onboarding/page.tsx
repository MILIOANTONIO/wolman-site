"use client";
import { useEffect, useRef, useState } from "react";
import { api, API_URL, fetchAudioBlobUrl, uploadFile, uploadFiles } from "@/lib/api";

type Offering = { id: string; name: string; description: string | null; price_cents: number; unit: string | null; group_name: string | null; ingredients: string | null; is_available: boolean };
type Voice = { voice_id: string; name: string; preview_url: string | null };
type Plan = { name: string; price_cents: number; included_minutes: number; included_numbers: number };
type Status = { type: "ok" | "error"; text: string } | null;

function StatusInline({ status }: { status: Status }) {
  if (!status) return null;
  return (
    <span style={{ marginLeft: 12, fontWeight: 600, fontSize: "0.9rem", color: status.type === "ok" ? "var(--success)" : "var(--accent)" }}>
      {status.type === "ok" ? "✓ " : "⚠ "}{status.text}
    </span>
  );
}

export default function OnboardingPage() {
  const [businessName, setBusinessName] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [savingBusiness, setSavingBusiness] = useState(false);
  const [businessStatus, setBusinessStatus] = useState<Status>(null);

  const [plans, setPlans] = useState<Record<string, Plan>>({});
  const [selectedPlan, setSelectedPlan] = useState("starter");
  const [planStatus, setPlanStatus] = useState<Status>(null);

  const [offerings, setOfferings] = useState<Offering[]>([]);
  const [newItem, setNewItem] = useState({ name: "", price: "", group_name: "", ingredients: "" });
  const [importing, setImporting] = useState(false);
  const [menuStatus, setMenuStatus] = useState<Status>(null);

  const [personaName, setPersonaName] = useState("Assistente");
  const [tone, setTone] = useState("amichevole");
  const [voices, setVoices] = useState<Voice[]>([]);
  const [voiceId, setVoiceId] = useState("");
  const [playingVoiceId, setPlayingVoiceId] = useState<string | null>(null);
  const [loadingVoiceId, setLoadingVoiceId] = useState<string | null>(null);
  const [savingAgent, setSavingAgent] = useState(false);
  const [agentStatus, setAgentStatus] = useState<Status>(null);
  const previewAudioRef = useRef<HTMLAudioElement | null>(null);
  const previewCacheRef = useRef<Record<string, string>>({}); // voice_id -> blob URL, per non rigenerare l'audio ad ogni ascolto

  const [identityDocType, setIdentityDocType] = useState("owner_id");
  const [uploadedDocs, setUploadedDocs] = useState<string[]>([]);
  const [uploadingIdentityDocs, setUploadingIdentityDocs] = useState(false);
  const [uploadingAddressDocs, setUploadingAddressDocs] = useState(false);
  const [identityDocsStatus, setIdentityDocsStatus] = useState<Status>(null);
  const [addressDocsStatus, setAddressDocsStatus] = useState<Status>(null);

  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [logoStatus, setLogoStatus] = useState<Status>(null);
  const [confirmCallEnabled, setConfirmCallEnabled] = useState(false);

  const [loadingTenant, setLoadingTenant] = useState(true);
  const [reviewStatus, setReviewStatus] = useState<Status>(null);
  const [submittingReview, setSubmittingReview] = useState(false);

  useEffect(() => {
    api.get("/api/onboarding/offerings").then(setOfferings).catch(() => {});
    api.get("/api/onboarding/voices").then(setVoices).catch(() => setVoices([]));
    api.get("/api/onboarding/plans").then(setPlans).catch(() => {});
    api.get("/api/onboarding/tenant").then((t) => {
      setBusinessName(t.business_name || "");
      setAddress(t.address || "");
      setCity(t.city || "");
      setLogoUrl(t.logo_url);
      setSelectedPlan(t.plan);
      setPersonaName(t.agent_persona_name);
      setTone(t.agent_tone);
      setVoiceId(t.agent_voice_id || "");
      setConfirmCallEnabled(t.confirm_call_enabled);
    }).catch(() => {}).finally(() => setLoadingTenant(false));
  }, []);

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
      setLogoStatus({ type: "error", text: err instanceof Error ? err.message : "Errore caricamento logo" });
    } finally {
      setUploadingLogo(false);
      e.target.value = "";
    }
  }

  async function savePlan(planCode: string) {
    setPlanStatus(null);
    try {
      await api.put("/api/onboarding/plan", { plan: planCode });
      setSelectedPlan(planCode);
      setPlanStatus({ type: "ok", text: "Piano selezionato e salvato" });
    } catch (err) {
      setPlanStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    }
  }

  async function saveBusiness(e: React.FormEvent) {
    e.preventDefault();
    setSavingBusiness(true);
    setBusinessStatus(null);
    try {
      await api.put("/api/onboarding/business", { business_name: businessName, address, city, timezone: "Europe/Rome" });
      setBusinessStatus({ type: "ok", text: "Salvato" });
    } catch (err) {
      setBusinessStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSavingBusiness(false);
    }
  }

  async function addOffering(e: React.FormEvent) {
    e.preventDefault();
    setMenuStatus(null);
    try {
      const created = await api.post("/api/onboarding/offerings", {
        name: newItem.name,
        price_cents: Math.round(parseFloat(newItem.price.replace(",", ".")) * 100),
        group_name: newItem.group_name || null,
        ingredients: newItem.ingredients || null,
        is_available: true,
      });
      setOfferings([...offerings, created]);
      setNewItem({ name: "", price: "", group_name: "", ingredients: "" });
      setMenuStatus({ type: "ok", text: `"${created.name}" aggiunta al menu` });
    } catch (err) {
      setMenuStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    }
  }

  async function removeOffering(id: string, name: string) {
    await api.delete(`/api/onboarding/offerings/${id}`);
    setOfferings(offerings.filter((o) => o.id !== id));
    setMenuStatus({ type: "ok", text: `"${name}" rimossa` });
  }

  async function importMenu(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files ? Array.from(e.target.files) : [];
    if (files.length === 0) return;
    setImporting(true);
    setMenuStatus(null);
    try {
      const result = await uploadFiles("/api/onboarding/offerings/import", files);
      setOfferings([...offerings, ...result.items]);
      setMenuStatus({ type: "ok", text: `Importate ${result.imported} voci — controllale qui sotto e correggi/rimuovi quelle sbagliate` });
    } catch (err) {
      setMenuStatus({ type: "error", text: err instanceof Error ? err.message : "Errore importazione" });
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  }

  async function togglePreview(voice: Voice) {
    const audio = previewAudioRef.current;
    if (!audio) return;

    if (playingVoiceId === voice.voice_id) {
      audio.pause();
      setPlayingVoiceId(null);
      return;
    }

    try {
      let url = previewCacheRef.current[voice.voice_id];
      if (!url) {
        setLoadingVoiceId(voice.voice_id);
        // Anteprima generata al volo con una frase di presentazione fissa
        // ("Ciao, sono il tuo nuovo agente AI...") invece del campione
        // generico di ElevenLabs, cosi' si sente davvero come suonerebbe
        // l'agente della pizzeria.
        url = await fetchAudioBlobUrl(`/api/onboarding/voices/${voice.voice_id}/preview`);
        previewCacheRef.current[voice.voice_id] = url;
      }
      audio.src = url;
      await audio.play();
      setPlayingVoiceId(voice.voice_id);
    } catch (err) {
      setAgentStatus({ type: "error", text: err instanceof Error ? err.message : "Errore nella generazione dell'anteprima" });
    } finally {
      setLoadingVoiceId(null);
    }
  }

  async function saveSettings(e: React.FormEvent) {
    e.preventDefault();
    setSavingAgent(true);
    setAgentStatus(null);
    try {
      const voice = voices.find((v) => v.voice_id === voiceId);
      await api.put("/api/onboarding/settings", {
        business_hours: {},
        reservation_slot_minutes: 30,
        agent_persona_name: personaName,
        agent_tone: tone,
        agent_voice_id: voiceId || null,
        agent_voice_name: voice?.name || null,
        confirm_call_enabled: confirmCallEnabled,
      });
      setAgentStatus({ type: "ok", text: "Impostazioni salvate" });
    } catch (err) {
      setAgentStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSavingAgent(false);
    }
  }

  async function uploadDocs(files: FileList | null, docType: string, label: string, setUploading: (v: boolean) => void, setStatus: (s: Status) => void) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setStatus(null);
    try {
      let count = 0;
      for (const file of Array.from(files)) {
        await uploadFile("/api/onboarding/kyc-documents", file, { doc_type: docType });
        setUploadedDocs((prev) => [...prev, `${label}: ${file.name}`]);
        count += 1;
      }
      setStatus({ type: "ok", text: `${count} file caricati` });
    } catch (err) {
      setStatus({ type: "error", text: err instanceof Error ? err.message : "Errore caricamento" });
    } finally {
      setUploading(false);
    }
  }

  async function submitForReview() {
    setSubmittingReview(true);
    setReviewStatus(null);
    try {
      const result = await api.post("/api/onboarding/submit-for-review");
      setReviewStatus({ type: "ok", text: `Inviato! Stato: ${result.status}. Ti avviseremo via email appena attivo.` });
    } catch (err) {
      setReviewStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSubmittingReview(false);
    }
  }

  if (loadingTenant) {
    return <div className="page">Caricamento...</div>;
  }

  return (
    <div className="page">
      <h1>Configura la tua pizzeria</h1>
      <p className="muted">Completa questi passaggi, poi invia per revisione. Ogni sezione mostra la propria conferma di salvataggio accanto al pulsante.</p>

      <div className="card">
        <h2>1. Dati attività</h2>

        <label>Logo</label>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {logoUrl ? (
            <img src={`${API_URL}${logoUrl}`} alt="Logo" style={{ width: 72, height: 72, objectFit: "contain", borderRadius: 8, border: "1px solid var(--border)", background: "white" }} />
          ) : (
            <div style={{ width: 72, height: 72, borderRadius: 8, border: "1px dashed var(--border)", display: "flex", alignItems: "center", justifyContent: "center" }} className="muted">
              nessuno
            </div>
          )}
          <input type="file" accept=".png,.jpg,.jpeg,.webp,.svg" onChange={handleLogoUpload} disabled={uploadingLogo} />
          {uploadingLogo && <span className="muted">Caricamento...</span>}
          <StatusInline status={logoStatus} />
        </div>

        <form onSubmit={saveBusiness}>
          <label>Nome pizzeria</label>
          <input value={businessName} onChange={(e) => setBusinessName(e.target.value)} required />
          <label>Indirizzo</label>
          <input value={address} onChange={(e) => setAddress(e.target.value)} />
          <label>Città</label>
          <input value={city} onChange={(e) => setCity(e.target.value)} />
          <div style={{ display: "flex", alignItems: "center", marginTop: 16 }}>
            <button type="submit" disabled={savingBusiness}>{savingBusiness ? "Salvataggio..." : "Salva"}</button>
            <StatusInline status={businessStatus} />
          </div>
        </form>
      </div>

      <div className="card">
        <h2>2. Piano di abbonamento</h2>
        <p className="muted">Prepagato: il canone e gli eventuali minuti extra si scalano dal credito che ricarichi. Potrai vedere consumi e saldo nella dashboard dopo l&apos;attivazione.</p>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {Object.entries(plans).map(([code, plan]) => (
            <div
              key={code}
              onClick={() => savePlan(code)}
              style={{
                flex: "1 1 160px", minWidth: 160, border: selectedPlan === code ? "2px solid var(--accent)" : "1px solid var(--border)",
                borderRadius: 10, padding: 16, cursor: "pointer", background: selectedPlan === code ? "var(--bg)" : "white",
              }}
            >
              <strong>{plan.name}</strong>
              <div style={{ fontSize: "1.4rem", margin: "8px 0" }}>{(plan.price_cents / 100).toFixed(0)} €<span className="muted" style={{ fontSize: "0.9rem" }}>/mese</span></div>
              <div className="muted">{plan.included_minutes} minuti inclusi</div>
              <div className="muted">{plan.included_numbers} numero italiano</div>
              {selectedPlan === code && <div style={{ marginTop: 8, color: "var(--accent)", fontWeight: 600, fontSize: "0.85rem" }}>✓ Selezionato</div>}
            </div>
          ))}
        </div>
        <StatusInline status={planStatus} />
      </div>

      <div className="card">
        <h2>3. Menu</h2>

        <div style={{ background: "var(--bg)", border: "1px dashed var(--border)", borderRadius: 8, padding: 12, marginBottom: 16 }}>
          <label style={{ marginTop: 0 }}>Importa il menu da file o foto (puoi selezionarne più di uno, anche più pagine/foto insieme)</label>
          <input type="file" multiple accept=".txt,.pdf,.doc,.docx,.jpg,.jpeg,.png,.webp" onChange={importMenu} disabled={importing} />
          {importing && <p className="muted">Sto leggendo il menu, un momento...</p>}
        </div>

        {offerings.length === 0 && <p className="muted">Nessuna voce di menu ancora — importa un file/foto sopra, oppure aggiungi a mano qui sotto.</p>}
        {offerings.map((o) => (
          <div key={o.id} className="order-card">
            <span>
              {o.name} {o.group_name && <span className="muted">({o.group_name})</span>} — {(o.price_cents / 100).toFixed(2)} €
              {o.ingredients && <div className="muted">{o.ingredients}</div>}
            </span>
            <button className="secondary" onClick={() => removeOffering(o.id, o.name)}>Rimuovi</button>
          </div>
        ))}
        <form onSubmit={addOffering} style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap", alignItems: "center" }}>
          <input placeholder="Nome piatto" value={newItem.name} onChange={(e) => setNewItem({ ...newItem, name: e.target.value })} required style={{ flex: "2 1 160px", minWidth: 160 }} />
          <input placeholder="Categoria (es. Pizze)" value={newItem.group_name} onChange={(e) => setNewItem({ ...newItem, group_name: e.target.value })} style={{ flex: "1 1 140px", minWidth: 140 }} />
          <input placeholder="Ingredienti (opzionale)" value={newItem.ingredients} onChange={(e) => setNewItem({ ...newItem, ingredients: e.target.value })} style={{ flex: "2 1 180px", minWidth: 180 }} />
          <input placeholder="Prezzo €" value={newItem.price} onChange={(e) => setNewItem({ ...newItem, price: e.target.value })} required style={{ flex: "0 1 100px", minWidth: 90 }} />
          <button type="submit">Aggiungi</button>
        </form>
        <StatusInline status={menuStatus} />
      </div>

      <div className="card">
        <h2>4. Il tuo agente AI</h2>
        <form onSubmit={saveSettings}>
          <label>Nome dell&apos;agente</label>
          <input value={personaName} onChange={(e) => setPersonaName(e.target.value)} />
          <label>Tono</label>
          <select value={tone} onChange={(e) => setTone(e.target.value)}>
            <option value="amichevole">Amichevole</option>
            <option value="professionale">Professionale</option>
            <option value="brillante">Brillante</option>
          </select>
          <label>Voce (ascolta e scegli){voiceId && voices.find((v) => v.voice_id === voiceId) && <span className="muted"> — attuale: {voices.find((v) => v.voice_id === voiceId)?.name}</span>}</label>
          <audio ref={previewAudioRef} onEnded={() => setPlayingVoiceId(null)} style={{ display: "none" }} />
          <div style={{ maxHeight: 280, overflowY: "auto", border: "1px solid var(--border)", borderRadius: 8 }}>
            {voices.map((v) => (
              <label
                key={v.voice_id}
                style={{
                  display: "flex", alignItems: "center", gap: 10, padding: "8px 12px",
                  borderBottom: "1px solid var(--border)", cursor: "pointer", margin: 0,
                  background: voiceId === v.voice_id ? "var(--bg)" : "transparent",
                }}
              >
                <input type="radio" name="agent_voice" checked={voiceId === v.voice_id} onChange={() => setVoiceId(v.voice_id)} />
                <button
                  type="button"
                  className="secondary"
                  onClick={(e) => { e.preventDefault(); togglePreview(v); }}
                  disabled={loadingVoiceId === v.voice_id}
                  style={{ padding: "4px 10px", flexShrink: 0 }}
                >
                  {loadingVoiceId === v.voice_id ? "…" : playingVoiceId === v.voice_id ? "⏸" : "▶"}
                </button>
                <span style={{ fontSize: "0.95rem" }}>{v.name}</span>
              </label>
            ))}
          </div>
          <div style={{ display: "flex", alignItems: "center", marginTop: 16 }}>
            <button type="submit" disabled={savingAgent}>{savingAgent ? "Salvataggio..." : "Salva impostazioni agente"}</button>
            <StatusInline status={agentStatus} />
          </div>
        </form>
      </div>

      <div className="card">
        <h2>5. Documenti (KYC)</h2>
        <p className="muted">Servono per l&apos;attivazione del numero di telefono: un documento d&apos;identità (o dell&apos;attività) e una prova di indirizzo. Puoi caricare più file per ciascuna sezione (es. fronte e retro).</p>

        <div style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 16 }}>
          <h3 style={{ marginTop: 0, fontSize: "1rem" }}>5a. Documento d&apos;identità o dell&apos;attività</h3>
          <label>Tipo</label>
          <select value={identityDocType} onChange={(e) => setIdentityDocType(e.target.value)}>
            <option value="owner_id">Documento d&apos;identità titolare</option>
            <option value="business_registration">Visura camerale / registrazione attività</option>
          </select>
          <label>File (uno o più)</label>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input type="file" multiple disabled={uploadingIdentityDocs} onChange={(e) => uploadDocs(e.target.files, identityDocType, "Identità/attività", setUploadingIdentityDocs, setIdentityDocsStatus)} />
            {uploadingIdentityDocs && <span className="muted">Caricamento...</span>}
            <StatusInline status={identityDocsStatus} />
          </div>
        </div>

        <div style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12 }}>
          <h3 style={{ marginTop: 0, fontSize: "1rem" }}>5b. Prova di indirizzo</h3>
          <label>File (uno o più)</label>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input type="file" multiple disabled={uploadingAddressDocs} onChange={(e) => uploadDocs(e.target.files, "address_proof", "Indirizzo", setUploadingAddressDocs, setAddressDocsStatus)} />
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

      <div className="card">
        <h2>6. Invia per revisione</h2>
        <p className="muted">Un operatore verificherà i documenti e attiverà il tuo numero e l&apos;agente AI.</p>
        <div style={{ display: "flex", alignItems: "center" }}>
          <button onClick={submitForReview} disabled={submittingReview}>{submittingReview ? "Invio..." : "Invia per revisione"}</button>
          <StatusInline status={reviewStatus} />
        </div>
      </div>
    </div>
  );
}
