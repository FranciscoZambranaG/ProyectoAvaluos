import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";

type Param = {
  key: string;
  value_json: unknown;
  description?: string | null;
  value_type: string;
  is_public: boolean;
};

type Meta = {
  title: string;
  help: string;
  group: string;
};

const META: Record<string, Meta> = {
  max_photos_per_property: {
    title: "Máximo de fotos por predio",
    help: "Cantidad máxima de fotografías que puede subir el contribuyente.",
    group: "Fotografías",
  },
  min_photos_per_property: {
    title: "Mínimo de fotos para enviar",
    help: "Cantidad mínima requerida antes de enviar el formulario a revisión.",
    group: "Fotografías",
  },
  image_pipeline: {
    title: "Conversión de imágenes",
    help: "Todas las fotos se convierten automáticamente a WebP para ahorrar espacio.",
    group: "Fotografías",
  },
  map_provider: {
    title: "Proveedor de mapa",
    help: "Servicio de mapa usado en el formulario (OpenStreetMap).",
    group: "Mapa",
  },
  map_center: {
    title: "Centro del mapa",
    help: "Punto inicial al abrir el mapa (latitud, longitud y zoom).",
    group: "Mapa",
  },
  map_tile_url: {
    title: "Dirección de las teselas del mapa",
    help: "URL técnica de las imágenes del mapa. Normalmente no se cambia.",
    group: "Mapa",
  },
  geocoder_url: {
    title: "Búsqueda de direcciones",
    help: "Servicio que convierte texto de dirección en coordenadas.",
    group: "Mapa",
  },
  gis_layers: {
    title: "Capas GIS (satélite, límites Cercado, predios, zona, vía, relieve)",
    help: "Imagen satelital (base), límites del municipio Cercado (restringe el mapa) y URLs WMS del GAMC. Si el servicio cambia, actualice aquí. Las capas no visibles solo se consultan (no se dibujan en el mapa).",
    group: "Mapa",
  },
  ipiu_base: {
    title: "Base IPIU",
    help: "Factor mínimo de infraestructura urbana (IPIU = base + suma de servicios). También en Admin → IPIU.",
    group: "Avalúo",
  },
  ipes_base: {
    title: "Base IPES",
    help: "Factor mínimo de equipamiento social (IPES = base + suma de equipamientos). También en Admin → IPES.",
    group: "Avalúo",
  },
  current_fiscal_year: {
    title: "Gestión / año fiscal vigente",
    help: "Año de gestión actual del sistema de avalúos.",
    group: "Avalúo",
  },
  appraisal_form_number_pattern: {
    title: "Numeración de formularios",
    help: "Patrón del número de formulario. {YYYY} = año, {SEQ:6} = correlativo.",
    group: "Avalúo",
  },
  pdf_keep_history: {
    title: "Conservar historial de PDF",
    help: "Si está activo, se guarda cada versión del PDF generado.",
    group: "Avalúo",
  },
  migration_target_default: {
    title: "Destino de migración",
    help: "Servidor municipal destino al migrar un formulario aprobado.",
    group: "Avalúo",
  },
  password_policy: {
    title: "Política de contraseñas",
    help: "Reglas de seguridad al crear o cambiar contraseña.",
    group: "Seguridad",
  },
  password_reset_ttl_minutes: {
    title: "Vigencia del enlace de recuperación",
    help: "Minutos que dura el enlace para restablecer la contraseña.",
    group: "Seguridad",
  },
  email_verification_required: {
    title: "Verificar correo al registrarse",
    help: "Si está activo, el usuario debe confirmar su correo.",
    group: "Seguridad",
  },
  branding: {
    title: "Identidad del portal (branding)",
    help: "Colores, textos y logo. Se edita en el módulo Branding.",
    group: "Portal",
  },
  ui_layout: {
    title: "Diseño del formulario",
    help: "Tema visual y orden de las pestañas del formulario de avalúo.",
    group: "Portal",
  },
};

function titleOf(key: string, fallback?: string | null) {
  return META[key]?.title || fallback || key;
}

function helpOf(key: string, fallback?: string | null) {
  return META[key]?.help || fallback || "";
}

function groupOf(key: string) {
  return META[key]?.group || "Otros";
}

function unwrap(v: unknown): unknown {
  // algunos valores string vienen serializados con comillas JSON
  return v;
}

