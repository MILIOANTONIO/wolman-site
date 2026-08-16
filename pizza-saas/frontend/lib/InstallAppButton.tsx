"use client";
import { useState } from "react";
import { useInstallPrompt } from "./useInstallPrompt";

export function InstallAppButton() {
  const { canInstall, promptInstall, isIOS, isStandalone } = useInstallPrompt();
  const [showIOSHint, setShowIOSHint] = useState(false);

  if (isStandalone) return null;

  if (canInstall) {
    return (
      <button type="button" className="secondary" onClick={promptInstall}>
        📲 Installa l&apos;app
      </button>
    );
  }

  if (isIOS) {
    return (
      <div>
        <button type="button" className="secondary" onClick={() => setShowIOSHint((v) => !v)}>
          📲 Installa l&apos;app
        </button>
        {showIOSHint && (
          <p className="muted" style={{ fontSize: "0.82rem", marginTop: 6 }}>
            Tocca <strong>Condividi</strong> (icona con la freccia) e poi <strong>&quot;Aggiungi a Home&quot;</strong>.
          </p>
        )}
      </div>
    );
  }

  return null;
}
