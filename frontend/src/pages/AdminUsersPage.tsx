import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api } from "../lib/api";

type Role = { code: string; name: string; description?: string | null };

type UserRow = {
  id: string;
  email: string;
  username?: string | null;
  first_name: string;
  last_name: string;
  document_number?: string | null;
  professional_reg?: string | null;
  is_active: boolean;
  roles: string[];
  role_labels: string[];
  expires_at?: string | null;
  deleted_at?: string | null;
  last_login_at?: string | null;
  must_change_password?: boolean;
};

const ROLE_HINT: Record<string, string> = {
  citizen: "Puede crear y completar sus propios formularios.",
  technical_architect: "Puede buscar, revisar y migrar formularios de otros. Requiere fecha de vencimiento.",
  system_admin: "Acceso total: usuarios, catálogos y configuración.",
  catalog_admin: "Puede administrar características, valores, parámetros y fórmulas.",
};

function toDateInput(iso?: string | null) {
  if (!iso) return "";
  return iso.slice(0, 10);
}

export function AdminUsersPage() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<UserRow[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [pickedRoles, setPickedRoles] = useState<string[]>(["citizen"]);
  const [expiresOn, setExpiresOn] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [editingProfile, setEditingProfile] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const selected = useMemo(() => results.find((u) => u.id === selectedId) || null, [results, selectedId]);
  const needsExpiry = pickedRoles.includes("technical_architect");
  const isFuncionario = Boolean(selected?.roles.includes("technical_architect"));

  useEffect(() => {
    api<Role[]>("/api/v1/admin/roles", {}, true)
      .then(setRoles)
      .catch((e) => setError(e instanceof Error ? e.message : "Error al cargar roles"));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setPickedRoles(selected.roles.length ? selected.roles : ["citizen"]);
    setExpiresOn(toDateInput(selected.expires_at));
    setFirstName(selected.first_name);
    setLastName(selected.last_name);
    setEditingProfile(false);
    setNewPassword("");
    setNewPasswordConfirm("");
  }, [selected]);

  function patchSelected(updated: UserRow) {
    setResults((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
  }

  async function search(e?: FormEvent) {
    e?.preventDefault();
    setError("");
    setMsg("");
    setSearched(true);
    if (q.trim().length < 2) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const rows = await api<UserRow[]>(`/api/v1/admin/users/search?q=${encodeURIComponent(q.trim())}`, {}, true);
      setResults(rows);
      if (rows[0]) setSelectedId(rows[0].id);
      else setSelectedId("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error de búsqueda");
    } finally {
      setLoading(false);
    }
  }

  function toggleRole(code: string) {
    setPickedRoles((prev) => {
      if (prev.includes(code)) return prev.filter((c) => c !== code);
      return [...prev, code];
    });
  }

  async function saveProfile(e?: FormEvent) {
    e?.preventDefault();
    if (!selected) return;
    setLoading(true);
    setError("");
    try {
      const updated = await api<UserRow>(`/api/v1/admin/users/${selected.id}/profile`, {
        method: "PUT",
        body: JSON.stringify({ first_name: firstName, last_name: lastName }),
      }, true);
      setMsg("Datos personales actualizados");
      setEditingProfile(false);
      patchSelected(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar");
    } finally {
      setLoading(false);
    }
  }

  async function onProfileEditToggle() {
    if (editingProfile) {
      await saveProfile();
      return;
    }
    setEditingProfile(true);
    setMsg("");
  }

  async function savePassword(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setLoading(true);
    setError("");
    try {
      const updated = await api<UserRow>(`/api/v1/admin/users/${selected.id}/password`, {
        method: "PUT",
        body: JSON.stringify({ password: newPassword, password_confirm: newPasswordConfirm }),
      }, true);
      setMsg("Contraseña asignada. El usuario deberá cambiarla al ingresar.");
      setNewPassword("");
      setNewPasswordConfirm("");
      patchSelected(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cambiar la contraseña");
    } finally {
      setLoading(false);
    }
  }

  async function saveRoles(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    const rolesToSave = pickedRoles.length ? pickedRoles : ["citizen"];
    setLoading(true);
    setError("");
    try {
      const updated = await api<UserRow>(`/api/v1/admin/users/${selected.id}/roles`, {
        method: "PUT",
        body: JSON.stringify({
          roles: rolesToSave,
          expires_on: needsExpiry ? expiresOn || null : null,
        }),
      }, true);
      setMsg("Roles actualizados");
      patchSelected(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar");
    } finally {
      setLoading(false);
    }
  }

  async function extendOneYear() {
    if (!selected) return;
    setLoading(true);
    setError("");
    try {
      const updated = await api<UserRow>(`/api/v1/admin/users/${selected.id}/extend-year`, {
        method: "PUT",
      }, true);
      setMsg("Vigencia extendida un año");
      setExpiresOn(toDateInput(updated.expires_at));
      patchSelected(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo renovar");
    } finally {
      setLoading(false);
    }
  }

  async function setActive(active: boolean) {
    if (!selected) return;
    setLoading(true);
    setError("");
    try {
      const updated = await api<UserRow>(`/api/v1/admin/users/${selected.id}/active?active=${active}`, {
        method: "PUT",
      }, true);
      setMsg(active ? "Usuario habilitado" : "Usuario inhabilitado");
      patchSelected(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  async function softDelete() {
    if (!selected) return;
    if (!confirm(`¿Eliminar lógicamente a ${selected.first_name} ${selected.last_name}?`)) return;
    setLoading(true);
    setError("");
    try {
      await api(`/api/v1/admin/users/${selected.id}`, { method: "DELETE" }, true);
      setMsg("Usuario eliminado lógicamente");
      setResults((prev) => prev.filter((u) => u.id !== selected.id));
      setSelectedId("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <h2>Administración · Usuarios y roles</h2>
      <p className="muted">
        Busque por nombre, apellido, CI o correo. Puede corregir datos, resetear contraseña, habilitar/inhabilitar y extender vigencia de funcionarios.
      </p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="hint">{msg}</div>}

      <form onSubmit={search} className="card" style={{ marginBottom: "1rem" }}>
        <div className="field">
          <label>Buscar usuario</label>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Nombre, apellido, CI o correo…"
            autoComplete="off"
          />
        </div>
        <button className="btn btn-primary" disabled={loading} type="submit" style={{ marginTop: ".7rem" }}>
          Buscar
        </button>
      </form>

      <div className="admin-grid" style={{ gridTemplateColumns: "1fr 1.4fr" }}>
        <section className="card">
          <strong>Resultados</strong>
          {!searched && <p className="muted">Escriba al menos 2 caracteres y busque.</p>}
          {searched && !results.length && <p className="muted">Sin coincidencias.</p>}
          <ul className="admin-list" style={{ marginTop: ".6rem" }}>
            {results.map((u) => (
              <li key={u.id}>
                <button type="button" className={u.id === selectedId ? "on" : ""} onClick={() => setSelectedId(u.id)}>
                  <span>
                    {u.first_name} {u.last_name}
                    <div className="muted" style={{ fontSize: ".75rem", color: "inherit", opacity: 0.85 }}>{u.email}</div>
                  </span>
                  <em>{u.role_labels[0] || "—"}</em>
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className="card">
          {!selected ? (
            <p className="muted">Seleccione un usuario</p>
          ) : (
            <>
              <h3 style={{ margin: "0 0 .35rem", fontSize: "1.1rem" }}>
                {selected.first_name} {selected.last_name}
              </h3>
              <p className="muted" style={{ margin: 0 }}>{selected.email}</p>
              <p className="muted" style={{ fontSize: ".85rem" }}>
                Usuario: {selected.username || "—"} · CI: {selected.document_number || "—"} · Reg. profesional: {selected.professional_reg || "—"}
              </p>
              <p className="muted" style={{ fontSize: ".85rem" }}>
                Estado: {selected.is_active ? "Activo" : "Inhabilitado"}
                {selected.expires_at ? ` · Vence: ${toDateInput(selected.expires_at)}` : ""}
                {selected.must_change_password ? " · Debe cambiar contraseña" : ""}
              </p>
              <p className="muted" style={{ fontSize: ".85rem" }}>
                Roles actuales: {selected.role_labels.join(", ") || "Ninguno"}
              </p>

              <div className="admin-form" style={{ marginTop: "1rem" }}>
                <strong>Datos personales</strong>
                <div className="grid2">
                  <div className="field">
                    <label>Nombres</label>
                    <input
                      required
                      disabled={!editingProfile || loading}
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                    />
                  </div>
                  <div className="field">
                    <label>Apellidos</label>
                    <input
                      required
                      disabled={!editingProfile || loading}
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                    />
                  </div>
                </div>
                <button
                  className={editingProfile ? "btn btn-primary" : "btn btn-out"}
                  disabled={loading}
                  type="button"
                  onClick={() => void onProfileEditToggle()}
                >
                  {editingProfile ? "Guardar" : "Editar"}
                </button>
              </div>

              <form onSubmit={savePassword} className="admin-form" style={{ marginTop: "1rem" }}>
                <strong>Nueva contraseña</strong>
                <p className="muted" style={{ margin: 0, fontSize: ".85rem" }}>
                  Al guardar, el usuario deberá cambiarla en el próximo ingreso y no podrá usar el portal hasta hacerlo.
                </p>
                <div className="field">
                  <label>Contraseña temporal</label>
                  <input type="password" required minLength={8} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
                </div>
                <div className="field">
                  <label>Confirmar contraseña</label>
                  <input type="password" required minLength={8} value={newPasswordConfirm} onChange={(e) => setNewPasswordConfirm(e.target.value)} />
                </div>
                <button className="btn btn-primary" disabled={loading} type="submit">Asignar contraseña</button>
              </form>

              <form onSubmit={saveRoles} className="admin-form" style={{ marginTop: "1rem" }}>
                <strong>Asignar roles</strong>
                {roles.map((r) => (
                  <label key={r.code} className="svcs" style={{ alignItems: "flex-start" }}>
                    <input
                      type="checkbox"
                      checked={pickedRoles.includes(r.code)}
                      onChange={() => toggleRole(r.code)}
                    />
                    <span>
                      <b>{r.name}</b>
                      <div className="muted" style={{ fontSize: ".8rem" }}>{ROLE_HINT[r.code] || r.description}</div>
                    </span>
                  </label>
                ))}

                {needsExpiry && (
                  <div className="field">
                    <label>Fecha de vencimiento (Funcionario)</label>
                    <input type="date" required value={expiresOn} onChange={(e) => setExpiresOn(e.target.value)} />
                  </div>
                )}

                <div className="actions">
                  <button className="btn btn-primary" disabled={loading} type="submit">Guardar roles</button>
                  {isFuncionario && (
                    <button className="btn btn-out" type="button" disabled={loading} onClick={() => void extendOneYear()}>
                      Extender 1 año
                    </button>
                  )}
                </div>
              </form>

              <div className="actions" style={{ marginTop: "1rem" }}>
                {selected.is_active ? (
                  <button type="button" className="btn btn-out" disabled={loading} onClick={() => void setActive(false)}>
                    Inhabilitar
                  </button>
                ) : (
                  <button type="button" className="btn btn-out" disabled={loading} onClick={() => void setActive(true)}>
                    Habilitar
                  </button>
                )}
                <button type="button" className="btn btn-out" disabled={loading} onClick={() => void softDelete()}>
                  Eliminar
                </button>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