export function AdminParametersPage() {
  const [rows, setRows] = useState<Param[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [value, setValue] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  const grouped = useMemo(() => {
    const map = new Map<string, Param[]>();
    for (const r of rows) {
      const g = groupOf(r.key);
      if (!map.has(g)) map.set(g, []);
      map.get(g)!.push(r);
    }
    return [...map.entries()];
  }, [rows]);

  async function load() {
    const list = await api<Param[]>("/api/v1/admin/parameters", {}, true);
    setRows(list);
    if (!selectedKey && list[0]) {
      setSelectedKey(list[0].key);
      setValue(list[0].value_json);
    }
  }

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Error"));
  }, []);

  useEffect(() => {
    const row = rows.find((r) => r.key === selectedKey);
    if (row) setValue(unwrap(row.value_json));
  }, [selectedKey, rows]);

  async function save(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api(`/api/v1/admin/parameters/${encodeURIComponent(selectedKey)}`, {
        method: "PUT",
        body: JSON.stringify({ value_json: value }),
      }, true);
      setMsg(`«${titleOf(selectedKey)}» guardado`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar");
    } finally {
      setLoading(false);
    }
  }

  const selected = rows.find((r) => r.key === selectedKey);

  return (
    <div className="page">
      <h2>Administración · Parámetros</h2>
      <p className="muted">Ajustes del sistema en lenguaje sencillo. No necesita conocimientos técnicos.</p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="hint">{msg}</div>}

      <div className="admin-grid" style={{ gridTemplateColumns: "1fr 1.6fr" }}>
        <section className="card">
          <strong>Configuraciones</strong>
          {grouped.map(([group, items]) => (
            <div key={group} style={{ marginTop: ".7rem" }}>
              <div className="muted" style={{ fontSize: ".75rem", fontWeight: 700, marginBottom: ".25rem" }}>{group}</div>
              <ul className="admin-list">
                {items.map((r) => (
                  <li key={r.key}>
                    <button type="button" className={r.key === selectedKey ? "on" : ""} onClick={() => setSelectedKey(r.key)}>
                      <span>{titleOf(r.key, r.description)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>

        <section className="card">
          {!selected ? (
            <p className="muted">Seleccione una configuración</p>
          ) : (
            <form onSubmit={save} className="admin-form">
              <h3 style={{ margin: 0, fontSize: "1.05rem" }}>{titleOf(selected.key, selected.description)}</h3>
              <p className="muted">{helpOf(selected.key, selected.description)}</p>
              <p className="muted" style={{ fontSize: ".8rem" }}>
                {selected.is_public ? "Visible en el portal" : "Solo uso interno"}
              </p>
              <ParamEditor paramKey={selected.key} value={value} onChange={setValue} />
              {selected.key === "branding" ? (
                <p className="hint">
                  Para colores, logo y frases use el módulo{" "}
                  <Link to="/app/admin/branding">Branding</Link>.
                </p>
              ) : (
                <button className="btn btn-primary" disabled={loading} type="submit">Guardar</button>
              )}
            </form>
          )}
        </section>
      </div>
    </div>
  );
}

function ParamEditor({
  paramKey,
  value,
  onChange,
}: {
  paramKey: string;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  if (paramKey === "branding") {
    return <p className="muted">Edición disponible en Branding.</p>;
  }

  if (typeof value === "number" || paramKey.includes("year") || paramKey.includes("photos") || paramKey.includes("ttl") || paramKey.includes("minutes")) {
    const n = typeof value === "number" ? value : Number(value);
    return (
      <div className="field">
        <label>Valor</label>
        <input type="number" value={Number.isFinite(n) ? n : 0} onChange={(e) => onChange(Number(e.target.value))} />
      </div>
    );
  }

  if (typeof value === "boolean" || paramKey.includes("required") || paramKey.includes("keep_history")) {
    const b = Boolean(value);
    return (
      <label className="svcs">
        <input type="checkbox" checked={b} onChange={(e) => onChange(e.target.checked)} />
        Activado
      </label>
    );
  }

  if (paramKey === "map_center" && value && typeof value === "object") {
    const o = value as { lat?: number; lng?: number; zoom?: number };
    return (
      <div className="grid2">
        <NumField label="Latitud" value={o.lat ?? 0} onChange={(lat) => onChange({ ...o, lat })} />
        <NumField label="Longitud" value={o.lng ?? 0} onChange={(lng) => onChange({ ...o, lng })} />
        <NumField label="Zoom" value={o.zoom ?? 13} onChange={(zoom) => onChange({ ...o, zoom })} />
      </div>
    );
  }

  if (paramKey === "password_policy" && value && typeof value === "object") {
    const o = value as Record<string, unknown>;
    return (
      <div className="admin-form">
        <NumField
          label="Longitud mínima"
          value={Number(o.min_length ?? 8)}
          onChange={(min_length) => onChange({ ...o, min_length })}
        />
        <Check label="Exigir mayúsculas" checked={Boolean(o.require_upper)} onChange={(require_upper) => onChange({ ...o, require_upper })} />
        <Check label="Exigir minúsculas" checked={Boolean(o.require_lower)} onChange={(require_lower) => onChange({ ...o, require_lower })} />
        <Check label="Exigir número" checked={Boolean(o.require_digit)} onChange={(require_digit) => onChange({ ...o, require_digit })} />
        <Check label="Exigir carácter especial" checked={Boolean(o.require_special)} onChange={(require_special) => onChange({ ...o, require_special })} />
      </div>
    );
  }

  if (paramKey === "image_pipeline" && value && typeof value === "object") {
    const o = value as Record<string, unknown>;
    return (
      <div className="admin-form">
        <div className="field">
          <label>Formato de salida</label>
          <select value={String(o.convert_to || "webp")} onChange={(e) => onChange({ ...o, convert_to: e.target.value })}>
            <option value="webp">WebP (recomendado)</option>
          </select>
        </div>
        <NumField label="Calidad (1–100)" value={Number(o.quality ?? 82)} onChange={(quality) => onChange({ ...o, quality })} />
        <Check label="Conservar archivo original" checked={Boolean(o.keep_original)} onChange={(keep_original) => onChange({ ...o, keep_original })} />
      </div>
    );
  }

  if (paramKey === "ui_layout" && value && typeof value === "object") {
    const o = value as { theme?: string; form_stepper?: string[] };
    const steps = (o.form_stepper || []).join(", ");
    return (
      <div className="admin-form">
        <div className="field">
          <label>Tema visual</label>
          <input value={o.theme || ""} onChange={(e) => onChange({ ...o, theme: e.target.value })} />
        </div>
        <div className="field">
          <label>Orden de pasos (separados por coma)</label>
          <textarea
            rows={3}
            value={steps}
            onChange={(e) =>
              onChange({
                ...o,
                form_stepper: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
              })
            }
          />
        </div>
      </div>
    );
  }

  if (paramKey === "gis_layers" && value && typeof value === "object") {
    const layers = value as Record<string, Record<string, unknown>>;
    const preferred = ["satellite", "municipal_limits", "parcels", "constructions", "road_material", "zone_homogeneous", "topography"];
    const keys = [...preferred.filter((k) => k in layers), ...Object.keys(layers).filter((k) => !preferred.includes(k))];
    return (
      <div className="admin-form">
        {keys.map((code) => {
          const layer = layers[code] || {};
          const isXyz = String(layer.layer_type || "") === "xyz" || code === "satellite" || Boolean(layer.tile_url && !layer.wms_url);
          const printOnly = Boolean(layer.print_only) || code === "constructions";
          return (
            <div key={code} className="card" style={{ padding: ".75rem" }}>
              <strong>{String(layer.name || code)}</strong>
              {printOnly ? (
                <p className="muted" style={{ margin: ".35rem 0 .6rem", fontSize: ".85rem" }}>
                  Solo se usa en el croquis del PDF. No se dibuja en el mapa del formulario.
                </p>
              ) : (
                <Check
                  label={isXyz ? "Visible en el mapa (capa base, debajo de predios y vías)" : "Visible en el mapa (si está apagada, solo se consulta)"}
                  checked={Boolean(layer.visible)}
                  onChange={(visible) => onChange({ ...layers, [code]: { ...layer, visible } })}
                />
              )}
              {isXyz ? (
                <>
                  <div className="field">
                    <label>URL de teselas satelitales (XYZ, proveedor gratuito)</label>
                    <input
                      value={String(layer.tile_url || "")}
                      onChange={(e) => onChange({ ...layers, [code]: { ...layer, tile_url: e.target.value } })}
                    />
                  </div>
                  <div className="field">
                    <label>Atribución</label>
                    <input
                      value={String(layer.attribution || "")}
                      onChange={(e) => onChange({ ...layers, [code]: { ...layer, attribution: e.target.value } })}
                    />
                  </div>
                </>
              ) : (
                <>
                  <div className="field">
                    <label>URL WMS</label>
                    <input
                      value={String(layer.wms_url || "")}
                      onChange={(e) => onChange({ ...layers, [code]: { ...layer, wms_url: e.target.value } })}
                    />
                  </div>
                  <div className="field">
                    <label>URL Identify (consulta)</label>
                    <input
                      value={String(layer.identify_url || "")}
                      onChange={(e) => onChange({ ...layers, [code]: { ...layer, identify_url: e.target.value } })}
                    />
                  </div>
                  {code === "parcels" && (
                    <div className="field">
                      <label>URL Query (búsqueda por código)</label>
                      <input
                        value={String(layer.query_url || "")}
                        onChange={(e) => onChange({ ...layers, [code]: { ...layer, query_url: e.target.value } })}
                      />
                    </div>
                  )}
                  {code === "municipal_limits" && (
                    <>
                      <div className="field">
                        <label>Capa WMS (0 = Límites de Cercado)</label>
                        <input
                          value={String(layer.wms_layer ?? "0")}
                          onChange={(e) => onChange({ ...layers, [code]: { ...layer, wms_layer: e.target.value } })}
                        />
                      </div>
                      <div className="field">
                        <label>Color del límite (más llamativo sobre la satelital)</label>
                        <div style={{ display: "flex", gap: ".6rem", alignItems: "center" }}>
                          <input
                            type="color"
                            value={String(layer.color || "#FFD400")}
                            onChange={(e) => onChange({ ...layers, [code]: { ...layer, color: e.target.value } })}
                          />
                          <input
                            value={String(layer.color || "#FFD400")}
                            onChange={(e) => onChange({ ...layers, [code]: { ...layer, color: e.target.value } })}
                          />
                        </div>
                      </div>
                      <Check
                        label="Restringir el mapa a este recuadro (no se puede salir del Cercado)"
                        checked={layer.constrain_map !== false}
                        onChange={(constrain_map) => onChange({ ...layers, [code]: { ...layer, constrain_map } })}
                      />
                      <div className="grid2">
                        <NumField
                          label="Sur (lat)"
                          value={Number((layer.bounds as { south?: number } | undefined)?.south ?? -17.53119)}
                          onChange={(south) =>
                            onChange({
                              ...layers,
                              [code]: { ...layer, bounds: { ...((layer.bounds as object) || {}), south } },
                            })
                          }
                        />
                        <NumField
                          label="Oeste (lng)"
                          value={Number((layer.bounds as { west?: number } | undefined)?.west ?? -66.2807)}
                          onChange={(west) =>
                            onChange({
                              ...layers,
                              [code]: { ...layer, bounds: { ...((layer.bounds as object) || {}), west } },
                            })
                          }
                        />
                        <NumField
                          label="Norte (lat)"
                          value={Number((layer.bounds as { north?: number } | undefined)?.north ?? -17.25731)}
                          onChange={(north) =>
                            onChange({
                              ...layers,
                              [code]: { ...layer, bounds: { ...((layer.bounds as object) || {}), north } },
                            })
                          }
                        />
                        <NumField
                          label="Este (lng)"
                          value={Number((layer.bounds as { east?: number } | undefined)?.east ?? -66.06952)}
                          onChange={(east) =>
                            onChange({
                              ...layers,
                              [code]: { ...layer, bounds: { ...((layer.bounds as object) || {}), east } },
                            })
                          }
                        />
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  if (typeof value === "string") {
    return (
      <div className="field">
        <label>Valor</label>
        <input value={value} onChange={(e) => onChange(e.target.value)} />
      </div>
    );
  }

  return (
    <div className="field">
      <label>Valor</label>
      <textarea
        rows={8}
        value={typeof value === "string" ? value : JSON.stringify(value, null, 2)}
        onChange={(e) => {
          try {
            onChange(JSON.parse(e.target.value));
          } catch {
            onChange(e.target.value);
          }
        }}
      />
    </div>
  );
}

function NumField({ label, value, onChange }: { label: string; value: number; onChange: (n: number) => void }) {
  return (
    <div className="field">
      <label>{label}</label>
      <input type="number" value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  );
}

function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }): ReactNode {
  return (
    <label className="svcs">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}
