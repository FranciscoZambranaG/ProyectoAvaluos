import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { UserIcon, LockClosedIcon, EyeIcon, EyeSlashIcon, ShieldCheckIcon } from "@heroicons/react/24/solid";
import { api } from "../lib/api";
import { setSession } from "../lib/auth";
import type { AuthUser } from "../lib/auth";
import { useBranding } from "../lib/branding";
import { GisBackdrop } from "../components/GisBackdrop";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Alert } from "../components/ui/Alert";

type AuthResponse = {
  token: { access_token: string };
  user: AuthUser;
};

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const branding = useBranding();
  const from = (location.state as { from?: string } | null)?.from || "/app";
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await api<AuthResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ login, password }),
      });
      setSession(data.token.access_token, data.user);
      if (data.user.must_change_password) {
        navigate("/cambiar-contrasena", { replace: true });
      } else {
        navigate(from, { replace: true });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesión");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative flex min-h-dvh items-center justify-center px-4 py-12">
      <GisBackdrop />

      <div className="w-full max-w-sm animate-card-in">
        <Card className="sm:p-9">
          <div className="mb-8 flex flex-col items-center text-center">
            <Link to="/">
              <img
                src="/brand/cocha-cyan.png"
                alt="Cocha"
                className="mb-5 h-16 w-auto drop-shadow-[0_3px_8px_rgba(38,21,74,0.25)]"
              />
            </Link>
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-widest text-accent-600">{branding.org}</p>
            <h1 className="text-2xl font-extrabold uppercase tracking-wide text-slate-900">{branding.portal}</h1>
            <p className="mt-2 text-sm text-slate-500">Usuario, correo institucional o correo auxiliar</p>
          </div>

          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <Input
              id="login"
              label="Usuario o correo"
              autoComplete="username"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              icon={UserIcon}
              required
            />
            <Input
              id="password"
              label="Contraseña"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              icon={LockClosedIcon}
              required
              rightElement={
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="cursor-pointer text-slate-400 hover:text-slate-600 focus:outline-none"
                  tabIndex={-1}
                  aria-label={showPassword ? "Ocultar contraseña" : "Ver contraseña"}
                >
                  {showPassword ? <EyeSlashIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
                </button>
              }
            />

            {error && <Alert type="error" message={error} />}

            <Button type="submit" variant="primary" size="lg" loading={loading} icon={ShieldCheckIcon} className="mt-1 w-full">
              {loading ? "Ingresando…" : "Ingresar"}
            </Button>

            <div className="flex items-center justify-between gap-3 text-sm">
              <Link to="/" className="font-medium text-accent-600 hover:text-accent-500">
                ← Volver al portal
              </Link>
              <Link to="/registro" className="font-medium text-accent-600 hover:text-accent-500">
                Registrarme
              </Link>
            </div>
          </form>
        </Card>
      </div>
    </main>
  );
}
