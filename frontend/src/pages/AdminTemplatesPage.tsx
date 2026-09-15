import { useEffect, useState } from "react";
import { ApiError, api, API_URL } from "../lib/api";
import { getToken } from "../lib/auth";

type TemplateInfo = {
  code: string;
  name: string;
  filename: string;
  description: string;
  source: "builtin" | "custom" | string;
  size_bytes: number;
  updated_at?: string | null;
  has_custom: boolean;
  placeholders: string[];
};

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

async function downloadAuth(path: string, fallbackName: string) {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    let message = "No se pudo descargar";
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") message = data.detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, message);
  }
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") || "";
  const match = /filename=\"?([^\";]+)\"?/i.exec(cd);
  const name = match?.[1] || fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function AdminTemplatesPage() {
  const [items, setItems] = useState<TemplateInfo[]>([]);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    const rows = await api<TemplateInfo[]>("/api/v1/admin/templates", {}, true);
    setItems(rows);
  }

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Error"));
  }, []);

  async function onUpload(code: string, file: File) {
    setLoading(true);
    setError("");
    setMsg("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      await api<TemplateInfo>(`/api/v1/admin/templates/${code}`, { method: "POST", body: fd }, true);
      setMsg("Plantilla cargada. Se usará en la próxima impresión del formulario.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al subir");
    } finally {
      setLoading(false);
    }
  }

  async function onRestore(code: string) {
    if (!confirm("¿Restaurar la plantilla predeterminada del sistema?")) return;
    setLoading(true);
    setError("");
    setMsg("");
    try {
      await api<TemplateInfo>(`/api/v1/admin/templates/${code}`, { method: "DELETE" }, true);
      setMsg("Se restauró la plantilla predeterminada.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <h2>Administración · Plantillas</h2>
      <p className="muted">
        Descargue la plantilla vacía de referencia, edítela en Word y súbala de nuevo. La plantilla activa se usa al
        imprimir el formulario de datos técnicos (si incluye marcadores Jinja/docxtpl; si no, se usa el layout interno).
      </p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="hint">{msg}</div>}

      {items.map((t) => (
        <section className="card admin-form" key={t.code} style={{ maxWidth: 820, marginBottom: "1rem" }}>
          <strong>{t.name}</strong>
          <p className="muted" style={{ fontSize: ".9rem", margin: ".35rem 0 .8rem" }}>
            {t.description}
          </p>
          <div className="grid2" style={{ marginBottom: ".85rem" }}>
            <div>
              <span className="muted">Archivo</span>
              <div>
                <b>{t.filename}</b>
              </div>
            </div>
            <div>
              <span className="muted">Origen</span>
              <div>
                <b>{t.source === "custom" ? "Personalizada (subida)" : "Predeterminada del sistema"}</b>
              </div>
            </div>
            <div>
              <span className="muted">Tamaño</span>
              <div>{formatBytes(t.size_bytes)}</div>
            </div>
            <div>
              <span className="muted">Actualizada</span>
              <div>{t.updated_at ? new Date(t.updated_at).toLocaleString("es-BO") : "—"}</div>
            </div>
          </div>

          <div className="actions" style={{ flexWrap: "wrap", gap: ".5rem" }}>
            <button
              type="button"
              className="btn btn-out"
              disabled={loading}
              onClick={() =>
                void downloadAuth(`/api/v1/admin/templates/${t.code}/blank`, `plantilla_vacia_${t.filename}`).catch(
                  (e) => setError(e instanceof Error ? e.message : "Error"),
                )
              }
            >
              Descargar plantilla vacía
            </button>
            <button
              type="button"
              className="btn btn-out"
              disabled={loading}
              onClick={() =>
                void downloadAuth(`/api/v1/admin/templates/${t.code}/download`, t.filename).catch((e) =>
                  setError(e instanceof Error ? e.message : "Error"),
                )
              }
            >
              Descargar plantilla activa
            </button>
            <label className="btn btn-primary" style={{ cursor: loading ? "wait" : "pointer", margin: 0 }}>
              {loading ? "Subiendo…" : "Cargar nuevo formato (.docx)"}
              <input
                type="file"
                accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                hidden
                disabled={loading}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void onUpload(t.code, f);
                  e.target.value = "";
                }}
              />
            </label>
            {t.has_custom && (
              <button type="button" className="btn btn-out" disabled={loading} onClick={() => void onRestore(t.code)}>
                Restaurar predeterminada
              </button>
            )}
          </div>

          <details style={{ marginTop: "1rem" }}>
            <summary style={{ cursor: "pointer" }}>Marcadores disponibles</summary>
            <ul className="muted" style={{ fontSize: ".85rem", marginTop: ".5rem", columns: 2, gap: "1.5rem" }}>
              {t.placeholders.map((p) => (
                <li key={p}>
                  <code>{p.includes("(") ? p : `{{${p}}}`}</code>
                </li>
              ))}
            </ul>
            <p className="muted" style={{ fontSize: ".82rem" }}>
              Para filas dinámicas use sintaxis docxtpl, por ejemplo{" "}
              <code>{`{%tr for b in blocks %}…{{ b.unit_number }}…{% endtr %}`}</code>.
            </p>
          </details>
        </section>
      ))}
    </div>
  );
}
