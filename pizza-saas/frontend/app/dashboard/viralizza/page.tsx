"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

// Viralizza e' ora una sezione con sotto-pagine (Webapp, Promoziona) - questo
// indirizzo di base rimanda alla prima sotto-pagina invece di mostrare
// contenuto proprio.
export default function ViralizzaRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/dashboard/viralizza/webapp");
  }, [router]);
  return <div className="page">Caricamento...</div>;
}
