import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { LockClosedIcon, ShieldCheckIcon } from "@heroicons/react/24/solid";
import { api } from "../lib/api";
import { clearSession, getToken, setSession, type AuthUser } from "../lib/auth";
import { GisBackdrop } from "../components/GisBackdrop";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Alert } from "../components/ui/Alert";

export function ForceChangePasswordPage() {
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user = await api<AuthUser>(
        "/api/v1/auth/me/password",
        {
          method: "PUT",
          body: JSON.stringify({
            current_password: currentPassword,
            password,
            password_confirm: passwordConfirm,
          }),
        },
        true,
      );
      const token = getToken();
      if (token) setSession(token, user);
      navigate("/app", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cambiar la contraseña");
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    clearSession();
    navigate("/login", { replace: true });
  }

  return (
    <main className="relative flex min-h-dvh items-center justify-center px-4 py-12">
      <GisBackdrop />

      <div className="w-full max-w-sm animate-card-in">
        <Card className="sm:p-9">
          <div className="mb-6 flex items-center justify-between">
            <img src="/brand/cocha-cyan.png" alt="Cocha" className="h-10 w-auto" />
            <Button variant="ghost" size="sm" onClick={logout}>
              Salir
            </Button>
          </div>

          <h1 className="text-xl font-extrabold text-slate-900">Cambiar contraseña</h1>
          <p className="mt-1 text-sm text-slate-500">Por seguridad debe definir una contraseña nueva antes de ingresar al portal.</p>

          <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4">
            {error && <Alert type="error" message={error} />}

            <Input
              label="Contraseña temporal"
              type="password"
              required
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              icon={LockClosedIcon}
            />
            <Input
              label="Nueva contraseña"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              icon={LockClosedIcon}
            />
            <Input
              label="Confirmar nueva contraseña"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              icon={LockClosedIcon}
            />

            <Alert type="info" message="8+ caracteres, mayúscula, minúscula, número y símbolo. Debe ser distinta a la temporal." />

            <Button type="submit" size="lg" loading={loading} icon={ShieldCheckIcon} className="w-full">
              {loading ? "Guardando…" : "Guardar e ingresar"}
            </Button>
          </form>
        </Card>
      </div>
    </main>
  );
}
