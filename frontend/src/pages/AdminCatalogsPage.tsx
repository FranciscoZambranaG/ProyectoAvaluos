import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api } from "../lib/api";

type CatalogType = {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
  items_count: number;
};

type CatalogItem = {
  id: string;
  catalog_type_id: string;
  type_code: string;
  code: string;
  label: string;
  sort_order: number;
  numeric_value?: number | null;
  attributes_json: Record<string, unknown>;
  description?: string | null;
  is_active: boolean;
};

const HINTS: Record<string, string> = {
  zone_homogeneous: "Valor catastral por m² de cada zona homogénea (Vb).",
  utility_service: "Factores IPIU. Se suman al mínimo 1,00 según servicios presentes.",
  ipes_factor: "Factores IPES. Se suman al mínimo 1,00 según equipamiento de la zona.",
  topography: "IPRT — un solo factor de relieve topográfico.",
  road_material: "IPV — un solo factor según material de la vía.",
  construction_typology: "Tipología según puntaje mínimo → valor Bs/m².",
  land_use: "Coeficiente de uso del bloque.",
  depreciation: "Coeficiente de depreciación por antigüedad.",
  parcel_location: "Ubicación en manzana (esquina, medio, pasaje).",
  parcel_shape: "Forma del predio (regular / irregular).",
};

const FACTOR_TYPES = new Set(["utility_service", "ipes_factor"]);

