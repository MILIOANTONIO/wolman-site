"use client";
import { useEffect, useState } from "react";
import { api, API_URL, uploadFile, uploadFiles } from "@/lib/api";
import { CameraButton } from "@/lib/CameraCapture";

type Offering = { id: string; name: string; description: string | null; price_cents: number; unit: string | null; group_name: string | null; ingredients: string | null; is_available: boolean; image_url: string | null; is_featured: boolean };
type Status = { type: "ok" | "error"; text: string } | null;

const PAGE_SIZE = 10;

function StatusInline({ status }: { status: Status }) {
  if (!status) return null;
  return (
    <span style={{ marginLeft: 12, fontWeight: 600, fontSize: "0.9rem", color: status.type === "ok" ? "var(--success)" : "var(--accent)" }}>
      {status.type === "ok" ? "✓ " : "⚠ "}{status.text}
    </span>
  );
}

export default function MenuPage() {
  const [offerings, setOfferings] = useState<Offering[]>([]);
  const [newItem, setNewItem] = useState({ name: "", price: "", group_name: "", ingredients: "" });
  const [importing, setImporting] = useState(false);
  const [status, setStatus] = useState<Status>(null);
  const [page, setPage] = useState(1);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState({ name: "", price: "", group_name: "", ingredients: "" });
  const [savingEdit, setSavingEdit] = useState(false);

  function reload() {
    api.get("/api/onboarding/offerings").then(setOfferings).catch(() => {});
  }

  useEffect(reload, []);

  async function addOffering(e: React.FormEvent) {
    e.preventDefault();
    setStatus(null);
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
      setStatus({ type: "ok", text: `"${created.name}" aggiunta` });
    } catch (err) {
      setStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    }
  }

  function startEdit(o: Offering) {
    setEditingId(o.id);
    setEditDraft({
      name: o.name,
      price: (o.price_cents / 100).toFixed(2).replace(".", ","),
      group_name: o.group_name || "",
      ingredients: o.ingredients || "",
    });
  }

  function cancelEdit() {
    setEditingId(null);
  }

  async function saveEdit(o: Offering) {
    setSavingEdit(true);
    setStatus(null);
    try {
      const updated = await api.put(`/api/onboarding/offerings/${o.id}`, {
        ...o,
        name: editDraft.name,
        price_cents: Math.round(parseFloat(editDraft.price.replace(",", ".")) * 100),
        group_name: editDraft.group_name || null,
        ingredients: editDraft.ingredients || null,
      });
      setOfferings(offerings.map((x) => (x.id === o.id ? updated : x)));
      setEditingId(null);
      setStatus({ type: "ok", text: `"${updated.name}" aggiornata` });
    } catch (err) {
      setStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSavingEdit(false);
    }
  }

  async function toggleAvailable(o: Offering) {
    const updated = await api.put(`/api/onboarding/offerings/${o.id}`, { ...o, is_available: !o.is_available });
    setOfferings(offerings.map((x) => (x.id === o.id ? updated : x)));
  }

  async function toggleFeatured(o: Offering) {
    const updated = await api.put(`/api/onboarding/offerings/${o.id}`, { ...o, is_featured: !o.is_featured });
    setOfferings(offerings.map((x) => (x.id === o.id ? updated : x)));
  }

  async function removeOffering(id: string, name: string) {
    await api.delete(`/api/onboarding/offerings/${id}`);
    setOfferings(offerings.filter((o) => o.id !== id));
    setStatus({ type: "ok", text: `"${name}" rimossa` });
  }

  async function uploadOfferingImage(o: Offering, file: File) {
    setStatus(null);
    try {
      const res = await uploadFile(`/api/onboarding/offerings/${o.id}/image`, file);
      setOfferings(offerings.map((x) => (x.id === o.id ? { ...x, image_url: res.image_url } : x)));
      setStatus({ type: "ok", text: `Foto di "${o.name}" aggiornata` });
    } catch (err) {
      setStatus({ type: "error", text: err instanceof Error ? err.message : "Errore caricamento foto" });
    }
  }

  async function removeOfferingImage(o: Offering) {
    await api.delete(`/api/onboarding/offerings/${o.id}/image`);
    setOfferings(offerings.map((x) => (x.id === o.id ? { ...x, image_url: null } : x)));
  }

  async function importFiles(files: File[]) {
    if (files.length === 0) return;
    setImporting(true);
    setStatus(null);
    try {
      const result = await uploadFiles("/api/onboarding/offerings/import", files);
      setOfferings([...offerings, ...result.items]);
      setStatus({ type: "ok", text: `Importate ${result.imported} voci — controllale nella tabella "Menu attivo" qui sotto` });
      setPage(1);
    } catch (err) {
      setStatus({ type: "error", text: err instanceof Error ? err.message : "Errore importazione" });
    } finally {
      setImporting(false);
    }
  }

  async function importMenu(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files ? Array.from(e.target.files) : [];
    await importFiles(files);
    e.target.value = "";
  }

  const totalPages = Math.max(1, Math.ceil(offerings.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageItems = offerings.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  return (
    <div style={{ maxWidth: 900 }}>
      <h1>Menu</h1>
      <p className="muted">{offerings.length} voci nel menu.</p>

      <div className="card">
        <h2>Nuovo menu da caricare</h2>
        <p className="muted">Importa da file o foto (puoi selezionare più file insieme, es. più pagine o foto), oppure aggiungi una voce a mano.</p>

        <div style={{ border: "1px dashed var(--border)", borderRadius: 8, padding: 12, marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <input type="file" multiple accept=".txt,.pdf,.doc,.docx,.jpg,.jpeg,.png,.webp" onChange={importMenu} disabled={importing} style={{ width: "auto" }} />
            <CameraButton onCapture={(file) => importFiles([file])} label="📷 Scatta foto del menu" />
          </div>
          {importing && <p className="muted">Sto leggendo il menu, può volerci un momento se è lungo...</p>}
          <StatusInline status={status} />
        </div>

        <form onSubmit={addOffering} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input placeholder="Nome piatto" value={newItem.name} onChange={(e) => setNewItem({ ...newItem, name: e.target.value })} required style={{ flex: "2 1 160px", minWidth: 160 }} />
          <input placeholder="Categoria" value={newItem.group_name} onChange={(e) => setNewItem({ ...newItem, group_name: e.target.value })} style={{ flex: "1 1 140px", minWidth: 140 }} />
          <input placeholder="Ingredienti" value={newItem.ingredients} onChange={(e) => setNewItem({ ...newItem, ingredients: e.target.value })} style={{ flex: "2 1 180px", minWidth: 180 }} />
          <input placeholder="Prezzo €" value={newItem.price} onChange={(e) => setNewItem({ ...newItem, price: e.target.value })} required style={{ flex: "0 1 100px", minWidth: 90 }} />
          <button type="submit">Aggiungi</button>
        </form>
      </div>

      <div className="card">
        <h2>Menu attivo</h2>
        {offerings.length === 0 && <p className="muted">Nessuna voce ancora — caricane uno sopra.</p>}
        {offerings.length > 0 && (
          <>
            <div style={{ overflowX: "auto" }}>
              <table className="responsive-table">
                <thead>
                  <tr>
                    <th>Foto</th>
                    <th>Nome</th>
                    <th>Categoria</th>
                    <th>Ingredienti</th>
                    <th>Prezzo</th>
                    <th>Stato</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {pageItems.map((o) =>
                    editingId === o.id ? (
                      <tr key={o.id}>
                        <td data-label="Foto">
                          {o.image_url ? <img src={`${API_URL}${o.image_url}`} alt="" style={{ width: 44, height: 44, objectFit: "cover", borderRadius: 6 }} /> : "—"}
                        </td>
                        <td data-label="Nome"><input value={editDraft.name} onChange={(e) => setEditDraft({ ...editDraft, name: e.target.value })} style={{ minWidth: 120 }} /></td>
                        <td data-label="Categoria"><input value={editDraft.group_name} onChange={(e) => setEditDraft({ ...editDraft, group_name: e.target.value })} style={{ minWidth: 100 }} /></td>
                        <td data-label="Ingredienti"><input value={editDraft.ingredients} onChange={(e) => setEditDraft({ ...editDraft, ingredients: e.target.value })} style={{ minWidth: 140 }} /></td>
                        <td data-label="Prezzo"><input value={editDraft.price} onChange={(e) => setEditDraft({ ...editDraft, price: e.target.value })} style={{ width: 70 }} /></td>
                        <td data-label="" colSpan={2}>
                          <div style={{ display: "flex", gap: 6 }}>
                            <button style={{ padding: "4px 10px", fontSize: "0.8rem" }} disabled={savingEdit} onClick={() => saveEdit(o)}>{savingEdit ? "..." : "Salva"}</button>
                            <button className="secondary" style={{ padding: "4px 10px", fontSize: "0.8rem" }} onClick={cancelEdit}>Annulla</button>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      <tr key={o.id} style={{ opacity: o.is_available ? 1 : 0.5 }}>
                        <td data-label="Foto">
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            {o.image_url && <img src={`${API_URL}${o.image_url}`} alt="" style={{ width: 44, height: 44, objectFit: "cover", borderRadius: 6 }} />}
                            <input
                              type="file" accept=".jpg,.jpeg,.png,.webp" id={`offering-img-${o.id}`} style={{ display: "none" }}
                              onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadOfferingImage(o, f); e.target.value = ""; }}
                            />
                            <label htmlFor={`offering-img-${o.id}`} className="secondary" style={{ padding: "4px 8px", fontSize: "0.75rem", cursor: "pointer" }}>
                              {o.image_url ? "Cambia" : "Aggiungi"}
                            </label>
                            {o.image_url && (
                              <button className="secondary" style={{ padding: "4px 8px", fontSize: "0.75rem" }} onClick={() => removeOfferingImage(o)}>✕</button>
                            )}
                          </div>
                        </td>
                        <td data-label="Nome"><strong>{o.name}</strong></td>
                        <td data-label="Categoria" className="muted">{o.group_name || "—"}</td>
                        <td data-label="Ingredienti" className="muted">{o.ingredients || "—"}</td>
                        <td data-label="Prezzo">{(o.price_cents / 100).toFixed(2)} €</td>
                        <td data-label="">
                          <div style={{ display: "flex", gap: 6 }}>
                            <button className="secondary" style={{ padding: "4px 10px", fontSize: "0.8rem" }} onClick={() => startEdit(o)}>Modifica</button>
                            <button className="secondary" style={{ padding: "4px 10px", fontSize: "0.8rem" }} onClick={() => toggleAvailable(o)}>
                              {o.is_available ? "Nascondi" : "Mostra"}
                            </button>
                            <button
                              className="secondary" title="Mostra in vetrina nella pagina pubblica" onClick={() => toggleFeatured(o)}
                              style={{ padding: "4px 10px", fontSize: "0.8rem", color: o.is_featured ? "var(--accent)" : undefined }}
                            >
                              {o.is_featured ? "★ In evidenza" : "☆ In evidenza"}
                            </button>
                          </div>
                        </td>
                        <td data-label="">
                          <button className="secondary" style={{ padding: "4px 10px", fontSize: "0.8rem" }} onClick={() => removeOffering(o.id, o.name)}>
                            Rimuovi
                          </button>
                        </td>
                      </tr>
                    )
                  )}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 16, justifyContent: "center" }}>
                <button className="secondary" disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>← Precedente</button>
                <span className="muted">Pagina {currentPage} di {totalPages}</span>
                <button className="secondary" disabled={currentPage === totalPages} onClick={() => setPage(currentPage + 1)}>Successiva →</button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
