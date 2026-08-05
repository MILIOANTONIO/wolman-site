"use client";
import { useEffect, useRef, useState } from "react";
import { api, fetchAudioBlobUrl } from "@/lib/api";

type Voice = { voice_id: string; name: string; preview_url: string | null };
type Status = { type: "ok" | "error"; text: string } | null;

function StatusInline({ status }: { status: Status }) {
  if (!status) return null;
  return (
    <span style={{ marginLeft: 12, fontWeight: 600, fontSize: "0.9rem", color: status.type === "ok" ? "var(--success)" : "var(--accent)" }}>
      {status.type === "ok" ? "✓ " : "⚠ "}{status.text}
    </span>
  );
}

export default function AgentePage() {
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [personaName, setPersonaName] = useState("Assistente");
  const [tone, setTone] = useState("amichevole");
  const [confirmCallEnabled, setConfirmCallEnabled] = useState(false);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [voiceId, setVoiceId] = useState("");
  const [voicePickerOpen, setVoicePickerOpen] = useState(false);
  const [playingVoiceId, setPlayingVoiceId] = useState<string | null>(null);
  const [loadingVoiceId, setLoadingVoiceId] = useState<string | null>(null);
  const [savingAgent, setSavingAgent] = useState(false);
  const [agentStatus, setAgentStatus] = useState<Status>(null);
  const previewAudioRef = useRef<HTMLAudioElement | null>(null);
  const previewCacheRef = useRef<Record<string, string>>({});

  const [promptChannel, setPromptChannel] = useState<"voice" | "whatsapp">("voice");
  const [prompt, setPrompt] = useState<string>("");
  const [isCustomPrompt, setIsCustomPrompt] = useState(false);
  const [loadingPrompt, setLoadingPrompt] = useState(false);
  const [savingPrompt, setSavingPrompt] = useState(false);
  const [promptStatus, setPromptStatus] = useState<Status>(null);
  const [agentId, setAgentId] = useState<string | null>(null);

  function loadAgent() {
    setLoading(true);
    setLoadError(null);
    api.get("/api/onboarding/voices").then(setVoices).catch(() => setVoices([]));
    api.get("/api/onboarding/tenant").then((t) => {
      setPersonaName(t.agent_persona_name);
      setTone(t.agent_tone);
      setVoiceId(t.agent_voice_id || "");
      setConfirmCallEnabled(t.confirm_call_enabled);
    }).catch((e) => setLoadError(e.message)).finally(() => setLoading(false));
  }

  useEffect(loadAgent, []);

  function loadPrompt(channel: "voice" | "whatsapp") {
    setPromptChannel(channel);
    setLoadingPrompt(true);
    setPromptStatus(null);
    api.get(`/api/dashboard/agent-prompt?channel=${channel}`)
      .then((r) => { setPrompt(r.prompt); setIsCustomPrompt(r.is_custom); setAgentId(r.elevenlabs_agent_id); })
      .catch((e) => setPromptStatus({ type: "error", text: e.message }))
      .finally(() => setLoadingPrompt(false));
  }

  useEffect(() => { loadPrompt("voice"); }, []);

  async function savePrompt() {
    setSavingPrompt(true);
    setPromptStatus(null);
    try {
      const result = await api.put("/api/dashboard/agent-prompt", { channel: promptChannel, prompt });
      setIsCustomPrompt(true);
      setPromptStatus({
        type: "ok",
        text: result.pushed_to_elevenlabs ? "Salvato e agente ElevenLabs aggiornato" : "Salvato (l'agente verrà creato/aggiornato all'attivazione)",
      });
    } catch (err) {
      setPromptStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSavingPrompt(false);
    }
  }

  async function resetPrompt() {
    setSavingPrompt(true);
    setPromptStatus(null);
    try {
      const data = await api.post(`/api/dashboard/agent-prompt/reset?channel=${promptChannel}`);
      setPrompt(data.prompt);
      setIsCustomPrompt(false);
      setPromptStatus({ type: "ok", text: "Tornato al prompt generato automaticamente" });
    } catch (err) {
      setPromptStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSavingPrompt(false);
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
        url = await fetchAudioBlobUrl(`/api/onboarding/voices/${voice.voice_id}/preview`);
        previewCacheRef.current[voice.voice_id] = url;
      }
      audio.src = url;
      await audio.play();
      setPlayingVoiceId(voice.voice_id);
    } catch (err) {
      setAgentStatus({ type: "error", text: err instanceof Error ? err.message : "Errore anteprima" });
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
        business_hours: {}, reservation_slot_minutes: 30,
        agent_persona_name: personaName, agent_tone: tone,
        agent_voice_id: voiceId || null, agent_voice_name: voice?.name || null,
        confirm_call_enabled: confirmCallEnabled,
      });
      setAgentStatus({ type: "ok", text: "Salvato" });
      loadPrompt(promptChannel);
    } catch (err) {
      setAgentStatus({ type: "error", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setSavingAgent(false);
    }
  }

  if (loading || loadError) {
    return (
      <div>
        {loadError ? (
          <div className="error">
            {loadError}
            <div style={{ marginTop: 12 }}>
              <button onClick={loadAgent}>Riprova</button>
            </div>
          </div>
        ) : (
          "Caricamento..."
        )}
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 800 }}>
      <h1>Agente AI</h1>
      <p className="muted">
        {agentId ? <>Agente attivo (id ElevenLabs: <code>{agentId}</code>)</> : "L'agente ElevenLabs verrà creato quando un admin approva la tua pizzeria."}
      </p>

      <div className="card">
        <h2>Personalità</h2>
        <form onSubmit={saveSettings}>
          <label>Nome dell&apos;agente</label>
          <input value={personaName} onChange={(e) => setPersonaName(e.target.value)} />
          <label>Tono</label>
          <select value={tone} onChange={(e) => setTone(e.target.value)}>
            <option value="amichevole">Amichevole</option>
            <option value="professionale">Professionale</option>
            <option value="brillante">Brillante</option>
          </select>

          <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 16 }}>
            <input type="checkbox" style={{ width: "auto" }} checked={confirmCallEnabled} onChange={(e) => setConfirmCallEnabled(e.target.checked)} />
            Richiama il cliente per confermare l&apos;ordine (funzione in preparazione, non ancora attiva)
          </label>

          <label style={{ marginTop: 16 }}>Voce</label>
          <audio ref={previewAudioRef} onEnded={() => setPlayingVoiceId(null)} style={{ display: "none" }} />

          {(() => {
            const current = voices.find((v) => v.voice_id === voiceId);
            return (
              <div style={{ display: "flex", alignItems: "center", gap: 10, border: "1px solid var(--border)", borderRadius: 8, padding: "8px 12px" }}>
                {current && (
                  <button type="button" className="secondary" onClick={(e) => { e.preventDefault(); togglePreview(current); }} disabled={loadingVoiceId === current.voice_id} style={{ padding: "4px 10px", flexShrink: 0 }}>
                    {loadingVoiceId === current.voice_id ? "…" : playingVoiceId === current.voice_id ? "⏸" : "▶"}
                  </button>
                )}
                <span style={{ fontSize: "0.95rem", flex: 1 }}>{current ? current.name : "Nessuna voce selezionata"}</span>
                <button type="button" className="secondary" onClick={(e) => { e.preventDefault(); setVoicePickerOpen((o) => !o); }} style={{ padding: "4px 10px", flexShrink: 0 }}>
                  {voicePickerOpen ? "Chiudi" : "Cambia voce"}
                </button>
              </div>
            );
          })()}

          {voicePickerOpen && (
            <div style={{ maxHeight: 280, overflowY: "auto", border: "1px solid var(--border)", borderTop: "none", borderRadius: "0 0 8px 8px" }}>
              {voices.map((v) => (
                <label key={v.voice_id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 12px", borderBottom: "1px solid var(--border)", cursor: "pointer", margin: 0, background: voiceId === v.voice_id ? "var(--bg)" : "transparent" }}>
                  <input type="radio" name="agent_voice" checked={voiceId === v.voice_id} onChange={() => setVoiceId(v.voice_id)} />
                  <button type="button" className="secondary" onClick={(e) => { e.preventDefault(); togglePreview(v); }} disabled={loadingVoiceId === v.voice_id} style={{ padding: "4px 10px", flexShrink: 0 }}>
                    {loadingVoiceId === v.voice_id ? "…" : playingVoiceId === v.voice_id ? "⏸" : "▶"}
                  </button>
                  <span style={{ fontSize: "0.95rem" }}>{v.name}</span>
                </label>
              ))}
            </div>
          )}
          <div style={{ display: "flex", alignItems: "center", marginTop: 16 }}>
            <button type="submit" disabled={savingAgent}>{savingAgent ? "Salvataggio..." : "Salva"}</button>
            <StatusInline status={agentStatus} />
          </div>
        </form>
      </div>

      <div className="card">
        <h2>Prompt di risposta</h2>
        <p className="muted">
          Questo è il testo esatto dato all&apos;AI per rispondere ai clienti — per impostazione predefinita si
          genera da solo da menu, orari e impostazioni sopra. Puoi modificarlo a mano qui sotto: voce e WhatsApp
          hanno un prompt separato, perché il canale voce parla ad alta voce mentre WhatsApp scrive messaggi di testo.
        </p>
        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <button className={promptChannel === "voice" ? "" : "secondary"} onClick={() => loadPrompt("voice")}>Canale voce</button>
          <button className={promptChannel === "whatsapp" ? "" : "secondary"} onClick={() => loadPrompt("whatsapp")}>Canale WhatsApp</button>
        </div>

        {loadingPrompt ? (
          <p className="muted">Caricamento...</p>
        ) : (
          <>
            <p className="muted" style={{ marginBottom: 8 }}>
              {isCustomPrompt ? "✏️ Personalizzato manualmente" : "🔄 Generato automaticamente da menu/orari/impostazioni"}
            </p>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={16}
              style={{ fontFamily: "monospace", fontSize: "0.85rem", resize: "vertical" }}
            />
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
              <button disabled={savingPrompt} onClick={savePrompt}>{savingPrompt ? "Salvataggio..." : "Salva prompt"}</button>
              <button className="secondary" disabled={savingPrompt} onClick={resetPrompt}>Rigenera automaticamente</button>
              <StatusInline status={promptStatus} />
            </div>
            {promptChannel === "voice" && (
              <p className="muted" style={{ marginTop: 8 }}>
                {agentId ? "Il salvataggio aggiorna subito l'agente ElevenLabs attivo." : "L'agente ElevenLabs non è ancora attivo: il prompt verrà usato quando un admin approva la tua pizzeria."}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
