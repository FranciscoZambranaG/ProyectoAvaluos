import { useEffect, useMemo, useState } from "react";
import { api, mediaUrl } from "../lib/api";

type ValueRow = {
  group_id: string;
  group_code: string;
  group_name: string;
  group_sort: number;
  option_id: string;
  option_code: string;
  option_label: string;
  option_sort: number;
  base_score: number;
  is_active: boolean;
  image_url?: string | null;
};

const PAGE_SIZES = [10, 20, 50, 100] as const;

export function AdminValuesPage() {
  const [rows, setRows] = useState<ValueRow[]>([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [drafts, setDrafts] = useState<Record<string, number>>({});
  const [editing, setEditing] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [pageSize, setPageSize] = useState<number>(10);
  const [page, setPage] = useState(1);

  async function load() {
    const data = await api<ValueRow[]>("/api/v1/admin/characteristic-values", {}, true);
    setRows(data);
    const d: Record<string, number> = {};
    for (const r of data) d[r.option_id] = Number(r.base_score);
    setDrafts(d);
    setEditing({});
  }

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Error"));
  }, []);

  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (r) =>
        r.group_name.toLowerCase().includes(q) ||
        r.option_label.toLowerCase().includes(q),
    );
  }, [rows, filter]);

  const totalPages = Math.max(1, Math.ceil(visible.length / pageSize));
  const pageSafe = Math.min(page, totalPages);
  const pageRows = visible.slice((pageSafe - 1) * pageSize, pageSafe * pageSize);
  const from = visible.length ? (pageSafe - 1) * pageSize + 1 : 0;
  const to = Math.min(pageSafe * pageSize, visible.length);

  useEffect(() => {
    setPage(1);
  }, [filter, pageSize]);

  async function save(optionId: string) {
    setError("");
    setLoading(true);
    try {
      await api(`/api/v1/admin/characteristic-values/${optionId}`, {
        method: "PUT",
        body: JSON.stringify({ base_score: drafts[optionId] ?? 0 }),
      }, true);
      setMsg("Valor actualizado");
      setEditing((prev) => ({ ...prev, [optionId]: false }));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  async function onEditToggle(optionId: string) {
    if (editing[optionId]) {
      await save(optionId);
      return;
    }
    setEditing((prev) => ({ ...prev, [optionId]: true }));
    setMsg("");
  }

  function Pager() {
    return (
      <div className="pager">
        <div className="field" style={{ margin: 0, minWidth: 110 }}>
          <label>Por página</label>
          <select value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))}>
            {PAGE_SIZES.map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>
        <div className="pager__nav">
          <button type="button" className="btn btn-out" disabled={pageSafe <= 1} onClick={() => setPage(pageSafe - 1)}>
            ← Anterior
          </button>
          <span className="pager__meta">
            {from}–{to} de {visible.length} · pág. {pageSafe}/{totalPages}
          </span>
          <button type="button" className="btn btn-out" disabled={pageSafe >= totalPages} onClick={() => setPage(pageSafe + 1)}>
            Siguiente →
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <h2>Administración · Valores parametrizados</h2>
      <p className="muted">
        Puntaje base por subtipo. Pulse Editar para modificar el valor; Guardar confirma los cambios.
      </p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="hint">{msg}</div>}

      <div className="field" style={{ maxWidth: 360, marginBottom: ".85rem" }}>
        <label>Buscar</label>
        <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Tipo o subtipo…" />
      </div>

      <Pager />

      <div className="table-wrap" style={{ marginTop: ".75rem" }}>
        <table>
          <thead>
            <tr>
              <th>Tipo</th>
              <th>Subtipo</th>
              <th>Orden</th>
              <th>Imagen</th>
              <th>Valor</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map((r) => {
              const isEditing = Boolean(editing[r.option_id]);
              return (
                <tr key={r.option_id}>
                  <td>{r.group_name}</td>
                  <td>{r.option_label}</td>
                  <td>{r.option_sort}</td>
                  <td>
                    {r.image_url ? (
                      <img src={mediaUrl(r.image_url)} alt="" style={{ width: 48, height: 36, objectFit: "cover", borderRadius: 6 }} />
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.0001"
                      style={{ width: 100 }}
                      disabled={!isEditing || loading}
                      value={drafts[r.option_id] ?? 0}
                      onChange={(e) => setDrafts({ ...drafts, [r.option_id]: Number(e.target.value) })}
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      className={isEditing ? "btn btn-primary" : "btn btn-out"}
                      style={{ padding: ".3rem .6rem" }}
                      disabled={loading}
                      onClick={() => onEditToggle(r.option_id)}
                    >
                      {isEditing ? "Guardar" : "Editar"}
                    </button>
                  </td>
                </tr>
              );
            })}
            {!pageRows.length && (
              <tr><td colSpan={6} className="muted">Sin resultados</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
