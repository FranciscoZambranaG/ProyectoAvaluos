import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { PlusIcon, MagnifyingGlassIcon } from "@heroicons/react/24/solid";
import { api } from "../lib/api";
import { getStoredUser } from "../lib/auth";
import { printAppraisalPdf } from "../lib/printPdf";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Badge } from "../components/ui/Badge";
import { Alert } from "../components/ui/Alert";
import { SectionHeader } from "../components/ui/SectionHeader";

type Item = {
  id: string;
  form_number?: string | null;
  status_code: string;
  status_name: string;
  address?: string | null;
  owner_name?: string | null;
  owner_document?: string | null;
  approved_area?: number | null;
  cadastral_code?: string | null;
  created_at: string;
  is_own?: boolean;
};

export function FormsPage() {
  const user = getStoredUser();
  const canSearch = user?.roles?.some((r) => r === "system_admin" || r === "technical_architect");

  const [rows, setRows] = useState<Item[]>([]);
  const [found, setFound] = useState<Item[]>([]);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [searchMsg, setSearchMsg] = useState("");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [printingId, setPrintingId] = useState<string | null>(null);

  useEffect(() => {
    api<Item[]>("/api/v1/appraisals", {}, true)
      .then(setRows)
      .catch((err) => setError(err instanceof Error ? err.message : "Error"))
      .finally(() => setLoading(false));
  }, []);

  async function onSearch(e: FormEvent) {
    e.preventDefault();
    if (!canSearch) return;
    setError("");
    setSearchMsg("");
    setSearched(true);
    const term = q.trim();
    if (term.length < 2) {
      setFound([]);
      setSearchMsg("Escriba al menos 2 caracteres.");
      return;
    }
    setSearching(true);
    try {
      const data = await api<Item[]>(`/api/v1/appraisals/search?q=${encodeURIComponent(term)}`, {}, true);
      setFound(data);
      if (!data.length) setSearchMsg("No se encontraron formularios.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error de búsqueda");
      setFound([]);
    } finally {
      setSearching(false);
    }
  }

  async function handlePrint(id: string) {
    setPrintingId(id);
    setError("");
    try {
      await printAppraisalPdf(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo imprimir");
    } finally {
      setPrintingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-extrabold text-slate-900">Formularios registrados</h1>
          <p className="mt-1 text-sm text-slate-500">Consulta y continúa la edición de tus avalúos en borrador.</p>
        </div>
        <Link to="/app/formularios/nuevo">
          <Button icon={PlusIcon}>Nuevo registro</Button>
        </Link>
      </div>

      {error && <Alert type="error" message={error} />}

      {canSearch && (
        <Card glass={false} as="form" onSubmit={onSearch}>
          <SectionHeader title="Buscar formularios" subtitle="Funcionario / administrador" />
          <p className="-mt-4 mb-4 text-xs text-slate-500">
            Un solo campo: código catastral, nombre del propietario, C.I./NIT o número de formulario.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <Input
              containerClassName="flex-1 min-w-[240px]"
              label="Buscar"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              autoComplete="off"
              icon={MagnifyingGlassIcon}
            />
            <Button type="submit" loading={searching}>
              {searching ? "Buscando…" : "Buscar"}
            </Button>
          </div>
          {searchMsg && <p className="mt-3 text-sm text-slate-500">{searchMsg}</p>}
          {searched && found.length > 0 && (
            <div className="mt-4 overflow-auto rounded-2xl border border-slate-200">
              <table className="w-full min-w-[640px] border-collapse text-sm">
                <thead>
                  <tr className="bg-slate-50 text-xs text-slate-500">
                    <th className="px-3 py-2.5 text-left">Nº formulario</th>
                    <th className="px-3 py-2.5 text-left">Propietario</th>
                    <th className="px-3 py-2.5 text-left">C.I./NIT</th>
                    <th className="px-3 py-2.5 text-left">Código catastral</th>
                    <th className="px-3 py-2.5 text-left">Estado</th>
                    <th className="px-3 py-2.5" />
                  </tr>
                </thead>
                <tbody>
                  {found.map((r) => (
                    <tr key={r.id} className="border-t border-slate-100">
                      <td className="px-3 py-2.5">{r.form_number || "—"}</td>
                      <td className="px-3 py-2.5">{r.owner_name || "—"}</td>
                      <td className="px-3 py-2.5">{r.owner_document || "—"}</td>
                      <td className="px-3 py-2.5">{r.cadastral_code || "—"}</td>
                      <td className="px-3 py-2.5">
                        <Badge variant="accent">{r.status_name}</Badge>
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-3 text-sm font-semibold">
                          <Link to={`/app/formularios/${r.id}`} className="text-accent-600 hover:text-accent-500">
                            Abrir
                          </Link>
                          <button
                            type="button"
                            className="cursor-pointer text-accent-600 hover:text-accent-500 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={printingId === r.id}
                            onClick={() => void handlePrint(r.id)}
                          >
                            {printingId === r.id ? "Generando…" : "Imprimir"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      <Card glass={false}>
        <SectionHeader title="Mis formularios" />
        <div className="overflow-auto rounded-2xl border border-slate-200">
          <table className="w-full min-w-[640px] border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 text-xs text-slate-500">
                <th className="px-3 py-2.5 text-left">Nº formulario</th>
                <th className="px-3 py-2.5 text-left">Propietario</th>
                <th className="px-3 py-2.5 text-left">C.I./NIT</th>
                <th className="px-3 py-2.5 text-left">Ubicación</th>
                <th className="px-3 py-2.5 text-left">Superficie</th>
                <th className="px-3 py-2.5 text-left">Estado</th>
                <th className="px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={7} className="px-3 py-4 text-sm text-slate-500">
                    Cargando…
                  </td>
                </tr>
              )}
              {!loading && rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-3 py-4 text-sm text-slate-500">
                    Sin registros.{" "}
                    <Link to="/app/formularios/nuevo" className="font-semibold text-accent-600 hover:text-accent-500">
                      Crear el primero
                    </Link>
                  </td>
                </tr>
              )}
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-slate-100">
                  <td className="px-3 py-2.5">{r.form_number}</td>
                  <td className="px-3 py-2.5">{r.owner_name || "—"}</td>
                  <td className="px-3 py-2.5">{r.owner_document || "—"}</td>
                  <td className="px-3 py-2.5">{r.address || "—"}</td>
                  <td className="px-3 py-2.5">{r.approved_area != null ? `${r.approved_area} m²` : "—"}</td>
                  <td className="px-3 py-2.5">
                    <Badge variant="accent">{r.status_name}</Badge>
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-3 text-sm font-semibold">
                      <Link to={`/app/formularios/${r.id}`} className="text-accent-600 hover:text-accent-500">
                        Abrir
                      </Link>
                      <button
                        type="button"
                        className="cursor-pointer text-accent-600 hover:text-accent-500 disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={printingId === r.id}
                        onClick={() => void handlePrint(r.id)}
                      >
                        {printingId === r.id ? "Generando…" : "Imprimir"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {printingId && (
        <div className="fixed inset-0 z-90 grid place-items-center bg-slate-900/50 p-4" role="status" aria-live="polite">
          <Card className="w-full max-w-sm text-center">
            <div className="mx-auto mb-3 h-9 w-9 animate-spin rounded-full border-4 border-accent-200 border-t-brand-800" aria-hidden />
            <strong className="text-slate-900">Generando documento…</strong>
            <p className="mt-1.5 text-sm text-slate-500">Espere un momento. Se abrirá el diálogo de impresión del navegador.</p>
          </Card>
        </div>
      )}
    </div>
  );
}
