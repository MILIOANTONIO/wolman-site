"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Status = { type: "ok" | "error"; text: string } | null;

type AvailableNumber = {
  available_did_id: string; number: string; city_name: string | null;
  sku_id: string; needs_registration: boolean; setup_price: string; monthly_price: string;
};

type DidwwStatus = {
  exists: boolean;
  available_did_id?: string | null;
  phone_number?: string | null;
  identity_id?: string | null;
  address_id?: string | null;
  documents_uploaded?: number;
  order_id?: string | null;
  order_status?: string | null;
  verification_id?: string | null;
  verification_status?: string | null;
  verification_reject_reason?: string | null;
  activation_status?: string | null;
};

type KycDoc = { id: string; doc_type: string; file_url: string };

const ACTIVATION_LABEL: Record<string, { icon: string; label: string }> = {
  in_elaborazione: { icon: "🕓", label: "Ordine in elaborazione" },
  in_verifica: { icon: "🕓", label: "In revisione" },
  attivo: { icon: "✅", label: "Attivo" },
  bloccato: { icon: "⚠️", label: "Bloccato" },
  scaduto: { icon: "⚠️", label: "Scaduto" },
};

function StatusInline({ status }: { status: Status }) {
  if (!status) return null;
  return (
    <span style={{ marginLeft: 12, fontWeight: 600, fontSize: "0.9rem", color: status.type === "ok" ? "var(--success)" : "var(--accent)" }}>
      {status.type === "ok" ? "✓ " : "⚠ "}{status.text}
    </span>
  );
}

function formatNumber(n: string): string {
  // 390291234567 -> +39 02 9123 4567 circa, solo per leggibilita'
  return n.startsWith("39") ? `+${n.slice(0, 2)} ${n.slice(2)}` : n;
}

