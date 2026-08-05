"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { api } from "@/lib/api";
import { useMe } from "@/lib/useMe";
import { ThemeToggle } from "@/lib/ThemeToggle";
import { usePushNotifications } from "@/lib/usePushNotifications";
import { useHeartbeat } from "@/lib/useHeartbeat";

const OWNER_LINKS = [
  { href: "/dashboard", label: "Ordini" },
  { href: "/dashboard/statistiche", label: "Statistiche" },
  { href: "/dashboard/prenotazioni", label: "Prenotazioni" },
  { href: "/dashboard/mappa", label: "Mappa consegne" },
  { href: "/dashboard/configurazione", label: "Configurazione" },
  { href: "/dashboard/menu", label: "Menu" },
  { href: "/dashboard/promozioni", label: "Promozioni" },
  { href: "/dashboard/viralizza", label: "Viralizza" },
  { href: "/dashboard/agente", label: "Agente AI" },
  { href: "/dashboard/consumi", label: "Consumi" },
];

// Sotto-account: ognuno vede solo la sua sezione - la restrizione vera è
// lato backend (require_roles), questa lista serve solo a non mostrare
// link che porterebbero comunque a un 403.
const LINKS_BY_ROLE: Record<string, { href: string; label: string }[]> = {
  owner: OWNER_LINKS,
  cuoco: [{ href: "/dashboard", label: "Comande" }],
  delivery: [{ href: "/dashboard", label: "Consegne" }],
  receptionista: [{ href: "/dashboard/prenotazioni", label: "Prenotazioni" }],
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const me = useMe();
  const pathname = usePathname();
  const router = useRouter();

  const links = me ? LINKS_BY_ROLE[me.role] || LINKS_BY_ROLE.owner : OWNER_LINKS;
  const allowedHrefs = links.map((l) => l.href);

  usePushNotifications(!!me);
  useHeartbeat(!!me);

  useEffect(() => {
    if (me === null) router.replace("/login");
  }, [me, router]);

  useEffect(() => {
    // Sotto-account (cuoco/delivery/receptionista) hanno solo 1-2 pagine
    // consentite: se navigano (o incollano un link) verso una sezione
    // riservata al titolare, il backend risponderebbe comunque 403 -
    // qui li rimandiamo subito alla loro pagina invece di mostrare una
    // schermata rotta piena di errori.
    if (me && !allowedHrefs.includes(pathname)) router.replace(allowedHrefs[0]);
  }, [me, pathname, allowedHrefs, router]);

  if (me === undefined || me === null) {
    return <div className="page">Verifica accesso...</div>;
  }

  if (!allowedHrefs.includes(pathname)) {
    return <div className="page">Verifica accesso...</div>;
  }

  async function logout() {
    await api.post("/api/auth/logout");
    window.location.href = "/login";
  }

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <h2>Pizza SaaS</h2>
        {links.map((link) => (
          <Link key={link.href} href={link.href} className={pathname === link.href ? "active" : ""}>
            {link.label}
          </Link>
        ))}
        <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8 }}>
          <ThemeToggle />
          <button onClick={logout} className="secondary">Esci</button>
        </div>
      </aside>
      <main className="admin-main">{children}</main>
    </div>
  );
}
