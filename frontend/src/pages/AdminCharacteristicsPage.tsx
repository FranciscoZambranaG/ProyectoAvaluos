import { useEffect, useMemo, useRef, useState, type DragEvent, type FormEvent } from "react";
import { api, mediaUrl } from "../lib/api";

type Group = {
  id: string;
  code: string;
  name: string;
  sort_order: number;
  applies_to: string;
  max_percent: number;
  is_active: boolean;
  options_count: number;
};

type OrderRule = {
  id: string;
  option_id: string;
  sort_order: number;
  year_from: number;
  year_to?: number | null;
  notes?: string | null;
  is_active: boolean;
};

type Option = {
  id: string;
  group_id: string;
  code: string;
  label: string;
  description?: string | null;
  sort_order: number;
  base_score: number;
  is_active: boolean;
  image_url?: string | null;
  order_rules: OrderRule[];
};

type ModalKind = "type-create" | "type-edit" | "subtype-create" | "subtype-edit" | null;

const APPLIES_LABEL: Record<string, string> = {
  block: "Bloque",
  improvement: "Mejora",
  both: "Bloque y mejora",
};

function moveItem<T extends { id: string }>(list: T[], fromId: string, toId: string): T[] {
  const from = list.findIndex((x) => x.id === fromId);
  const to = list.findIndex((x) => x.id === toId);
  if (from < 0 || to < 0 || from === to) return list;
  const next = [...list];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

export function AdminCharacteristicsPage() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [groupId, setGroupId] = useState("");
  const [options, setOptions] = useState<Option[]>([]);
  const [optionId, setOptionId] = useState("");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const uploadingRef = useRef(false);
  const [modal, setModal] = useState<ModalKind>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dropTargetId, setDropTargetId] = useState<string | null>(null);

  const [typeForm, setTypeForm] = useState({
    name: "",
    sort_order: 0,
    applies_to: "block",
    max_percent: 100,
    is_active: true,
  });
  const [optForm, setOptForm] = useState({
    label: "",
    description: "",
    sort_order: 0,
    is_active: true,
  });
  const [ruleForm, setRuleForm] = useState({
    sort_order: 2,
    year_from: 2011,
    year_to: "" as string | number,
    notes: "",
  });

  const selected = useMemo(() => options.find((o) => o.id === optionId) || null, [options, optionId]);
  const selectedGroup = useMemo(() => groups.find((g) => g.id === groupId) || null, [groups, groupId]);

  async function loadGroups() {
    const rows = await api<Group[]>("/api/v1/admin/characteristic-groups", {}, true);
    setGroups(rows);
    if (!groupId && rows[0]) setGroupId(rows[0].id);
    else if (groupId && !rows.some((g) => g.id === groupId) && rows[0]) setGroupId(rows[0].id);
  }

  async function loadOptions(gid: string) {
    if (!gid) return;
    const rows = await api<Option[]>(`/api/v1/admin/characteristic-groups/${gid}/options`, {}, true);
    setOptions(rows);
    if (rows.length && !rows.some((o) => o.id === optionId)) setOptionId(rows[0].id);
    if (!rows.length) setOptionId("");
  }

  useEffect(() => {
    loadGroups().catch((e) => setError(e instanceof Error ? e.message : "Error"));
  }, []);

  useEffect(() => {
    if (!groupId) return;
    loadOptions(groupId).catch((e) => setError(e instanceof Error ? e.message : "Error"));
  }, [groupId]);

  function openCreateType() {
    setTypeForm({
      name: "",
      sort_order: (groups.length + 1) * 10,
      applies_to: "block",
      max_percent: 100,
      is_active: true,
    });
    setModal("type-create");
  }

  function openEditType() {
    if (!selectedGroup) return;
    setTypeForm({
      name: selectedGroup.name,
      sort_order: selectedGroup.sort_order,
      applies_to: selectedGroup.applies_to || "block",
      max_percent: Number(selectedGroup.max_percent ?? 100),
      is_active: selectedGroup.is_active,
    });
    setModal("type-edit");
  }

  function openCreateSubtype() {
    setOptForm({ label: "", description: "", sort_order: (options.length + 1) * 10, is_active: true });
    setModal("subtype-create");
  }

  function openEditSubtype() {
    if (!selected) return;
    setOptForm({
      label: selected.label,
      description: selected.description || "",
      sort_order: selected.sort_order,
      is_active: selected.is_active,
    });
    setModal("subtype-edit");
  }

  async function submitType(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const body = {
        name: typeForm.name.trim(),
        sort_order: typeForm.sort_order,
        is_active: typeForm.is_active,
        applies_to: typeForm.applies_to,
        max_percent: Number(typeForm.max_percent),
      };
      if (modal === "type-create") {
        const created = await api<Group>("/api/v1/admin/characteristic-groups", {
          method: "POST",
          body: JSON.stringify(body),
        }, true);
        setMsg(created.is_active ? "Tipo agregado" : "Tipo reactivado");
        setGroupId(created.id);
      } else if (modal === "type-edit" && selectedGroup) {
        await api(`/api/v1/admin/characteristic-groups/${selectedGroup.id}`, {
          method: "PUT",
          body: JSON.stringify(body),
        }, true);
        setMsg("Tipo actualizado");
      }
      setModal(null);
      await loadGroups();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  async function softDeleteType() {
    if (!selectedGroup) return;
    if (!confirm(`¿Eliminar lógicamente el tipo «${selectedGroup.name}»?`)) return;
    setLoading(true);
    setError("");
    try {
      await api(`/api/v1/admin/characteristic-groups/${selectedGroup.id}`, { method: "DELETE" }, true);
      setMsg("Tipo deshabilitado (eliminación lógica)");
      setModal(null);
      await loadGroups();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  async function submitSubtype(e: FormEvent) {
    e.preventDefault();
    if (!groupId) return;
    setLoading(true);
    setError("");
    try {
      const body = {
        label: optForm.label.trim(),
        description: optForm.description || null,
        sort_order: optForm.sort_order,
        is_active: optForm.is_active,
      };
      if (modal === "subtype-create") {
        const created = await api<Option>(`/api/v1/admin/characteristic-groups/${groupId}/options`, {
          method: "POST",
          body: JSON.stringify(body),
        }, true);
        setMsg(created.is_active ? "Subtipo agregado" : "Subtipo reactivado");
        setOptionId(created.id);
      } else if (modal === "subtype-edit" && selected) {
        const updated = await api<Option>(`/api/v1/admin/characteristic-options/${selected.id}`, {
          method: "PUT",
          body: JSON.stringify(body),
        }, true);
        setMsg("Subtipo actualizado");
        setOptionId(updated.id);
      }
      setModal(null);
      await loadOptions(groupId);
      await loadGroups();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  async function softDeleteSubtype() {
    if (!selected) return;
    if (!confirm(`¿Eliminar lógicamente el subtipo «${selected.label}»?`)) return;
    setLoading(true);
    setError("");
    try {
      await api(`/api/v1/admin/characteristic-options/${selected.id}`, { method: "DELETE" }, true);
      setMsg("Subtipo deshabilitado (eliminación lógica)");
      setModal(null);
      await loadOptions(groupId);
      await loadGroups();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  async function persistGroupOrder(ordered: Group[]) {
    setGroups(ordered);
    await api("/api/v1/admin/characteristic-groups/reorder", {
      method: "POST",
      body: JSON.stringify({ ordered_ids: ordered.map((g) => g.id) }),
    }, true);
    await loadGroups();
  }

  async function persistOptionOrder(ordered: Option[]) {
    setOptions(ordered);
    await api(`/api/v1/admin/characteristic-groups/${groupId}/options/reorder`, {
      method: "POST",
      body: JSON.stringify({ ordered_ids: ordered.map((o) => o.id) }),
    }, true);
    await loadOptions(groupId);
  }

  function onDragStart(id: string, e: DragEvent) {
    setDraggingId(id);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", id);
  }

  function onDragOver(id: string, e: DragEvent) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (dropTargetId !== id) setDropTargetId(id);
  }

  async function onDropGroups(targetId: string, e: DragEvent) {
    e.preventDefault();
    const fromId = draggingId || e.dataTransfer.getData("text/plain");
    setDraggingId(null);
    setDropTargetId(null);
    if (!fromId || fromId === targetId) return;
    const ordered = moveItem(groups, fromId, targetId);
    if (ordered === groups) return;
    try {
      await persistGroupOrder(ordered);
      setMsg("Orden de tipos actualizado");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    }
  }

  async function onDropOptions(targetId: string, e: DragEvent) {
    e.preventDefault();
    const fromId = draggingId || e.dataTransfer.getData("text/plain");
    setDraggingId(null);
    setDropTargetId(null);
    if (!fromId || fromId === targetId) return;
    const ordered = moveItem(options, fromId, targetId);
    if (ordered === options) return;
    try {
      await persistOptionOrder(ordered);
      setMsg("Orden de subtipos actualizado");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    }
  }

  function onDragEnd() {
    setDraggingId(null);
    setDropTargetId(null);
  }

  async function uploadImage(file: File) {
    if (!selected || loading || uploadingRef.current) return;
    uploadingRef.current = true;
    setLoading(true);
    setError("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const updated = await api<Option>(
        `/api/v1/admin/characteristic-options/${selected.id}/image`,
        { method: "POST", body: fd },
        true,
      );
      setMsg("Imagen actualizada");
      // Actualizar solo este subtipo (sin reload): conserva ?v= y el nuevo media id.
      setOptions((prev) => prev.map((o) => (o.id === updated.id ? { ...o, ...updated } : o)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      uploadingRef.current = false;
      setLoading(false);
    }
  }

  async function addRule(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setLoading(true);
    setError("");
    try {
      await api(`/api/v1/admin/characteristic-options/${selected.id}/order-rules`, {
        method: "POST",
        body: JSON.stringify({
          sort_order: Number(ruleForm.sort_order),
          year_from: Number(ruleForm.year_from),
          year_to: ruleForm.year_to === "" ? null : Number(ruleForm.year_to),
          notes: ruleForm.notes || null,
          is_active: true,
        }),
      }, true);
      setMsg("Regla de orden por fechas creada");
      await loadOptions(groupId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  async function removeRule(ruleId: string) {
    await api(`/api/v1/admin/order-rules/${ruleId}`, { method: "DELETE" }, true);
    await loadOptions(groupId);
  }

  const modalTitle =
    modal === "type-create"
      ? "Agregar tipo"
      : modal === "type-edit"
        ? "Edición de tipo"
        : modal === "subtype-create"
          ? "Agregar subtipo"
          : modal === "subtype-edit"
            ? "Edición de subtipo"
            : "";

  return (
    <div className="page">
      <h2>Administración · Características</h2>
      <p className="muted">
        Parametrice tipos y subtipos. Arrastre las filas para cambiar el orden en que se muestran. Los valores/puntajes se gestionan en Admin · Valores.
      </p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="hint">{msg}</div>}

      <div className="admin-grid">
        <section className="card">
          <div className="actions" style={{ marginBottom: ".35rem" }}>
            <strong>Tipos</strong>
          </div>
          <p className="muted" style={{ fontSize: ".8rem", margin: "0 0 .45rem" }}>Arrastre para reordenar</p>
          <ul className="admin-list">
            {groups.map((g) => (
              <li
                key={g.id}
                className={`${draggingId === g.id ? "dragging" : ""}${dropTargetId === g.id && draggingId !== g.id ? " drag-over" : ""}`}
                draggable
                onDragStart={(e) => onDragStart(g.id, e)}
                onDragOver={(e) => onDragOver(g.id, e)}
                onDrop={(e) => void onDropGroups(g.id, e)}
                onDragEnd={onDragEnd}
              >
                <span className="admin-list__handle" title="Arrastrar" aria-hidden>⋮⋮</span>
                <button
                  type="button"
                  className={`${g.id === groupId ? "on" : ""}${g.is_active ? "" : " inactive"}`}
                  onClick={() => setGroupId(g.id)}
                >
                  <span>
                    {g.name}
                    {!g.is_active ? " (inactivo)" : ""}
                    <small className="admin-list__meta">{APPLIES_LABEL[g.applies_to] || g.applies_to} · máx. {Number(g.max_percent)}%</small>
                  </span>
                  <em>{g.options_count}</em>
                </button>
              </li>
            ))}
          </ul>
          <div className="actions" style={{ marginTop: ".7rem" }}>
            <button type="button" className="btn btn-primary" onClick={openCreateType}>Agregar tipo</button>
            <button type="button" className="btn btn-out" disabled={!selectedGroup} onClick={openEditType}>Editar</button>
          </div>
        </section>

        <section className="card">
          <div className="actions" style={{ marginBottom: ".35rem" }}>
            <strong>Subtipos</strong>
          </div>
          <p className="muted" style={{ fontSize: ".8rem", margin: "0 0 .45rem" }}>Arrastre para reordenar</p>
          <ul className="admin-list">
            {options.map((o) => (
              <li
                key={o.id}
                className={`${draggingId === o.id ? "dragging" : ""}${dropTargetId === o.id && draggingId !== o.id ? " drag-over" : ""}`}
                draggable
                onDragStart={(e) => onDragStart(o.id, e)}
                onDragOver={(e) => onDragOver(o.id, e)}
                onDrop={(e) => void onDropOptions(o.id, e)}
                onDragEnd={onDragEnd}
              >
                <span className="admin-list__handle" title="Arrastrar" aria-hidden>⋮⋮</span>
                <button
                  type="button"
                  className={`${o.id === optionId ? "on" : ""}${o.is_active ? "" : " inactive"}`}
                  onClick={() => setOptionId(o.id)}
                >
                  <span>{o.label}{!o.is_active ? " (inactivo)" : ""}</span>
                </button>
              </li>
            ))}
          </ul>
          <div className="actions" style={{ marginTop: ".7rem" }}>
            <button type="button" className="btn btn-primary" disabled={!groupId} onClick={openCreateSubtype}>Agregar subtipo</button>
            <button type="button" className="btn btn-out" disabled={!selected} onClick={openEditSubtype}>Editar</button>
          </div>
        </section>

        <section className="card">
          <strong>Detalle del subtipo</strong>
          {!selected ? (
            <p className="muted">Seleccione un subtipo</p>
          ) : (
            <>
              <p style={{ margin: ".6rem 0 .2rem" }}><b>{selected.label}</b></p>
              {selected.description && <p className="muted" style={{ fontSize: ".88rem" }}>{selected.description}</p>}

              <div className="field" style={{ marginTop: "1rem" }}>
                <label>Imagen del subtipo</label>
                {selected.image_url && (
                  <img
                    className="admin-thumb"
                    key={selected.image_url}
                    src={mediaUrl(selected.image_url)}
                    alt={selected.label}
                  />
                )}
                <input
                  type="file"
                  accept="image/*,.jpg,.jpeg,.png,.webp,.gif,.bmp"
                  disabled={loading}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    e.target.value = "";
                    if (f) void uploadImage(f);
                  }}
                />
                {loading && <p className="muted" style={{ fontSize: ".85rem" }}>Subiendo imagen…</p>}
              </div>

              <div style={{ marginTop: "1rem" }}>
                <strong>Orden por año de construcción</strong>
                <p className="muted" style={{ fontSize: ".85rem" }}>
                  Ejemplo: madera orden base 5; regla año ≥ 2011 → orden 2.
                </p>
                <ul className="admin-rules">
                  {(selected.order_rules || []).map((r) => (
                    <li key={r.id}>
                      Orden <b>{r.sort_order}</b> · años {r.year_from}–{r.year_to ?? "∞"}
                      <button type="button" className="btn btn-out" style={{ padding: ".2rem .45rem" }} onClick={() => removeRule(r.id)}>Quitar</button>
                    </li>
                  ))}
                </ul>
                <form onSubmit={addRule} className="grid2" style={{ marginTop: ".5rem" }}>
                  <div className="field"><label>Orden efectivo</label><input type="number" value={ruleForm.sort_order} onChange={(e) => setRuleForm({ ...ruleForm, sort_order: Number(e.target.value) })} /></div>
                  <div className="field"><label>Año desde</label><input type="number" value={ruleForm.year_from} onChange={(e) => setRuleForm({ ...ruleForm, year_from: Number(e.target.value) })} /></div>
                  <div className="field"><label>Año hasta (vacío = sin fin)</label><input type="number" value={ruleForm.year_to} onChange={(e) => setRuleForm({ ...ruleForm, year_to: e.target.value })} /></div>
                  <div className="field"><label>Notas</label><input value={ruleForm.notes} onChange={(e) => setRuleForm({ ...ruleForm, notes: e.target.value })} /></div>
                  <div className="actions" style={{ gridColumn: "1 / -1" }}>
                    <button className="btn btn-primary" disabled={loading} type="submit">Agregar regla</button>
                  </div>
                </form>
              </div>
            </>
          )}
        </section>
      </div>

      {modal && (
        <div className="modal-backdrop" role="presentation" onClick={() => setModal(null)}>
          <div className="modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <div className="actions" style={{ marginBottom: ".5rem" }}>
              <strong>{modalTitle}</strong>
              <button type="button" className="btn btn-out" style={{ padding: ".25rem .55rem" }} onClick={() => setModal(null)}>✕</button>
            </div>

            {(modal === "type-create" || modal === "type-edit") && (
              <form onSubmit={submitType} className="admin-form">
                <div className="field">
                  <label>Nombre</label>
                  <input required value={typeForm.name} onChange={(e) => setTypeForm({ ...typeForm, name: e.target.value })} />
                </div>
                <div className="field">
                  <label>Aplica a</label>
                  <select
                    value={typeForm.applies_to}
                    onChange={(e) => setTypeForm({ ...typeForm, applies_to: e.target.value })}
                  >
                    <option value="block">Bloque constructivo</option>
                    <option value="improvement">Mejora</option>
                    <option value="both">Bloque y mejora</option>
                  </select>
                </div>
                <div className="field">
                  <label>Porcentaje máximo del tipo</label>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step={0.01}
                    required
                    value={typeForm.max_percent}
                    onChange={(e) => setTypeForm({ ...typeForm, max_percent: Number(e.target.value) })}
                  />
                </div>
                <label className="svcs">
                  <input type="checkbox" checked={typeForm.is_active} onChange={(e) => setTypeForm({ ...typeForm, is_active: e.target.checked })} />
                  Activo
                </label>
                <div className="actions">
                  <button className="btn btn-primary" disabled={loading} type="submit">Guardar</button>
                  {modal === "type-edit" && (
                    <button className="btn btn-out" type="button" disabled={loading} onClick={() => void softDeleteType()}>
                      Eliminar
                    </button>
                  )}
                </div>
              </form>
            )}

            {(modal === "subtype-create" || modal === "subtype-edit") && (
              <form onSubmit={submitSubtype} className="admin-form">
                <div className="field">
                  <label>Nombre</label>
                  <input required value={optForm.label} onChange={(e) => setOptForm({ ...optForm, label: e.target.value })} />
                </div>
                <div className="field">
                  <label>Descripción</label>
                  <textarea rows={4} value={optForm.description} onChange={(e) => setOptForm({ ...optForm, description: e.target.value })} />
                </div>
                <label className="svcs">
                  <input type="checkbox" checked={optForm.is_active} onChange={(e) => setOptForm({ ...optForm, is_active: e.target.checked })} />
                  Activo
                </label>
                <div className="actions">
                  <button className="btn btn-primary" disabled={loading} type="submit">Guardar</button>
                  {modal === "subtype-edit" && (
                    <button className="btn btn-out" type="button" disabled={loading} onClick={() => void softDeleteSubtype()}>
                      Eliminar
                    </button>
                  )}
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
