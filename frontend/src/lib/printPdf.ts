import { getToken } from "./auth";
import { API_URL } from "./api";

/**
 * Genera el PDF del formulario y abre el diálogo de impresión del navegador
 * (sin abrir otra pestaña).
 */
export async function printAppraisalPdf(appraisalId: string): Promise<void> {
  const token = getToken();
  const res = await fetch(`${API_URL}/api/v1/appraisals/${appraisalId}/pdf`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    let msg = "No se pudo generar el documento";
    try {
      const j = await res.json();
      if (typeof j?.detail === "string") msg = j.detail;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);

  await new Promise<void>((resolve, reject) => {
    const iframe = document.createElement("iframe");
    iframe.setAttribute("aria-hidden", "true");
    iframe.style.position = "fixed";
    iframe.style.right = "0";
    iframe.style.bottom = "0";
    iframe.style.width = "0";
    iframe.style.height = "0";
    iframe.style.border = "0";
    iframe.style.opacity = "0";
    iframe.style.pointerEvents = "none";

    let settled = false;
    const finish = (err?: Error) => {
      if (settled) return;
      settled = true;
      window.setTimeout(() => {
        URL.revokeObjectURL(url);
        iframe.remove();
      }, 90_000);
      if (err) reject(err);
      else resolve();
    };

    iframe.onload = () => {
      window.setTimeout(() => {
        try {
          const win = iframe.contentWindow;
          if (!win) throw new Error("No se pudo abrir la vista de impresión");
          win.focus();
          win.print();
          finish();
        } catch (e) {
          finish(e instanceof Error ? e : new Error("Error al imprimir"));
        }
      }, 450);
    };

    iframe.onerror = () => finish(new Error("No se pudo cargar el PDF para imprimir"));
    document.body.appendChild(iframe);
    iframe.src = url;
  });
}
