"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, API_URL } from "@/lib/api";

export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === "signup") {
        await api.post("/api/auth/signup", { email, password, business_name: businessName });
      } else {
        await api.post("/api/auth/login", { email, password });
      }
      router.push("/dashboard/configurazione");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page" style={{ maxWidth: 420 }}>
      <div className="card">
        <h1>Pizza SaaS</h1>
        <p className="muted">{mode === "login" ? "Accedi al tuo account" : "Crea il tuo account"}</p>

        <a href={`${API_URL}/api/auth/google/login?role=owner`}>
          <button type="button" style={{ width: "100%", marginTop: 16, background: "#4285F4" }}>
            Accedi con Google
          </button>
        </a>

        <div className="muted" style={{ textAlign: "center", margin: "16px 0" }}>oppure</div>

        <form onSubmit={submit}>
          {mode === "signup" && (
            <>
              <label>Nome attività</label>
              <input value={businessName} onChange={(e) => setBusinessName(e.target.value)} required />
            </>
          )}
          <label>Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />

          {error && <div className="error">{error}</div>}

          <button type="submit" disabled={loading} style={{ width: "100%", marginTop: 16 }}>
            {mode === "login" ? "Accedi" : "Registrati"}
          </button>
        </form>

        <button
          type="button"
          className="secondary"
          style={{ width: "100%", marginTop: 12 }}
          onClick={() => setMode(mode === "login" ? "signup" : "login")}
        >
          {mode === "login" ? "Non hai un account? Registrati" : "Hai già un account? Accedi"}
        </button>
      </div>
    </div>
  );
}
