"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, API_URL } from "@/lib/api";

type KycDoc = { id: string; doc_type: string; file_url: string; review_status: string; notes: string | null };
type TenantDetail = {
  id: string; business_name: string; category: string; status: string; city: string | null;
  kyc_documents: KycDoc[]; phone_number: string | null; whatsapp_connected: boolean;
};

export default function AdminTenantDetail() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [tenant, setTenant] = useState<TenantDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [phoneNumber, setPhoneNumber] = useState("");
  const [didwwRef, setDidwwRef] = useState("");
  const [waPhoneId, setWaPhoneId] = useState("");
  const [waToken, setWaToken] = useState("");

  function reload() {
    api.get(`/api/admin/tenants/${params.id}`).then(setTenant).catch((e) => setError(e.message));
  }

  useEffect(reload, [params.id]);

  async function reviewDoc(docId: string, review_status: string) {
    await api.post(`/api/admin/tenants/${params.id}/kyc-documents/${docId}/review`, { review_status });
    reload();
  }

  async function savePhoneNumber(e: React.FormEvent) {
    e.preventDefault();
    await api.post(`/api/admin/tenants/${params.id}/phone-number`, { e164_number: phoneNumber, didww_reference: didwwRef || null });
    reload();
  }

  async function saveWhatsapp(e: React.FormEvent) {
    e.preventDefault();
    await api.post(`/api/admin/tenants/${params.id}/whatsapp-channel`, { phone_number_id: waPhoneId, access_token: waToken });
    await api.post(`/api/admin/tenants/${params.id}/whatsapp-channel/verify`);
    reload();
  }

  async function approve() {
    setError(null);
    try {
      await api.post(`/api/admin/tenants/${params.id}/approve`);
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore");
    }
  }

  async function reject() {
    await api.post(`/api/admin/tenants/${params.id}/reject`);
    router.push("/admin/tenants");
  }

  if (!tenant) {
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
    <div style={{ maxWidth: 700 }}>
      <a href="/admin/tenants">&larr; Torna alla lista</a>
      <h1>{tenant.business_name}</h1>
      <p className="muted">{tenant.category} — {tenant.city} — stato: <strong>{tenant.status}</strong></p>
      {error && <div className="error">{error}</div>}

      <div className="card">
        <h2>Documenti KYC</h2>
        {tenant.kyc_documents.length === 0 && <p className="muted">Nessun documento caricato.</p>}
        {tenant.kyc_documents.map((d) => (
          <div key={d.id} className="order-card">
            <div>
              <a href={`${API_URL}${d.file_url}`} target="_blank" rel="noreferrer">{d.doc_type}</a>
              <div className="muted">stato: {d.review_status}</div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={() => reviewDoc(d.id, "approved")}>Approva</button>
              <button className="secondary" onClick={() => reviewDoc(d.id, "rejected")}>Rifiuta</button>
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>Numero di telefono (DIDWW)</h2>
        <p className="muted">Ordina il numero dal portale DIDWW usando i documenti sopra, poi inseriscilo qui.</p>
        {tenant.phone_number ? <p><strong>{tenant.phone_number}</strong></p> : (
          <form onSubmit={savePhoneNumber} style={{ display: "flex", gap: 8 }}>
            <input placeholder="+39..." value={phoneNumber} onChange={(e) => setPhoneNumber(e.target.value)} required />
            <input placeholder="Riferimento DIDWW (opzionale)" value={didwwRef} onChange={(e) => setDidwwRef(e.target.value)} />
            <button type="submit">Salva</button>
          </form>
        )}
      </div>

      <div className="card">
        <h2>Canale WhatsApp</h2>
        {tenant.whatsapp_connected ? <p>Collegato ✓</p> : (
          <form onSubmit={saveWhatsapp}>
            <label>Phone Number ID (Meta)</label>
            <input value={waPhoneId} onChange={(e) => setWaPhoneId(e.target.value)} required />
            <label>Access Token</label>
            <input value={waToken} onChange={(e) => setWaToken(e.target.value)} required />
            <button type="submit" style={{ marginTop: 16 }}>Collega</button>
          </form>
        )}
      </div>

      <div className="card">
        <h2>Decisione</h2>
        <div style={{ display: "flex", gap: 12 }}>
          <button onClick={approve}>Approva e attiva</button>
          <button className="secondary" onClick={reject}>Rifiuta</button>
        </div>
      </div>
    </div>
  );
}
