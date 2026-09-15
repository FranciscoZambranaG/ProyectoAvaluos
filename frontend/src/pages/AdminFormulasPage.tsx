import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api } from "../lib/api";

type FormulaVersion = {
  id: string;
  version: number;
  expression: string;
  variables_json: Record<string, unknown>;
  fiscal_year?: number | null;
  is_active: boolean;
  notes?: string | null;
};

type Formula = {
  id: string;
  code: string;
  name: string;
  description?: string | null;
  output_type: string;
  is_active: boolean;
  versions: FormulaVersion[];
};

type VarRow = { key: string; source: string };

/** Etiquetas en español para variables técnicas */
const VAR_LABELS: Record<string, string> = {
  land_value: "Valor del terreno",
  blocks_value: "Valor de los bloques",
  improvements_value: "Valor de las mejoras",
  ipiu: "IPIU infraestructura urbana",
  ipes: "IPES equipamiento social",
  iprt: "IPRT relieve topográfico",
  ipv: "IPV calidad de vía",
  zone_m2: "Valor bruto de zona (Vb)",
  location_coef: "Ubicación en manzana",
  shape_coef: "Forma del predio",
  base_score: "Puntaje base del material",
  percentage: "Porcentaje declarado",
  total_score: "Puntaje total del bloque",
  area: "Superficie (m²)",
  approved_area: "Superficie aprobada (m²)",
  "appraisal.land_value": "Valor del terreno del avalúo",
  "appraisal.blocks_value": "Valor de bloques del avalúo",
  "appraisal.improvements_value": "Valor de mejoras del avalúo",
  "characteristic_option.base_score": "Puntaje base del catálogo",
  "unit_characteristic_value.percentage": "Porcentaje de la característica",
  "construction_unit.characteristic_values": "Características del bloque",
  "construction_unit.total_score": "Puntaje acumulado del bloque",
  "construction_unit.area": "Superficie del bloque o mejora",
  "property_details.approved_area": "Área aprobada del predio",
  "catalog.zone_homogeneous": "Zona homogénea",
  "catalog.topography": "Topografía",
  "catalog.parcel_shape": "Forma del predio",
  "catalog.parcel_location": "Ubicación del predio",
  "catalog.road_material": "Material de vía",
  "catalog.land_use": "Uso del suelo",
  "catalog.depreciation": "Depreciación",
  "catalog.construction_typology": "Tipología constructiva",
  "catalog.improvement_typology": "Tipología de mejora",
  property_services: "Servicios básicos",
  unit_characteristic_values: "Puntajes de características",
  catalog: "Catálogo de tipologías",
};

const SOURCE_OPTIONS = Object.entries(VAR_LABELS).map(([value, label]) => ({ value, label }));

function labelOf(key: string) {
  return VAR_LABELS[key] || key.replace(/_/g, " ");
}

function friendlyExpression(expr: string) {
  let out = expr;
  const keys = Object.keys(VAR_LABELS).sort((a, b) => b.length - a.length);
  for (const k of keys) {
    out = out.replaceAll(k, labelOf(k));
  }
  return out;
}

