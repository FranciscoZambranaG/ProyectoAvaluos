import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import type { AuthUser } from "../lib/auth";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Alert } from "../components/ui/Alert";
import { SectionHeader } from "../components/ui/SectionHeader";

type Summary = {
  welcome: string;
  user: AuthUser;
  stats: { formularios: number; borradores: number; enviados: number; migrados: number };
  next_steps: string[];
};

export function DashboardPage() {
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Summary>("/api/v1/dashboard/summary", {}, true)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Error"));
  }, []);

  if (error) return <Alert type="error" message={error} />;
  if (!data) return <p className="text-sm text-slate-500">Cargando…</p>;

  const stats = [
    { label: "Formularios", value: data.stats.formularios },
    { label: "Borradores", value: data.stats.borradores },
    { label: "Enviados", value: data.stats.enviados },
    { label: "Migrados", value: data.stats.migrados },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-extrabold text-slate-900">{data.welcome}</h1>
        <p className="mt-1 text-sm text-slate-500">
          {data.user.roles.includes("system_admin")
            ? "Acceso de superadministrador. Los contribuyentes deben registrarse con su Nº del Colegio de Arquitectos."
            : `Registro profesional: ${data.user.professional_reg || "—"}`}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map((s) => (
          <Card key={s.label} glass={false} className="p-4 text-center sm:p-5">
            <p className="text-xs font-medium text-slate-500">{s.label}</p>
            <p className="mt-1 text-2xl font-extrabold text-brand-800">{s.value}</p>
          </Card>
        ))}
      </div>

      <Card glass={false}>
        <SectionHeader title="Próximos pasos" />
        <ul className="list-disc space-y-1.5 pl-5 text-sm text-slate-600">
          {data.next_steps.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
        <Link to="/app/formularios" className="mt-5 inline-block">
          <Button>Ir a formularios</Button>
        </Link>
      </Card>
    </div>
  );
}
