import { Navigate, Outlet, useLocation } from "react-router-dom";
import { getStoredUser, getToken } from "../lib/auth";

export function RequireAuth() {
  const token = getToken();
  const user = getStoredUser();
  const location = useLocation();
  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (user?.must_change_password && location.pathname !== "/cambiar-contrasena") {
    return <Navigate to="/cambiar-contrasena" replace />;
  }
  return <Outlet />;
}
