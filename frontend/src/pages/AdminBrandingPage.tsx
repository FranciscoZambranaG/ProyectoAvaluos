import { useEffect, useState, type FormEvent } from "react";
import { api } from "../lib/api";
import type { Branding } from "../lib/branding";

const empty: Branding = {
  org: "",
  unit: "",
  portal: "",
  slogan: "",
  tagline: "",
  colors: {
    navy: "#00A7D6",
    navy2: "#0078A8",
    blue: "#00A7D6",
    blueSoft: "#E8F7FB",
    ink: "#12323C",
    muted: "#4A6B75",
    bg: "#F3FAFC",
  },
  logo_url: "",
};

export function AdminBrandingPage() {
  const [form, setForm] = useState<Branding>(empty);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api<Branding>("/api/v1/admin/branding", {}, true)
      .then((b) => setForm({ ...empty, ...b, colors: { ...empty.colors, ...(b.colors || {}) }, logo_url: b.logo_url || "" }))
      .catch((e) => setError(e instanceof Error ? e.message : "Error"));
  }, []);

  async function save(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const saved = await api<Branding>("/api/v1/admin/branding", {
        method: "PUT",
        body: JSON.stringify({ ...form, logo_url: form.logo_url || null }),
      }, true);
      setForm({ ...empty, ...saved, colors: { ...empty.colors, ...(saved.colors || {}) }, logo_url: saved.logo_url || "" });
      setMsg("Branding guardado. Recargue la página para ver los colores en todo el portal.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  function setColor(key: string, value: string) {
    setForm({ ...form, colors: { ...form.colors, [key]: value } });
  }

  return (
    <div className="page">
      <h2>Administración · Branding</h2>
      <p className="muted">Identidad Cocha del manual de marca GAMC (p. ej. «Cocha es progreso», celeste #00A7D6).</p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="hint">{msg}</div>}

      <form onSubmit={save} className="card admin-form" style={{ maxWidth: 720 }}>
        <div className="field"><label>Organización</label><input value={form.org} onChange={(e) => setForm({ ...form, org: e.target.value })} /></div>
        <div className="field"><label>Unidad</label><input value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} /></div>
        <div className="field"><label>Nombre del portal</label><input value={form.portal} onChange={(e) => setForm({ ...form, portal: e.target.value })} /></div>
        <div className="field"><label>Eslogan</label><input value={form.slogan} onChange={(e) => setForm({ ...form, slogan: e.target.value })} /></div>
        <div className="field"><label>Frase / tagline</label><input value={form.tagline} onChange={(e) => setForm({ ...form, tagline: e.target.value })} /></div>
        <div className="field"><label>URL del logo</label><input value={form.logo_url || ""} onChange={(e) => setForm({ ...form, logo_url: e.target.value })} placeholder="https://… o /media/…" /></div>

        <strong>Colores</strong>
        <div className="grid2">
          {(["navy", "navy2", "blue", "blueSoft", "ink", "muted", "bg"] as const).map((k) => (
            <div className="field" key={k}>
              <label>{k}</label>
              <div style={{ display: "flex", gap: ".5rem", alignItems: "center" }}>
                <input type="color" value={form.colors[k] || "#000000"} onChange={(e) => setColor(k, e.target.value)} style={{ width: 48, height: 36, padding: 0 }} />
                <input value={form.colors[k] || ""} onChange={(e) => setColor(k, e.target.value)} />
              </div>
            </div>
          ))}
        </div>

        <button className="btn btn-primary" disabled={loading} type="submit">Guardar branding</button>
      </form>
    </div>
  );
}
