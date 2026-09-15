import { Link } from "react-router-dom";
import { useBranding } from "../lib/branding";
import { GisBackdrop } from "../components/GisBackdrop";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";

export function LandingPage() {
  const b = useBranding();

  return (
    <div className="relative min-h-dvh">
      <GisBackdrop />

      <header className="sticky top-0 z-20 border-b border-white/40 bg-white/70 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <Link to="/" className="flex min-w-0 items-center gap-2.5">
            <img className="h-10 w-auto sm:h-11" src="/brand/cocha-cyan.png" alt="Cocha" />
            <span className="min-w-0">
              <span className="block truncate text-sm font-bold text-slate-900">{b.portal}</span>
              <span className="block truncate text-xs text-slate-500">{b.unit}</span>
            </span>
          </Link>
          <div className="flex shrink-0 items-center gap-2">
            <Link to="/login">
              <Button variant="secondary" size="sm">
                Ingresar
              </Button>
            </Link>
            <Link to="/registro">
              <Button variant="primary" size="sm">
                Nuevo registro
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <section className="px-4 py-14 sm:px-6 sm:py-20">
        <div className="mx-auto max-w-4xl animate-card-in text-center">
          <Card className="mx-auto max-w-3xl">
            <img
              className="mx-auto mb-6 h-24 w-auto drop-shadow-[0_3px_8px_rgba(38,21,74,0.25)]"
              src="/brand/cocha-lockup.png"
              alt="Cocha · Gobierno Autónomo Municipal de Cochabamba"
            />
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-accent-600">{b.portal}</p>
            <h1 className="text-3xl font-extrabold leading-tight text-slate-900 sm:text-4xl">{b.tagline}</h1>
            <p className="mx-auto mt-3 max-w-md text-base text-slate-600">{b.slogan}</p>
            <div className="mt-7 flex flex-wrap justify-center gap-3">
              <Link to="/registro">
                <Button size="lg">Crear cuenta</Button>
              </Link>
              <Link to="/login">
                <Button variant="secondary" size="lg">
                  Ya tengo usuario
                </Button>
              </Link>
            </div>
            <p className="mt-5 text-sm text-slate-500">Trámite claro y cercano. Ubique el predio con OpenStreetMap, sin Google Maps.</p>
          </Card>
        </div>
      </section>

      <section className="px-4 pb-16 sm:px-6" id="tramite">
        <div className="mx-auto max-w-5xl">
          <h2 className="text-center text-2xl font-extrabold text-slate-900">Cómo tramitar el avalúo</h2>
          <p className="mx-auto mt-1 max-w-xl text-center text-sm text-slate-500">
            Siga estos pasos. Un arquitecto, una cuenta: correo y Nº del Colegio de Arquitectos son únicos.
          </p>
          <div className="mt-8 grid gap-5 sm:grid-cols-3">
            {[
              { n: "01", title: "Regístrese", body: "CI, correo y Nº de registro profesional. Proceso rápido y sencillo." },
              { n: "02", title: "Complete el formulario", body: "Propietario, predio, bloques, materiales ilustrados y fotografías." },
              { n: "03", title: "Revisión y migración", body: "El técnico aprueba y copia datos, imágenes y PDF a la BD de oficina." },
            ].map((step) => (
              <Card key={step.n} glass={false} className="p-6">
                <b className="text-xs font-black uppercase tracking-wider text-accent-600">{step.n}</b>
                <h3 className="mt-1.5 text-base font-bold text-slate-900">{step.title}</h3>
                <p className="mt-1 text-sm text-slate-500">{step.body}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <footer className="border-t border-white/40 bg-brand-900/95 px-4 py-5 text-white sm:px-6">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 text-sm">
          <span className="flex items-center gap-2.5">
            <img className="h-8 w-auto" src="/brand/cocha-on-cyan.png" alt="Cocha" />
            {b.org}
          </span>
          <span className="text-white/80">{b.tagline}</span>
        </div>
      </footer>
    </div>
  );
}
