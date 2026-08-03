"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useMe } from "@/lib/useMe";

export default function Home() {
  const me = useMe();
  const router = useRouter();

  useEffect(() => {
    if (me === undefined) return;
    router.replace(me ? "/dashboard" : "/login");
  }, [me, router]);

  return <div className="page">Caricamento...</div>;
}
