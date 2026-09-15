import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../lib/api";

export type Branding = {
  org: string;
  unit: string;
  portal: string;
  slogan: string;
  tagline: string;
  colors: Record<string, string>;
  logo_url?: string | null;
};

const defaults: Branding = {
  org: "Gobierno Autónomo Municipal de Cochabamba",
  unit: "Dirección de Administración Geográfica y Catastro",
  portal: "Portal de Catastro Municipal",
  slogan: "Trámite claro y cercano para el avalúo de su predio.",
  tagline: "Cocha es progreso",
  colors: {
    navy: "#341A67",
    navy2: "#26154A",
    blue: "#341A67",
    blueSoft: "#EDF8FD",
    ink: "#1E1033",
    muted: "#64748B",
    bg: "#F3FAFC",
  },
  logo_url: "/brand/cocha-cyan.png",
};

const BrandingContext = createContext<Branding>(defaults);

function applyCssVars(colors: Record<string, string>) {
  const root = document.documentElement;
  if (colors.navy) root.style.setProperty("--navy", colors.navy);
  if (colors.navy2) root.style.setProperty("--navy-2", colors.navy2);
  if (colors.blue) root.style.setProperty("--blue", colors.blue);
  if (colors.blueSoft) root.style.setProperty("--blue-soft", colors.blueSoft);
  if (colors.ink) root.style.setProperty("--ink", colors.ink);
  if (colors.muted) root.style.setProperty("--muted", colors.muted);
  if (colors.bg) root.style.setProperty("--bg", colors.bg);
}

export function BrandingProvider({ children }: { children: ReactNode }) {
  const [branding, setBranding] = useState<Branding>(defaults);

  useEffect(() => {
    api<Branding>("/api/v1/public/branding")
      .then((b) => {
        const merged = {
          ...defaults,
          ...b,
          colors: { ...defaults.colors, ...(b.colors || {}) },
        };
        setBranding(merged);
        applyCssVars(merged.colors);
      })
      .catch(() => applyCssVars(defaults.colors));
  }, []);

  const value = useMemo(() => branding, [branding]);
  return <BrandingContext.Provider value={value}>{children}</BrandingContext.Provider>;
}

export function useBranding() {
  return useContext(BrandingContext);
}