export function AdminFormulasPage() {
  const [rows, setRows] = useState<Formula[]>([]);
  const [formulaId, setFormulaId] = useState("");
  const [meta, setMeta] = useState({ name: "", description: "", is_active: true });
  const [expression, setExpression] = useState("");
  const [varRows, setVarRows] = useState<VarRow[]>([]);
  const [notes, setNotes] = useState("");
  const [fiscalYear, setFiscalYear] = useState<number | "">(2026);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  const selected = useMemo(() => rows.find((r) => r.id === formulaId) || null, [rows, formulaId]);

  async function load() {
    const list = await api<Formula[]>("/api/v1/admin/formulas", {}, true);
    setRows(list);
    if (!formulaId && list[0]) setFormulaId(list[0].id);
  }

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Error"));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setMeta({ name: selected.name, description: selected.description || "", is_active: selected.is_active });
    const active = selected.versions.find((v) => v.is_active) || selected.versions[0];
    if (active) {
      setExpression(active.expression);
      setVarRows(
        Object.entries(active.variables_json || {}).map(([key, source]) => ({
          key,
          source: String(source),
        })),
      );
      setNotes(active.notes || "");
      setFiscalYear(active.fiscal_year ?? 2026);
    } else {
      setExpression("");
      setVarRows([]);
    }
  }, [selected]);

  async function saveMeta(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setLoading(true);
    setError("");
    try {
      await api(`/api/v1/admin/formulas/${selected.id}`, {
        method: "PUT",
        body: JSON.stringify(meta),
      }, true);
      setMsg("Datos de la fórmula guardados");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  async function publishVersion(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setLoading(true);
    setError("");
    try {
      const variables_json: Record<string, string> = {};
      for (const row of varRows) {
        if (!row.key.trim()) continue;
        variables_json[row.key.trim()] = row.source.trim();
      }
      await api(`/api/v1/admin/formulas/${selected.id}/versions`, {
        method: "POST",
        body: JSON.stringify({
          expression,
          variables_json,
          fiscal_year: fiscalYear === "" ? null : Number(fiscalYear),
          notes: notes || null,
          is_active: true,
        }),
      }, true);
      setMsg("Nueva versión publicada");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo publicar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <h2>Administración · Fórmulas</h2>
      <p className="muted">Cómo se calculan los valores del avalúo: terreno, bloques, mejoras y total.</p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="hint">{msg}</div>}

      <div className="admin-grid" style={{ gridTemplateColumns: "1fr 1.8fr" }}>
        <section className="card">
          <strong>Fórmulas</strong>
          <ul className="admin-list" style={{ marginTop: ".6rem" }}>
            {rows.map((f) => (
              <li key={f.id}>
                <button type="button" className={f.id === formulaId ? "on" : ""} onClick={() => setFormulaId(f.id)}>
                  <span>{f.name}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className="card">
          {!selected ? (
            <p className="muted">Seleccione una fórmula</p>
          ) : (
            <>
              <form onSubmit={saveMeta} className="admin-form">
                <div className="field">
                  <label>Nombre</label>
                  <input value={meta.name} onChange={(e) => setMeta({ ...meta, name: e.target.value })} />
                </div>
                <div className="field">
                  <label>Descripción (en lenguaje claro)</label>
                  <textarea
                    rows={3}
                    value={meta.description}
                    onChange={(e) => setMeta({ ...meta, description: e.target.value })}
                    placeholder="Explique qué calcula esta fórmula…"
                  />
                </div>
                <label className="svcs">
                  <input type="checkbox" checked={meta.is_active} onChange={(e) => setMeta({ ...meta, is_active: e.target.checked })} />
                  Fórmula activa
                </label>
                <button className="btn btn-out" disabled={loading} type="submit">Guardar datos</button>
              </form>

              <hr style={{ border: 0, borderTop: "1px solid var(--line)", margin: "1rem 0" }} />

              <form onSubmit={publishVersion} className="admin-form">
                <strong>Nueva versión del cálculo</strong>
                <div className="field">
                  <label>Fórmula / expresión</label>
                  <textarea rows={3} value={expression} onChange={(e) => setExpression(e.target.value)} />
                  {expression && (
                    <p className="muted" style={{ fontSize: ".82rem", margin: ".35rem 0 0" }}>
                      En palabras: {friendlyExpression(expression)}
                    </p>
                  )}
                </div>

                <div>
                  <strong style={{ fontSize: ".9rem" }}>Datos que usa la fórmula</strong>
                  <p className="muted" style={{ fontSize: ".82rem" }}>
                    Cada fila indica qué dato del sistema alimenta la fórmula.
                  </p>
                  <div className="admin-form" style={{ marginTop: ".4rem" }}>
                    {varRows.map((row, idx) => (
                      <div key={idx} className="grid2" style={{ alignItems: "end" }}>
                        <div className="field">
                          <label>Nombre en la fórmula</label>
                          <input
                            value={row.key}
                            onChange={(e) => {
                              const next = [...varRows];
                              next[idx] = { ...row, key: e.target.value };
                              setVarRows(next);
                            }}
                          />
                          <span className="muted" style={{ fontSize: ".75rem" }}>{labelOf(row.key)}</span>
                        </div>
                        <div className="field">
                          <label>Origen del dato</label>
                          <select
                            value={SOURCE_OPTIONS.some((o) => o.value === row.source) ? row.source : "__custom__"}
                            onChange={(e) => {
                              const next = [...varRows];
                              const v = e.target.value === "__custom__" ? row.source : e.target.value;
                              next[idx] = { ...row, source: v };
                              setVarRows(next);
                            }}
                          >
                            {SOURCE_OPTIONS.map((o) => (
                              <option key={o.value} value={o.value}>{o.label}</option>
                            ))}
                            <option value="__custom__">Otro…</option>
                          </select>
                          {!SOURCE_OPTIONS.some((o) => o.value === row.source) && (
                            <input
                              style={{ marginTop: ".35rem" }}
                              value={row.source}
                              onChange={(e) => {
                                const next = [...varRows];
                                next[idx] = { ...row, source: e.target.value };
                                setVarRows(next);
                              }}
                            />
                          )}
                        </div>
                        <button
                          type="button"
                          className="btn btn-out"
                          style={{ padding: ".35rem .6rem", gridColumn: "1 / -1", justifySelf: "start" }}
                          onClick={() => setVarRows(varRows.filter((_, i) => i !== idx))}
                        >
                          Quitar dato
                        </button>
                      </div>
                    ))}
                    <button
                      type="button"
                      className="btn btn-out"
                      onClick={() => setVarRows([...varRows, { key: "", source: "appraisal.land_value" }])}
                    >
                      Agregar dato
                    </button>
                  </div>
                </div>

                <div className="field">
                  <label>Gestión / año fiscal</label>
                  <input type="number" value={fiscalYear} onChange={(e) => setFiscalYear(e.target.value === "" ? "" : Number(e.target.value))} />
                </div>
                <div className="field">
                  <label>Notas</label>
                  <input value={notes} onChange={(e) => setNotes(e.target.value)} />
                </div>
                <button className="btn btn-primary" disabled={loading} type="submit">Publicar versión</button>
              </form>

              <div style={{ marginTop: "1rem" }}>
                <strong>Historial de versiones</strong>
                <ul className="admin-rules">
                  {selected.versions.map((v) => (
                    <li key={v.id} style={{ flexDirection: "column", alignItems: "stretch" }}>
                      <span>Versión {v.version}{v.is_active ? " · vigente" : ""} · gestión {v.fiscal_year ?? "—"}</span>
                      <span className="muted" style={{ fontSize: ".8rem" }}>{friendlyExpression(v.expression)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
