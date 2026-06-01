import { Navigate, Outlet } from "react-router-dom";
import { getAccessToken } from "../../lib/auth";

export function AuthGuard() {
  if (!getAccessToken()) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}
