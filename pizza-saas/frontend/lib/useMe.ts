"use client";
import { useEffect, useState } from "react";
import { api } from "./api";

export type Me = { id: string; email: string; tenant_id: string; role: string };

export function useMe() {
  const [me, setMe] = useState<Me | null | undefined>(undefined); // undefined = ancora in caricamento

  useEffect(() => {
    api
      .get("/api/auth/me")
      .then((data) => setMe(data))
      .catch(() => setMe(null));
  }, []);

  return me;
}
