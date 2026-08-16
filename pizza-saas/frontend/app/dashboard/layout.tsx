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
import { useAppUpdate } from "@/lib/useAppUpdate";

// Eventi WebSocket che fanno comparire un pallino sulla voce di menu
// corrispondente - si azzera quando l'utente apre quella pagina. Vale solo
// per la sessione aperta (non recupera eventi arrivati mentre il browser
// era chiuso).
const BADGE_EVENT_TO_HREF: Record<string, string> = {
  order_created: "/dashboard",
  reservation_created: "/dashboard/prenotazioni",
};

type NavLink = { href: string; label: string; children?: { href: string; label: string }[] };

const OWNER_LINKS: NavLink[] = [
  { href: "/dashboard", label: "Ordini" },
  { href: "/dashboard/statistiche", label: "Statistiche" },
  { href: "/dashboard/prenotazioni", label: "Prenotazioni" },
  { href: "/dashboard/mappa", label: "Mappa consegne" },
  { href: "/dashboard/configurazione", label: "Configurazione" },
  { href: "/dashboard/menu", label: "Menu" },
  { href: "/dashboard/promozioni", label: "Promozioni" },
  {
    href: "/dashboard/viralizza", label: "Viralizza",
    children: [
      { href: "/dashboard/viralizza/webapp", label: "Webapp" },
      { href: "/dashboard/viralizza/promoziona", label: "Promoziona" },
      { href: "/dashboard/viralizza/promoziona/libreria", label: "Libreria" },
      { href: "/dashboard/viralizza/promoziona/crea", label: "Crea Reel" },
      { href: "/dashboard/viralizza/promoziona/social", label: "Social" },
    ],
  },
  { href: "/dashboard/agente", label: "Agente AI" },
  { href: "/dashboard/consumi", label: "Consumi" },
];

// Sotto-account: ognuno vede solo la sua sezione - la restrizione vera è
// lato backend (require_roles), questa lista serve solo a non mostrare
// link che porterebbero comunque a un 403.
const LINKS_BY_ROLE: Record<string, NavLink[]> = {
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
  const allowedHrefs = links.flatMap((l) => [l.href, ...(l.children?.map((c) => c.href) || [])]);

  useAppUpdate();
  const pushStatus = usePushNotifications(!!me);
  useHeartbeat(!!me);

  const [badges, setBadges] = useState<Record<string, number>>({});
  const [openGroup, setOpenGroup] = useState<string | null>(
    links.find((l) => l.children?.some((c) => pathname.startsWith(c.href)))?.href ?? null
  );

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
        {links.map((link) => {
          if (link.children) {
            const isOpen = openGroup === link.href;
            const isActiveGroup = link.children.some((c) => pathname.startsWith(c.href));
            return (
              <div key={link.href}>
                <button
                  type="button"
                  onClick={() => setOpenGroup(isOpen ? null : link.href)}
                  className={`nav-toggle${isActiveGroup ? " active" : ""}`}
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8,
                    width: "100%", background: "none", border: "none", textAlign: "left",
                    font: "inherit", cursor: "pointer",
                  }}
                >
                  <span>{link.label}</span>
                  <span style={{ transition: "transform .15s", transform: isOpen ? "rotate(90deg)" : "none", opacity: 0.6 }}>›</span>
                </button>
                {isOpen && (
                  <div style={{ display: "flex", flexDirection: "column" }}>
                    {link.children.map((child) => (
                      <Link
                        key={child.href}
                        href={child.href}
                        className={pathname === child.href ? "active" : ""}
                        style={{ paddingLeft: 26, fontSize: "0.92rem" }}
                      >
                        {child.label}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            );
          }
          return (
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
          );
        })}
        <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8 }}>
          <ThemeToggle />
          <InstallAppButton />
          <button onClick={logout} className="secondary">Esci</button>
        </div>
      </aside>
      <main className="admin-main">
        {pushStatus === "denied" && (
          <div className="card" style={{ marginBottom: 16, borderColor: "var(--accent)" }}>
            <strong>⚠️ Notifiche disattivate</strong>
            <div className="muted" style={{ marginTop: 4 }}>
              Senza notifiche attive non saprai quando arriva un nuovo ordine mentre l'app è chiusa. Il browser non richiede il permesso una seconda volta dopo averlo negato: va riattivato a mano.
            </div>
            <div className="muted" style={{ marginTop: 8 }}>
              <strong>Su Windows (app installata):</strong> tasto destro sull'icona nella barra delle applicazioni → Gestisci → Notifiche → attiva. Oppure Impostazioni di Windows → App → Pizza SaaS → Notifiche.<br />
              <strong>In Chrome/Edge (browser):</strong> clicca il lucchetto 🔒 accanto all'indirizzo del sito → Notifiche → Consenti.<br />
              <strong>Su Android/iPhone:</strong> Impostazioni del telefono → App → Pizza SaaS (o il browser usato) → Notifiche → attiva.
            </div>
            <div className="muted" style={{ marginTop: 8 }}>Dopo averle riattivate, ricarica questa pagina.</div>
          </div>
        )}
        {children}
      </main>
    </div>
  );
}
