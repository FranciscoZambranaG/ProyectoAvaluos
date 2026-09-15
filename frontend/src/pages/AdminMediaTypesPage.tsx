import { useEffect, useState, type FormEvent } from "react";
import { api } from "../lib/api";

type MediaType = {
  id: string;
  code: string;
  name: string;
  category: string;
  sort_order: number;
  is_active: boolean;
};

export function AdminMediaTypesPage() {
  const [rows, setRows] = useState<MediaType[]>([]);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const [create, setCreate] = useState({ name: "", code: "", sort_order: 0 });
  const [editing, setEditing] = useState<Record<string, { name: string; sort_order: number; is_active: boolean }>>({});

  async function load() {
    const data = await api<MediaType[]>("/api/v1/admin/media-types?category=photo", {}, true);
    setRows(data);
  }

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Error al cargar"));
  }, []);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api(
        "/api/v1/admin/media-types",
        {
          method: "POST",
          body: JSON.stringify({
            name: create.name,
            code: create.code || undefined,
            category: "photo",
            sort_order: create.sort_order || rows.length * 10 + 10,
            is_active: true,
          }),
        },
        true,
      );
      setCreate({ name: "", code: "", sort_order: 0 });
      setMsg("Tipo de fotografía creado");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear");
    } finally {
      setLoading(false);
    }
  }

  async function save(id: string) {
    const row = rows.find((r) => r.id === id);
    const d = editing[id];
    if (!row || !d) return;
    setLoading(true);
    setError("");
    try {
      await api(
        `/api/v1/admin/media-types/${id}`,
        {
          method: "PUT",
          body: JSON.stringify({
            code: row.code,
            name: d.name,
            category: row.category,
            sort_order: d.sort_order,
            is_active: d.is_active,
          }),
        },
        true,
      );
      setEditing((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      setMsg("Tipo actualizado");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar");
    } finally {
      setLoading(false);
    }
  }

  async function deactivate(id: string) {
    setLoading(true);
    setError("");
    try {
      await api(`/api/v1/admin/media-types/${id}`, { method: "DELETE" }, true);
      setMsg("Tipo desactivado (deja de aparecer en el formulario)");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo desactivar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <h1>Tipos de fotografía</h1>
      <p className="muted">
        Estos tipos aparecen en el paso Fotografías del formulario. Puede crear, renombrar u ocultar opciones
        (frente, laterales, cubierta, etc.).
      </p>
      {error && <p className="error">{error}</p>}
      {msg && <div className="hint">{msg}</div>}

      <form onSubmit={onCreate} className="grid2" style={{ margin: "1rem 0" }}>
        <div className="field">
          <label>Nombre *</label>
          <input required value={create.name} onChange={(e) => setCreate({ ...create, name: e.target.value })} placeholder="Foto patio" />
        </div>
        <div className="field">
          <label>Código (opcional)</label>
          <input value={create.code} onChange={(e) => setCreate({ ...create, code: e.target.value })} placeholder="photo_patio" />
        </div>
        <div className="actions" style={{ gridColumn: "1 / -1" }}>
          <button className="btn btn-primary" disabled={loading} type="submit">
            Agregar tipo
          </button>
        </div>
      </form>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Código</th>
              <th>Orden</th>
              <th>Estado</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const d = editing[r.id];
              const on = Boolean(d);
              return (
                <tr key={r.id}>
                  <td>
                    {on ? (
                      <input value={d.name} onChange={(e) => setEditing({ ...editing, [r.id]: { ...d, name: e.target.value } })} />
                    ) : (
                      r.name
                    )}
                  </td>
                  <td>
                    <code>{r.code}</code>
                  </td>
                  <td>
                    {on ? (
                      <input
                        type="number"
                        value={d.sort_order}
                        onChange={(e) => setEditing({ ...editing, [r.id]: { ...d, sort_order: Number(e.target.value) } })}
                      />
                    ) : (
                      r.sort_order
                    )}
                  </td>
                  <td>{r.is_active ? "Activo" : "Oculto"}</td>
                  <td>
                    <div className="actions">
                      {on ? (
                        <button type="button" className="btn btn-primary" disabled={loading} onClick={() => void save(r.id)}>
                          Guardar
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="btn btn-out"
                          onClick={() =>
                            setEditing({
                              ...editing,
                              [r.id]: { name: r.name, sort_order: r.sort_order, is_active: r.is_active },
                            })
                          }
                        >
                          Editar
                        </button>
                      )}
                      {r.is_active ? (
                        <button type="button" className="btn btn-out" disabled={loading} onClick={() => void deactivate(r.id)}>
                          Ocultar
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="btn btn-out"
                          disabled={loading}
                          onClick={() => {
                            setEditing({
                              ...editing,
                              [r.id]: { name: r.name, sort_order: r.sort_order, is_active: true },
                            });
                            void (async () => {
                              setLoading(true);
                              setError("");
                              try {
                                await api(
                                  `/api/v1/admin/media-types/${r.id}`,
                                  {
                                    method: "PUT",
                                    body: JSON.stringify({
                                      code: r.code,
                                      name: r.name,
                                      category: r.category,
                                      sort_order: r.sort_order,
                                      is_active: true,
                                    }),
                                  },
                                  true,
                                );
                                setMsg("Tipo activado");
                                await load();
                              } catch (err) {
                                setError(err instanceof Error ? err.message : "No se pudo activar");
                              } finally {
                                setLoading(false);
                              }
                            })();
                          }}
                        >
                          Activar
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
