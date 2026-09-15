import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import { ChevronDown, ChevronRight, LayoutDashboard, LogOut, Menu, User as UserIcon } from "lucide-react";
import { clearSession, getStoredUser } from "../lib/auth";
import { useBranding } from "../lib/branding";
import { GisBackdrop } from "../components/GisBackdrop";

const navLinkBase =
  "flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-semibold transition-colors duration-150";
const navLinkActive = "bg-brand-800 text-white shadow-sm shadow-brand-800/20";
const navLinkInactive = "text-slate-700 hover:bg-slate-100 hover:text-slate-900";

export function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = getStoredUser();
  const branding = useBranding();
  const isAdmin = user?.roles?.some((r) => r === "system_admin" || r === "catalog_admin");
  const isSystemAdmin = user?.roles?.includes("system_admin");
  const adminOpen = location.pathname.startsWith("/app/admin");
  const [menuOpen, setMenuOpen] = useState(adminOpen);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  function logout() {
    clearSession();
    navigate("/login");
  }

  const displayName = user?.first_name ? `${user.first_name} ${user.last_name ?? ""}`.trim() : user?.email || "Usuario";
  const initial = displayName.charAt(0).toUpperCase();

  return (
    <div className="relative flex h-dvh overflow-hidden text-slate-800 antialiased">
      <GisBackdrop />

      {/* Sidebar */}
      <div className={`shrink-0 overflow-hidden transition-[width] duration-300 ease-in-out ${sidebarOpen ? "w-64" : "w-0"}`}>
        <aside
          className={`flex h-dvh w-64 flex-col border-r border-slate-200/90 bg-white shadow-[4px_0_24px_rgba(15,23,42,0.06)] transition-opacity duration-200 ${
            sidebarOpen ? "opacity-100 delay-100" : "opacity-0"
          }`}
        >
          <div className="border-b border-slate-100 px-4 py-4">
            <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-400">Navegación</p>
            <div className="mt-2 flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-800 text-white">
                <LayoutDashboard className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-slate-900">{branding.portal}</p>
                <p className="truncate text-[11px] text-slate-500">{branding.unit}</p>
              </div>
            </div>
          </div>

          <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
            <NavLink to="/app" end className={({ isActive }) => `${navLinkBase} ${isActive ? navLinkActive : navLinkInactive}`}>
              <span>Dashboard</span>
            </NavLink>
            <NavLink to="/app/formularios" className={({ isActive }) => `${navLinkBase} ${isActive ? navLinkActive : navLinkInactive}`}>
              <span>Formularios</span>
            </NavLink>

            {isAdmin && (
              <div className="grid gap-1">
                <button
                  type="button"
                  className={`${navLinkBase} ${adminOpen ? navLinkActive : navLinkInactive} w-full justify-between`}
                  onClick={() => setMenuOpen((v) => !v)}
                  aria-current={adminOpen ? "true" : undefined}
                >
                  <span>Admin</span>
                  {menuOpen || adminOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                </button>
                {(menuOpen || adminOpen) && (
                  <div className="ml-2 grid gap-1 border-l border-slate-200 pl-3">
                    <NavLink to="/app/admin/caracteristicas" className={({ isActive }) => `${navLinkBase} !py-2 text-[13px] ${isActive ? navLinkActive : navLinkInactive}`}>
                      Características
                    </NavLink>
                    <NavLink to="/app/admin/catalogos" className={({ isActive }) => `${navLinkBase} !py-2 text-[13px] ${isActive ? navLinkActive : navLinkInactive}`}>
                      Catálogos parametrizados
                    </NavLink>
                    <NavLink to="/app/admin/valores" className={({ isActive }) => `${navLinkBase} !py-2 text-[13px] ${isActive ? navLinkActive : navLinkInactive}`}>
                      Valores
                    </NavLink>
                    <NavLink to="/app/admin/parametros" className={({ isActive }) => `${navLinkBase} !py-2 text-[13px] ${isActive ? navLinkActive : navLinkInactive}`}>
                      Parámetros
                    </NavLink>
                    <NavLink to="/app/admin/fotos" className={({ isActive }) => `${navLinkBase} !py-2 text-[13px] ${isActive ? navLinkActive : navLinkInactive}`}>
                      Tipos de fotografía
                    </NavLink>
                    <NavLink to="/app/admin/formulas" className={({ isActive }) => `${navLinkBase} !py-2 text-[13px] ${isActive ? navLinkActive : navLinkInactive}`}>
                      Fórmulas
                    </NavLink>
                    <NavLink to="/app/admin/branding" className={({ isActive }) => `${navLinkBase} !py-2 text-[13px] ${isActive ? navLinkActive : navLinkInactive}`}>
                      Branding
                    </NavLink>
                    <NavLink to="/app/admin/plantillas" className={({ isActive }) => `${navLinkBase} !py-2 text-[13px] ${isActive ? navLinkActive : navLinkInactive}`}>
                      Plantillas
                    </NavLink>
                    {isSystemAdmin && (
                      <NavLink to="/app/admin/usuarios" className={({ isActive }) => `${navLinkBase} !py-2 text-[13px] ${isActive ? navLinkActive : navLinkInactive}`}>
                        Usuarios
                      </NavLink>
                    )}
                  </div>
                )}
              </div>
            )}

            <NavLink to="/app/perfil" className={({ isActive }) => `${navLinkBase} ${isActive ? navLinkActive : navLinkInactive}`}>
              <span>Perfil</span>
            </NavLink>
          </nav>

          <div className="border-t border-slate-100 px-4 py-3">
            <p className="text-[11px] text-slate-400">{branding.tagline}</p>
          </div>
        </aside>
      </div>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/92 shadow-[0_1px_0_rgba(15,23,42,0.04)] backdrop-blur-md">
          <div className="flex h-14 items-center justify-between gap-3 px-3 sm:h-16 sm:px-6">
            <div className="flex min-w-0 items-center gap-2.5 sm:gap-3">
              <button
                type="button"
                onClick={() => setSidebarOpen((v) => !v)}
                aria-label="Mostrar u ocultar el menú"
                className="flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900"
              >
                <Menu className="h-5 w-5" />
              </button>
              <img className="h-8 w-auto shrink-0 sm:h-9" src="/brand/cocha-cyan.png" alt="Cocha" />
              <div className="hidden min-w-0 border-l border-slate-200 pl-2.5 text-left sm:block">
                <p className="truncate text-[10px] font-black uppercase tracking-[0.14em] text-accent-600">{branding.org}</p>
                <p className="truncate text-sm font-bold text-slate-900">{branding.portal}</p>
              </div>
            </div>

            <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
              <NavLink
                to="/app/perfil"
                className="flex max-w-[220px] cursor-pointer items-center gap-2 rounded-xl border border-slate-200 bg-white px-2 py-1.5 text-left transition-colors hover:border-slate-300 hover:bg-slate-50 sm:px-2.5"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-800 text-xs font-bold text-white">
                  {initial}
                </span>
                <span className="hidden min-w-0 sm:block">
                  <span className="block truncate text-xs font-bold text-slate-900">{displayName}</span>
                  <span className="block truncate text-[10px] font-medium text-slate-500">{user?.email}</span>
                </span>
                <UserIcon className="h-4 w-4 shrink-0 text-slate-400 sm:hidden" aria-hidden="true" />
              </NavLink>

              <button
                type="button"
                onClick={logout}
                aria-label="Cerrar sesión"
                title="Cerrar sesión"
                className="flex h-10 items-center gap-2 rounded-xl border border-state-danger/25 bg-white px-2.5 text-state-danger transition-colors hover:border-state-danger/40 hover:bg-state-danger/5 sm:px-3"
              >
                <LogOut className="h-4 w-4 shrink-0" />
                <span className="hidden text-xs font-semibold sm:inline">Salir</span>
              </button>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 sm:py-8">
          <div className="mx-auto max-w-6xl space-y-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