export function AdminCatalogsPage() {
  const [types, setTypes] = useState<CatalogType[]>([]);
  const [typeCode, setTypeCode] = useState("");
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState<Record<string, boolean>>({});
  const [drafts, setDrafts] = useState<Record<string, { label: string; numeric_value: number; is_active: boolean }>>({});
  const [create, setCreate] = useState({ label: "", numeric_value: 0, sort_order: 0 });

  const selected = useMemo(() => types.find((t) => t.code === typeCode) || null, [types, typeCode]);
  const valueLabel = selected && FACTOR_TYPES.has(selected.code) ? "Coeficiente" : "Valor / coeficiente";

  async function loadTypes() {
    const rows = await api<CatalogType[]>("/api/v1/admin/catalogs", {}, true);
    setTypes(rows);
    if (!typeCode && rows[0]) setTypeCode(rows[0].code);
  }

  async function loadItems(code: string) {
    if (!code) return;
    const rows = await api<CatalogItem[]>(`/api/v1/admin/catalogs/${code}/items`, {}, true);
    setItems(rows);
    const d: Record<string, { label: string; numeric_value: number; is_active: boolean }> = {};
    for (const r of rows) {
      d[r.id] = {
        label: r.label,
        numeric_value: Number(r.numeric_value ?? 0),
        is_active: r.is_active,
      };
    }
    setDrafts(d);
    setEditing({});
  }

  useEffect(() => {
    loadTypes().catch((e) => setError(e instanceof Error ? e.message : "Error"));
  }, []);

  useEffect(() => {
    if (typeCode) loadItems(typeCode).catch((e) => setError(e instanceof Error ? e.message : "Error"));
  }, [typeCode]);

  async function saveItem(id: string) {
    const row = items.find((r) => r.id === id);
    const d = drafts[id];
    if (!row || !d || !selected) return;
    setLoading(true);
    setError("");
    try {
      const attrs =
        FACTOR_TYPES.has(selected.code)
          ? { ...row.attributes_json, coeficiente: d.numeric_value }
          : row.attributes_json;
      await api(`/api/v1/admin/catalogs/${selected.code}/items/${id}`, {
        method: "PUT",
        body: JSON.stringify({
          code: row.code,
          label: d.label,
          sort_order: row.sort_order,
          numeric_value: d.numeric_value,
          attributes_json: attrs,
          is_active: d.is_active,
        }),
      }, true);
      setMsg("Ítem actualizado");
      setEditing((prev) => ({ ...prev, [id]: false }));
      await loadItems(selected.code);
      await loadTypes();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar");
    } finally {
      setLoading(false);
    }
  }

  async function onEditToggle(id: string) {
    if (editing[id]) {
      await saveItem(id);
      return;
    }
    setEditing((prev) => ({ ...prev, [id]: true }));
    setMsg("");
  }

  async function createItem(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setLoading(true);
    setError("");
    try {
      const attrs = FACTOR_TYPES.has(selected.code)
        ? { coeficiente: create.numeric_value }
        : {};
      await api(`/api/v1/admin/catalogs/${selected.code}/items`, {
        method: "POST",
        body: JSON.stringify({
          label: create.label,
          numeric_value: create.numeric_value,
          sort_order: create.sort_order || items.length + 1,
          attributes_json: attrs,
          is_active: true,
        }),
      }, true);
      setCreate({ label: "", numeric_value: 0, sort_order: 0 });
      setMsg("Ítem creado");
      await loadItems(selected.code);
      await loadTypes();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <h2>Administración · Catálogos parametrizados</h2>
      <p className="muted">
        Zonas, IPIU, IPES, IPRT, IPV, tipologías y coeficientes. Pulse Editar para modificar etiqueta y valor; Guardar confirma los cambios.
      </p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="hint">{msg}</div>}

      <div className="admin-grid" style={{ gridTemplateColumns: "1fr 2fr" }}>
        <section className="card">
          <strong>Catálogos</strong>
          <ul className="admin-list" style={{ marginTop: ".6rem" }}>
            {types.map((t) => (
              <li key={t.id}>
                <button type="button" className={t.code === typeCode ? "on" : ""} onClick={() => setTypeCode(t.code)}>
                  <span>{t.name}</span>
                  <small className="muted">{t.items_count}</small>
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className="card">
          {!selected ? (
            <p className="muted">Seleccione un catálogo</p>
          ) : (
            <>
              <strong>{selected.name}</strong>
              <p className="muted" style={{ fontSize: ".85rem" }}>
                {HINTS[selected.code] || selected.name}
              </p>

              <div className="table-wrap" style={{ marginTop: ".75rem" }}>
                <table>
                  <thead>
                    <tr>
                      <th>Etiqueta</th>
                      <th>{valueLabel}</th>
                      <th>Activo</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((r) => {
                      const d = drafts[r.id] || { label: r.label, numeric_value: 0, is_active: true };
                      const isEditing = Boolean(editing[r.id]);
                      return (
                        <tr key={r.id}>
                          <td>
                            <input
                              value={d.label}
                              disabled={!isEditing || loading}
                              onChange={(e) => setDrafts({ ...drafts, [r.id]: { ...d, label: e.target.value } })}
                            />
                          </td>
                          <td>
                            <input
                              type="number"
                              step="0.01"
                              value={d.numeric_value}
                              disabled={!isEditing || loading}
                              onChange={(e) => setDrafts({ ...drafts, [r.id]: { ...d, numeric_value: Number(e.target.value) } })}
                            />
                          </td>
                          <td>
                            <input
                              type="checkbox"
                              checked={d.is_active}
                              disabled={!isEditing || loading}
                              onChange={(e) => setDrafts({ ...drafts, [r.id]: { ...d, is_active: e.target.checked } })}
                            />
                          </td>
                          <td>
                            <button
                              type="button"
                              className={isEditing ? "btn btn-primary" : "btn btn-out"}
                              disabled={loading}
                              onClick={() => void onEditToggle(r.id)}
                            >
                              {isEditing ? "Guardar" : "Editar"}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <form onSubmit={createItem} className="grid2" style={{ marginTop: "1rem" }}>
                <div className="field">
                  <label>Etiqueta *</label>
                  <input required value={create.label} onChange={(e) => setCreate({ ...create, label: e.target.value })} />
                </div>
                <div className="field">
                  <label>{valueLabel}</label>
                  <input
                    type="number"
                    step="0.01"
                    value={create.numeric_value}
                    onChange={(e) => setCreate({ ...create, numeric_value: Number(e.target.value) })}
                  />
                </div>
                <div className="hint" style={{ gridColumn: "1 / -1" }}>
                  El código se genera automáticamente.
                </div>
                <div className="actions" style={{ alignSelf: "end" }}>
                  <button className="btn btn-primary" disabled={loading} type="submit">Agregar ítem</button>
                </div>
              </form>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
