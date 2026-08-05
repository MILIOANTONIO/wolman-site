"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { api, API_URL } from "@/lib/api";
import { ThemeToggle } from "@/lib/ThemeToggle";

const LINKS = [
  { href: "/admin", label: "Panoramica" },
  { href: "/admin/tenants", label: "Pizzerie" },
  { href: "/admin/didww", label: "DIDWW" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const pathname = usePathname();

  useEffect(() => {
    api.get("/api/admin/stats").then(() => setAuthed(true)).catch(() => setAuthed(false));
  }, []);

  if (authed === null) {
    return <div className="page">Verifica accesso...</div>;
  }

  if (authed === false) {
    return (
      <div className="page" style={{ maxWidth: 420 }}>
        <div className="card">
          <h1>Pannello admin</h1>
          <p className="muted">Accesso riservato.</p>
          <a href={`${API_URL}/api/auth/google/login?role=admin`}>
            <button type="button" style={{ width: "100%", background: "#4285F4" }}>Accedi con Google</button>
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <h2>Pizza SaaS Admin</h2>
        {LINKS.map((link) => (
          <Link key={link.href} href={link.href} className={pathname === link.href ? "active" : ""}>
            {link.label}
          </Link>
        ))}
        <div style={{ marginTop: 16 }}>
          <ThemeToggle />
        </div>
      </aside>
      <main className="admin-main">{children}</main>
    </div>
  );
}
