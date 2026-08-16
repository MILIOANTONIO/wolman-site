"use client";
import { useEffect, useRef, useState } from "react";

/**
 * Pulsante "Scatta foto" che apre la fotocamera (posteriore su telefono,
 * webcam su PC) direttamente nella pagina via getUserMedia, invece di
 * affidarsi al solo attributo HTML "capture" (che su desktop spesso non
 * apre nulla di utilizzabile).
 */
export function CameraButton({ onCapture, label = "📷 Scatta foto" }: { onCapture: (file: File) => void; label?: string }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    if (open && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
      videoRef.current.play().catch(() => {});
    }
  }, [open]);

  async function openCamera() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      streamRef.current = stream;
      setOpen(true);
    } catch {
      setError("Impossibile accedere alla fotocamera: controlla i permessi del browser.");
    }
  }

  function closeCamera() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setOpen(false);
  }

  function capture() {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    canvas.toBlob(
      (blob) => {
        if (blob) onCapture(new File([blob], `foto-${Date.now()}.jpg`, { type: "image/jpeg" }));
        closeCamera();
      },
      "image/jpeg",
      0.9
    );
  }

  return (
    <>
      <button type="button" className="secondary" onClick={openCamera}>{label}</button>
      {error && <span className="error" style={{ marginLeft: 8 }}>{error}</span>}
      {open && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", zIndex: 1000, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16, padding: 16 }}>
          <video ref={videoRef} style={{ maxWidth: "92vw", maxHeight: "70vh", borderRadius: 8 }} playsInline muted />
          <div style={{ display: "flex", gap: 12 }}>
            <button onClick={capture}>Scatta</button>
            <button className="secondary" onClick={closeCamera}>Annulla</button>
          </div>
        </div>
      )}
    </>
  );
}
