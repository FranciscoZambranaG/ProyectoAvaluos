/** Interpreta coma como decimal (es-BO). El punto del teclado numérico se trata igual. */
export function parseDecimal(raw: string): number | null {
  const s = raw.trim().replace(/\s/g, "");
  if (!s || s === "," || s === "." || s === "-") return null;
  let normalized = s;
  if (s.includes(",") && s.includes(".")) {
    const lastComma = s.lastIndexOf(",");
    const lastDot = s.lastIndexOf(".");
    if (lastComma > lastDot) {
      normalized = s.replace(/\./g, "").replace(",", ".");
    } else {
      normalized = s.replace(/,/g, "");
    }
  } else {
    normalized = s.replace(",", ".");
  }
  const n = Number(normalized);
  return Number.isFinite(n) ? n : null;
}

export function formatDecimal(value: number | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) return "";
  return String(value).replace(".", ",");
}

export function isNumpadDecimal(e: { code?: string; key?: string; location?: number }) {
  return e.code === "NumpadDecimal" || (e.key === "." && e.location === 3);
}
