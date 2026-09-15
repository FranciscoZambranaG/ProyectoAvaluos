import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { DecimalInput } from "../components/DecimalInput";
import { api } from "../lib/api";

type CatalogItem = {
  id: string;
  code: string;
  label: string;
  sort_order: number;
  numeric_value?: number | null;
  attributes_json: Record<string, unknown>;
  is_active: boolean;
};

type Param = {
  key: string;
  value_json: unknown;
  description?: string | null;
};

type Props = {
  catalogCode: "utility_service" | "ipes_factor";
  title: string;
  subtitle: string;
  baseParamKey: "ipiu_base" | "ipes_base";
  baseLabel: string;
};

export function AdminFactorCatalogPage({ catalogCode, title, subtitle, baseParamKey, baseLabel }: Props) {
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [baseValue, setBaseValue] = useState<number>(1);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, { label: string; numeric_value: number; is_active: boolean }>>({});
  const [create, setCreate] = useState({ code: "", label: "", numeric_value: 0.05, sort_order: 0 });

  async function load() {
    const [rows, params] = await Promise.all([
      api<CatalogItem[]>(`/api/v1/admin/catalogs/${catalogCode}/items`, {}, true),
      api<Param[]>("/api/v1/admin/parameters", {}, true),
    ]);
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
    const base = params.find((p) => p.key === baseParamKey);
    const raw = base?.value_json;
    const n = typeof raw === "number" ? raw : Number(raw);
    setBaseValue(Number.isFinite(n) ? n : 1);
  }

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Error al cargar"));
  }, [catalogCode, baseParamKey]);

  async function saveBase() {
    setLoading(true);
    setError("");
    try {
      await api(
        `/api/v1/admin/parameters/${baseParamKey}`,
        { method: "PUT", body: JSON.stringify({ value_json: baseValue }) },
        true,
      );
      setMsg(`${baseLabel} actualizado`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar la base");
    } finally {
      setLoading(false);
    }
  }

  async function saveItem(id: string) {
    const row = items.find((r) => r.id === id);
    const d = drafts[id];
    if (!row || !d) return;
    setLoading(true);
    setError("");
    try {
      await api(
        `/api/v1/admin/catalogs/${catalogCode}/items/${id}`,
        {
          method: "PUT",
          body: JSON.stringify({
            code: row.code,
            label: d.label,
            sort_order: row.sort_order,
            numeric_value: d.numeric_value,
            attributes_json: { ...row.attributes_json, coeficiente: d.numeric_value },
            is_active: d.is_active,
          }),
        },
        true,
      );
      setMsg("Factor actualizado");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar");
    } finally {
      setLoading(false);
    }
  }

  async function createItem(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api(
        `/api/v1/admin/catalogs/${catalogCode}/items`,
        {
          method: "POST",
          body: JSON.stringify({
            code: create.code || undefined,
            label: create.label,
            numeric_value: create.numeric_value,
            sort_order: create.sort_order || items.length + 1,
            attributes_json: { coeficiente: create.numeric_value },
            is_active: true,
          }),
        },
        true,
      );
      setCreate({ code: "", label: "", numeric_value: 0.05, sort_order: 0 });
      setMsg("Factor creado");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <h2>{title}</h2>
      <p className="muted">{subtitle}</p>
      <p className="muted" style={{ fontSize: ".85rem" }}>
        También disponible en{" "}
        <Link to="/app/admin/catalogos">Catálogos / índices</Link> y el factor base en{" "}
        <Link to="/app/admin/parametros">Parámetros</Link>.
      </p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="hint">{msg}</div>}

      <section className="card" style={{ marginBottom: "1rem" }}>
        <strong>{baseLabel}</strong>
        <p className="muted" style={{ fontSize: ".85rem" }}>
          Índice = base + suma de factores marcados en el predio. Por defecto 1,00.
        </p>
        <div className="grid2" style={{ marginTop: ".75rem", alignItems: "end" }}>
          <div className="field">
            <label>Valor base</label>
            <DecimalInput value={baseValue} onChange={(n) => setBaseValue(n ?? 1)} />
          </div>
          <div className="actions">
            <button type="button" className="btn btn-primary" disabled={loading} onClick={() => void saveBase()}>
              Guardar base
            </button>
          </div>
        </div>
      </section>

      <section className="card">
        <strong>Factores parametrizables</strong>
        <div className="table-wrap" style={{ marginTop: ".75rem" }}>
          <table>
            <thead>
              <tr>
                <th>Código</th>
                <th>Etiqueta</th>
                <th>Coeficiente</th>
                <th>Activo</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => {
                const d = drafts[r.id] || { label: r.label, numeric_value: 0, is_active: true };
                return (
                  <tr key={r.id}>
                    <td>
                      <code>{r.code}</code>
                    </td>
                    <td>
                      <input
                        value={d.label}
                        onChange={(e) => setDrafts({ ...drafts, [r.id]: { ...d, label: e.target.value } })}
                      />
                    </td>
                    <td>
                      <DecimalInput
                        value={d.numeric_value}
                        onChange={(n) => setDrafts({ ...drafts, [r.id]: { ...d, numeric_value: n ?? 0 } })}
                      />
                    </td>
                    <td>
                      <input
                        type="checkbox"
                        checked={d.is_active}
                        onChange={(e) => setDrafts({ ...drafts, [r.id]: { ...d, is_active: e.target.checked } })}
                      />
                    </td>
                    <td>
                      <button type="button" className="btn btn-out" disabled={loading} onClick={() => void saveItem(r.id)}>
                        Guardar
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
            <label>Código</label>
            <input value={create.code} onChange={(e) => setCreate({ ...create, code: e.target.value })} placeholder="auto si vacío" />
          </div>
          <div className="field">
            <label>Etiqueta *</label>
            <input required value={create.label} onChange={(e) => setCreate({ ...create, label: e.target.value })} />
          </div>
          <div className="field">
            <label>Coeficiente *</label>
            <DecimalInput
              required
              value={create.numeric_value}
              onChange={(n) => setCreate({ ...create, numeric_value: n ?? 0 })}
            />
          </div>
          <div className="actions" style={{ gridColumn: "1 / -1" }}>
            <button className="btn btn-primary" disabled={loading} type="submit">
              Agregar factor
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export function AdminIpiuPage() {
  return (
    <AdminFactorCatalogPage
      catalogCode="utility_service"
      title="Administración · IPIU — Infraestructura urbana"
      subtitle="Factores que se suman al índice ponderado de infraestructura urbana (agua, alcantarillado, energía, etc.)."
      baseParamKey="ipiu_base"
      baseLabel="Base IPIU"
    />
  );
}

export function AdminIpesPage() {
  return (
    <AdminFactorCatalogPage
      catalogCode="ipes_factor"
      title="Administración · IPES — Equipamiento social"
      subtitle="Factores que se suman al índice ponderado de equipamiento social (salud, educación, comercio, etc.)."
      baseParamKey="ipes_base"
      baseLabel="Base IPES"
    />
  );
}
