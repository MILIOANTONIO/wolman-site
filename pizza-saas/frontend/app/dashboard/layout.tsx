"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useMe } from "@/lib/useMe";
import { ThemeToggle } from "@/lib/ThemeToggle";
import { usePushNotifications } from "@/lib/usePushNotifications";
import { useHeartbeat } from "@/lib/useHeartbeat";
import { useOrdersSocket } from "@/lib/useOrdersSocket";
import { InstallAppButton } from "@/lib/InstallAppButton";

// Eventi WebSocket che fanno comparire un pallino sulla voce di menu
// corrispondente - si azzera quando l'utente apre quella pagina. Vale solo
// per la sessione aperta (non recupera eventi arrivati mentre il browser
// era chiuso).
const BADGE_EVENT_TO_HREF: Record<string, string> = {
  order_created: "/dashboard",
  reservation_created: "/dashboard/prenotazioni",
};

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

  const [badges, setBadges] = useState<Record<string, number>>({});

  useOrdersSocket(me?.tenant_id ?? null, (event) => {
    const href = BADGE_EVENT_TO_HREF[event.type];
    if (!href || href === pathname) return; // gia' sulla pagina: niente pallino
    setBadges((prev) => ({ ...prev, [href]: (prev[href] || 0) + 1 }));
  });

  useEffect(() => {
    setBadges((prev) => (prev[pathname] ? { ...prev, [pathname]: 0 } : prev));
  }, [pathname]);

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
          <Link
            key={link.href}
            href={link.href}
            className={pathname === link.href ? "active" : ""}
            style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}
          >
            <span>{link.label}</span>
            {!!badges[link.href] && (
              <span
                style={{
                  background: "var(--accent)", color: "#fff", borderRadius: 999,
                  fontSize: "0.72rem", fontWeight: 700, minWidth: 18, height: 18,
                  display: "inline-flex", alignItems: "center", justifyContent: "center", padding: "0 5px",
                }}
              >
                {badges[link.href]}
              </span>
            )}
          </Link>
        ))}
        <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8 }}>
          <ThemeToggle />
          <InstallAppButton />
          <button onClick={logout} className="secondary">Esci</button>
        </div>
      </aside>
      <main className="admin-main">{children}</main>
    </div>
  );
}
