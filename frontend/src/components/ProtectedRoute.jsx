import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function ProtectedRoute({ children, roles }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div className="center-screen"><div className="spinner" /> Loading...</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (roles?.length && !roles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }

  return children;
}
