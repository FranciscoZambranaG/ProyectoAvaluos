import { useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { setSession } from "../lib/auth";
import type { AuthUser } from "../lib/auth";
import { GisBackdrop } from "../components/GisBackdrop";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Alert } from "../components/ui/Alert";

type AuthResponse = {
  token: { access_token: string };
  user: AuthUser;
};

const empty = {
  first_name: "",
  last_name: "",
  document_number: "",
  email: "",
  professional_reg: "",
  username: "",
  password: "",
  password_confirm: "",
};

function isMunicipalEmail(email: string): boolean {
  return email.trim().toLowerCase().endsWith("@cochabamba.bo");
}

export function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState(empty);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const municipal = useMemo(() => isMunicipalEmail(form.email), [form.email]);

  function set<K extends keyof typeof empty>(key: K, value: string) {
    setForm((prev) => {
      const next = { ...prev, [key]: value };
      if (key === "email") {
        const email = value.trim().toLowerCase();
        next.username = email;
        if (isMunicipalEmail(email)) {
          next.professional_reg = "";
        }
      }
      return next;
    });
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const email = form.email.trim().toLowerCase();
      const payload = {
        ...form,
        email,
        username: email,
        professional_reg: municipal ? "" : form.professional_reg.trim(),
      };
      const data = await api<AuthResponse>("/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setSession(data.token.access_token, data.user);
      navigate("/app", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo registrar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative min-h-dvh px-4 py-12">
      <GisBackdrop />

      <div className="mx-auto w-full max-w-2xl animate-card-in">
        <Card className="sm:p-9">
          <div className="mb-2 flex justify-center">
            <Link to="/">
              <img src="/brand/cocha-cyan.png" alt="Cocha" className="h-14 w-auto drop-shadow-[0_3px_8px_rgba(38,21,74,0.25)]" />
            </Link>
          </div>
          <h1 className="text-center text-xl font-extrabold text-slate-900">Registro de datos personales</h1>
          {!municipal && (
            <p className="mt-1 text-center text-sm text-slate-500">
              El número de registro del Colegio de Arquitectos es obligatorio y único para contribuyentes. El correo también debe ser
              único.
            </p>
          )}

          <form onSubmit={onSubmit} className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
            {error && (
              <div className="sm:col-span-2">
                <Alert type="error" message={error} />
              </div>
            )}

            <Input label="Nombres *" required value={form.first_name} onChange={(e) => set("first_name", e.target.value)} />
            <Input label="Apellidos *" required value={form.last_name} onChange={(e) => set("last_name", e.target.value)} />
            <Input
              label="Carnet de identidad *"
              required
              value={form.document_number}
              onChange={(e) => set("document_number", e.target.value)}
            />
            <Input label="Correo electrónico *" type="email" required value={form.email} onChange={(e) => set("email", e.target.value)} />
            <Input
              label={`Nº registro Colegio de Arquitectos${municipal ? " (opcional)" : " *"}`}
              required={!municipal}
              minLength={municipal ? undefined : 3}
              disabled={municipal}
              placeholder={municipal ? "No requerido" : undefined}
              value={form.professional_reg}
              onChange={(e) => set("professional_reg", e.target.value)}
            />
            <Input label="Usuario *" required disabled value={form.username} readOnly />
            <Input
              label="Contraseña *"
              type="password"
              required
              minLength={8}
              value={form.password}
              onChange={(e) => set("password", e.target.value)}
            />
            <Input
              label="Repetir contraseña *"
              type="password"
              required
              value={form.password_confirm}
              onChange={(e) => set("password_confirm", e.target.value)}
            />

            <div className="sm:col-span-2">
              <Alert
                type="info"
                message={
                  municipal
                    ? "Contraseña: 8+ caracteres, mayúscula, minúscula, número y símbolo."
                    : "El Nº de registro profesional y el correo son claves de unicidad. Si ya existen, el sistema rechaza el alta. Contraseña: 8+ caracteres, mayúscula, minúscula, número y símbolo."
                }
              />
            </div>

            <div className="flex items-center justify-between gap-3 sm:col-span-2">
              <Link to="/login" className="text-sm font-medium text-accent-600 hover:text-accent-500">
                ← Volver al inicio de sesión
              </Link>
              <Button type="submit" loading={loading}>
                {loading ? "Grabando…" : "Grabar"}
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </main>
  );
}
