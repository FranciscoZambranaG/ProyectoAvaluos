import { useEffect, useState, type FormEvent } from "react";
import { api } from "../lib/api";
import { getStoredUser, setSession, getToken, type AuthUser } from "../lib/auth";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Alert } from "../components/ui/Alert";
import { SectionHeader } from "../components/ui/SectionHeader";

export function ProfilePage() {
  const stored = getStoredUser();
  const [form, setForm] = useState({
    first_name: stored?.first_name || "",
    last_name: stored?.last_name || "",
    document_number: stored?.document_number || "",
    auxiliary_email: stored?.auxiliary_email || "",
  });
  const [pwd, setPwd] = useState({ current_password: "", password: "", password_confirm: "" });
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api<AuthUser>("/api/v1/auth/me", {}, true)
      .then((u) => {
        setForm({
          first_name: u.first_name,
          last_name: u.last_name,
          document_number: u.document_number || "",
          auxiliary_email: u.auxiliary_email || "",
        });
        const token = getToken();
        if (token) setSession(token, u);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Error"));
  }, []);

  async function saveProfile(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setMsg("");
    try {
      const u = await api<AuthUser>(
        "/api/v1/auth/me",
        {
          method: "PUT",
          body: JSON.stringify({
            ...form,
            auxiliary_email: form.auxiliary_email.trim() || null,
          }),
        },
        true,
      );
      const token = getToken();
      if (token) setSession(token, u);
      setMsg("Datos personales actualizados");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar");
    } finally {
      setLoading(false);
    }
  }

  async function savePassword(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setMsg("");
    try {
      await api("/api/v1/auth/me/password", { method: "PUT", body: JSON.stringify(pwd) }, true);
      setPwd({ current_password: "", password: "", password_confirm: "" });
      setMsg("Contraseña actualizada");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cambiar la contraseña");
    } finally {
      setLoading(false);
    }
  }

  if (!stored) return null;

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-extrabold text-slate-900">Perfil</h1>
        <p className="mt-1 text-sm text-slate-500">Puede corregir sus datos personales y cambiar la contraseña.</p>
      </div>

      {error && <Alert type="error" message={error} />}
      {msg && <Alert type="success" message={msg} />}

      <Card glass={false} as="form" onSubmit={saveProfile}>
        <SectionHeader title="Datos personales" />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Nombres" required value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} />
          <Input label="Apellidos" required value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} />
        </div>
        <div className="mt-4">
          <Input
            label="C.I."
            required
            value={form.document_number}
            onChange={(e) => setForm({ ...form, document_number: e.target.value })}
          />
        </div>
        <div className="mt-4">
          <Input label="Correo principal" disabled value={stored.email} />
        </div>
        <div className="mt-4">
          <Input
            label="Correo auxiliar"
            type="email"
            value={form.auxiliary_email}
            onChange={(e) => setForm({ ...form, auxiliary_email: e.target.value })}
          />
        </div>
        <div className="mt-4">
          <Input label="Usuario" disabled value={stored.username || "—"} />
        </div>
        <div className="mt-4">
          <Input label="Nº Colegio de Arquitectos" disabled value={stored.professional_reg || "No aplica"} />
        </div>
        <Button type="submit" loading={loading} className="mt-5">
          Guardar datos
        </Button>
      </Card>

      <Card glass={false} as="form" onSubmit={savePassword}>
        <SectionHeader title="Cambiar contraseña" />
        <div className="grid gap-4">
          <Input
            label="Contraseña actual"
            type="password"
            required
            value={pwd.current_password}
            onChange={(e) => setPwd({ ...pwd, current_password: e.target.value })}
          />
          <Input
            label="Nueva contraseña"
            type="password"
            required
            value={pwd.password}
            onChange={(e) => setPwd({ ...pwd, password: e.target.value })}
          />
          <Input
            label="Confirmar nueva contraseña"
            type="password"
            required
            value={pwd.password_confirm}
            onChange={(e) => setPwd({ ...pwd, password_confirm: e.target.value })}
          />
        </div>
        <Button type="submit" loading={loading} className="mt-5">
          Actualizar contraseña
        </Button>
      </Card>
    </div>
  );
}
