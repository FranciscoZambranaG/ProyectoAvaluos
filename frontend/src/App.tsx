import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { RequireAuth } from "./components/RequireAuth";
import { BrandingProvider } from "./lib/branding";
import { AdminBrandingPage } from "./pages/AdminBrandingPage";
import { AdminCatalogsPage } from "./pages/AdminCatalogsPage";
import { AdminCharacteristicsPage } from "./pages/AdminCharacteristicsPage";
import { AdminFormulasPage } from "./pages/AdminFormulasPage";
import { AdminMediaTypesPage } from "./pages/AdminMediaTypesPage";
import { AdminParametersPage } from "./pages/AdminParametersPage";
import { AdminTemplatesPage } from "./pages/AdminTemplatesPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";
import { AdminValuesPage } from "./pages/AdminValuesPage";
import { AppraisalFormPage } from "./pages/AppraisalFormPage";
import { AppraisalPrintPage } from "./pages/AppraisalPrintPage";
import { AppShell } from "./pages/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { FormsPage } from "./pages/FormsPage";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { ForceChangePasswordPage } from "./pages/ForceChangePasswordPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RegisterPage } from "./pages/RegisterPage";

export default function App() {
  return (
    <BrandingProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/registro" element={<RegisterPage />} />
          <Route element={<RequireAuth />}>
            <Route path="/cambiar-contrasena" element={<ForceChangePasswordPage />} />
            <Route path="/app" element={<AppShell />}>
              <Route index element={<DashboardPage />} />
              <Route path="formularios" element={<FormsPage />} />
              <Route path="formularios/nuevo" element={<AppraisalFormPage />} />
              <Route path="formularios/:id" element={<AppraisalFormPage />} />
              <Route path="formularios/:id/imprimir" element={<AppraisalPrintPage />} />
              <Route path="admin/caracteristicas" element={<AdminCharacteristicsPage />} />
              <Route path="admin/catalogos" element={<AdminCatalogsPage />} />
              <Route path="admin/valores" element={<AdminValuesPage />} />
              <Route path="admin/parametros" element={<AdminParametersPage />} />
              <Route path="admin/fotos" element={<AdminMediaTypesPage />} />
              <Route path="admin/formulas" element={<AdminFormulasPage />} />
              <Route path="admin/branding" element={<AdminBrandingPage />} />
              <Route path="admin/plantillas" element={<AdminTemplatesPage />} />
              <Route path="admin/usuarios" element={<AdminUsersPage />} />
              <Route path="perfil" element={<ProfilePage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </BrandingProvider>
  );
}