export default function PhoneNumberWizard() {
  const [loading, setLoading] = useState(true);
  const [didwwStatus, setDidwwStatus] = useState<DidwwStatus>({ exists: false });

  const [searching, setSearching] = useState(false);
  const [searchResult, setSearchResult] = useState<{ match_level: string; match_label: string | null; numbers: AvailableNumber[] } | null>(null);
  const [searchStatus, setSearchStatus] = useState<Status>(null);
  const [reservingId, setReservingId] = useState<string | null>(null);

  const [identity, setIdentity] = useState({ first_name: "", last_name: "", contact_email: "", phone_number: "", company_name: "" });
  const [savingIdentity, setSavingIdentity] = useState(false);
  const [identityStatus, setIdentityStatus] = useState<Status>(null);

  const [postalCode, setPostalCode] = useState("");
  const [savingAddress, setSavingAddress] = useState(false);
  const [addressStatus, setAddressStatus] = useState<Status>(null);

  const [kycDocs, setKycDocs] = useState<KycDoc[]>([]);
  const [attachingDocId, setAttachingDocId] = useState<string | null>(null);
  const [docsStatus, setDocsStatus] = useState<Status>(null);

  const [ordering, setOrdering] = useState(false);
  const [orderStatus, setOrderStatus] = useState<Status>(null);

  const [startingVerify, setStartingVerify] = useState(false);
  const [verifyStatus, setVerifyStatus] = useState<Status>(null);
  const [refreshingStatus, setRefreshingStatus] = useState(false);

  function loadStatus() {
    return api.get("/api/onboarding/didww/status").then(setDidwwStatus).catch(() => {});
  }

  useEffect(() => {
    loadStatus().finally(() => setLoading(false));
  }, []);

  async function runSearch() {
    setSearching(true);
    setSearchStatus(null);
    try {
      const result = await api.get("/api/onboarding/didww/search");
      setSearchResult(result);
      if (result.numbers.length === 0) {
        setSearchStatus({ type: "error", text: "Al momento non ci sono numeri disponibili nella tua zona. Riprova più tardi o contattaci." });
      }
    } catch (err) {
      setSearchStatus({ type: "error", text: err instanceof Error ? err.message : "Errore ricerca" });
    } finally {
      setSearching(false);
    }
  }

  async function reserve(n: AvailableNumber) {
    setReservingId(n.available_did_id);
    setSearchStatus(null);
    try {
      await api.post("/api/onboarding/didww/reserve", { available_did_id: n.available_did_id, sku_id: n.sku_id, number: n.number });
      await loadStatus();
    } catch (err) {
      setSearchStatus({ type: "error", text: err instanceof Error ? err.message : "Errore prenotazione" });
    } finally {
      setReservingId(null);
    }
  }

  async function saveIdentity(e: React.FormEvent) {
    e.preventDefault();
    setSavingIdentity(true);
    setIdentityStatus(null);
    try {
      await api.post("/api/onboarding/didww/identity", { identity_type: "business", ...identity });
      setIdentityStatus({ type: "ok", text: "Salvato" });
      await loadStatus();
    } catch (err) {
      setIdentityStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSavingIdentity(false);
    }
  }

  async function saveAddress(e: React.FormEvent) {
    e.preventDefault();
    setSavingAddress(true);
    setAddressStatus(null);
    try {
      await api.post("/api/onboarding/didww/address", { postal_code: postalCode });
      setAddressStatus({ type: "ok", text: "Salvato" });
      await loadStatus();
    } catch (err) {
      setAddressStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSavingAddress(false);
    }
  }

  useEffect(() => {
    if (didwwStatus.address_id && !didwwStatus.order_id && kycDocs.length === 0) {
      api.get("/api/onboarding/kyc-documents").then(setKycDocs).catch(() => {});
    }
  }, [didwwStatus.address_id, didwwStatus.order_id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function attachDoc(doc: KycDoc) {
    setAttachingDocId(doc.id);
    setDocsStatus(null);
    try {
      await api.post("/api/onboarding/didww/upload-document", { kyc_document_id: doc.id });
      setDocsStatus({ type: "ok", text: `"${doc.doc_type}" collegato` });
      await loadStatus();
    } catch (err) {
      setDocsStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setAttachingDocId(null);
    }
  }

  async function placeOrder() {
    setOrdering(true);
    setOrderStatus(null);
    try {
      await api.post("/api/onboarding/didww/order");
      await loadStatus();
    } catch (err) {
      setOrderStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setOrdering(false);
    }
  }

  async function startVerify() {
    setStartingVerify(true);
    setVerifyStatus(null);
    try {
      await api.post("/api/onboarding/didww/verify");
      await loadStatus();
    } catch (err) {
      setVerifyStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setStartingVerify(false);
    }
  }

  async function refreshStatus() {
    setRefreshingStatus(true);
    await loadStatus();
    setRefreshingStatus(false);
  }

  if (loading) return <p className="muted">Caricamento...</p>;

  // Ordine gia' piazzato: unico pannello di stato, guidato da activation_status
  // (calcolato lato server controllando davvero il numero su DIDWW, non solo
  // l'ordine) - qui si vede se e' ancora in revisione o gia' attivo.
  if (didwwStatus.order_id) {
    const rejected = didwwStatus.verification_status === "rejected";
    const info = didwwStatus.activation_status ? ACTIVATION_LABEL[didwwStatus.activation_status] : null;

    if (didwwStatus.activation_status === "attivo") {
      return (
        <div>
          <p>✅ Numero attivo: <strong>{formatNumber(didwwStatus.phone_number || "")}</strong></p>
          <p className="muted">È collegato alla tua pizzeria e pronto per ricevere chiamate.</p>
        </div>
      );
    }

    if (rejected) {
      return (
        <div>
          <p>⚠️ Verifica respinta per {formatNumber(didwwStatus.phone_number || "")}</p>
          {didwwStatus.verification_reject_reason && <p className="error">Motivo: {didwwStatus.verification_reject_reason}</p>}
          <p className="muted">Controlla che i documenti caricati corrispondano esattamente all&apos;intestatario (documento personale, o visura camerale per un&apos;attività) e all&apos;indirizzo inserito, poi contattaci per riprovare.</p>
        </div>
      );
    }

    if (!didwwStatus.verification_id) {
      return (
        <div>
          <p className="muted">Numero {formatNumber(didwwStatus.phone_number || "")} ordinato. Avvia la verifica dei documenti per attivarlo.</p>
          <button onClick={startVerify} disabled={startingVerify}>{startingVerify ? "Avvio..." : "Avvia verifica"}</button>
          <StatusInline status={verifyStatus} />
        </div>
      );
    }

    return (
      <div>
        <p>{info?.icon || "🕓"} {info?.label || "In revisione"}: <strong>{formatNumber(didwwStatus.phone_number || "")}</strong></p>
        <p className="muted">
          DIDWW deve verificare che il documento e la prova di indirizzo corrispondano all&apos;intestatario prima di attivare il numero:
          di solito entro 48 ore. Non serve fare nulla, ti avviseremo — oppure controlla di nuovo qui.
        </p>
        <button className="secondary" onClick={refreshStatus} disabled={refreshingStatus}>{refreshingStatus ? "..." : "Aggiorna stato"}</button>
      </div>
    );
  }

  if (didwwStatus.address_id) {
    return (
      <div>
        <p className="muted">Collega almeno un documento già caricato, poi ordina il numero ({didwwStatus.documents_uploaded || 0} collegati finora).</p>
        {kycDocs.length === 0 && <p className="muted">Nessun documento caricato ancora — carica un documento nella sezione &quot;Documenti (KYC)&quot; qui sotto, poi torna qui.</p>}
        {kycDocs.map((d) => (
          <div key={d.id} className="order-card">
            <span>{d.doc_type}</span>
            <button className="secondary" disabled={attachingDocId === d.id} onClick={() => attachDoc(d)}>
              {attachingDocId === d.id ? "..." : "Collega"}
            </button>
          </div>
        ))}
        <StatusInline status={docsStatus} />
        <div style={{ marginTop: 12 }}>
          <button onClick={placeOrder} disabled={ordering || (didwwStatus.documents_uploaded || 0) === 0}>
            {ordering ? "Invio ordine..." : "Ordina il numero"}
          </button>
          <StatusInline status={orderStatus} />
        </div>
      </div>
    );
  }

  if (didwwStatus.identity_id) {
    return (
      <form onSubmit={saveAddress}>
        <p className="muted">Uso l&apos;indirizzo inserito sopra in &quot;Dati attività&quot; — serve solo il CAP.</p>
        <label>CAP</label>
        <input value={postalCode} onChange={(e) => setPostalCode(e.target.value)} required style={{ maxWidth: 160 }} />
        <div style={{ display: "flex", alignItems: "center", marginTop: 12 }}>
          <button type="submit" disabled={savingAddress}>{savingAddress ? "Salvataggio..." : "Continua"}</button>
          <StatusInline status={addressStatus} />
        </div>
      </form>
    );
  }

  if (didwwStatus.available_did_id) {
    return (
      <form onSubmit={saveIdentity}>
        <p className="muted">Dati per l&apos;attivazione regolatoria del numero {formatNumber(didwwStatus.phone_number || "")} (richiesti da DIDWW).</p>
        <div style={{ display: "flex", gap: 12 }}>
          <div style={{ flex: 1 }}>
            <label>Nome</label>
            <input value={identity.first_name} onChange={(e) => setIdentity({ ...identity, first_name: e.target.value })} required />
          </div>
          <div style={{ flex: 1 }}>
            <label>Cognome</label>
            <input value={identity.last_name} onChange={(e) => setIdentity({ ...identity, last_name: e.target.value })} required />
          </div>
        </div>
        <label>Email di contatto</label>
        <input type="email" value={identity.contact_email} onChange={(e) => setIdentity({ ...identity, contact_email: e.target.value })} required />
        <label>Telefono di contatto</label>
        <input value={identity.phone_number} onChange={(e) => setIdentity({ ...identity, phone_number: e.target.value })} required />
        <label>Ragione sociale</label>
        <input value={identity.company_name} onChange={(e) => setIdentity({ ...identity, company_name: e.target.value })} required />
        <div style={{ display: "flex", alignItems: "center", marginTop: 12 }}>
          <button type="submit" disabled={savingIdentity}>{savingIdentity ? "Salvataggio..." : "Continua"}</button>
          <StatusInline status={identityStatus} />
        </div>
      </form>
    );
  }

  return (
    <div>
      <p className="muted">Cerca un numero fisso italiano nella tua zona da collegare all&apos;agente AI — 1 numero è incluso nel tuo piano. Ti mostriamo solo numeri della tua città o provincia, mai di zone lontane dal tuo indirizzo.</p>
      <button onClick={runSearch} disabled={searching}>{searching ? "Ricerca..." : "Cerca numeri disponibili"}</button>
      <StatusInline status={searchStatus} />

      {searchResult && searchResult.numbers.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <p className="muted" style={{ fontSize: "0.85rem" }}>
            {searchResult.match_level === "citta" && `Numeri trovati a ${searchResult.match_label}.`}
            {searchResult.match_level === "provincia" && `Nessun numero esatto per la tua città — ecco quelli del capoluogo di provincia, ${searchResult.match_label}.`}
            {searchResult.match_level === "regione" && `Nessun numero in provincia — ecco quelli disponibili in ${searchResult.match_label}.`}
          </p>
          {searchResult.numbers.map((n) => (
            <div key={n.available_did_id} className="order-card">
              <span>📞 {formatNumber(n.number)} — {n.city_name}</span>
              <button disabled={reservingId === n.available_did_id} onClick={() => reserve(n)}>
                {reservingId === n.available_did_id ? "Prenotazione..." : "Scegli"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
