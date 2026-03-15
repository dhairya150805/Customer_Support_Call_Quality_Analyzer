import { Navigate } from "react-router-dom";
import { isAuthenticated } from "@/lib/api";

interface Props {
  children: React.ReactNode;
}

export function PrivateRoute({ children }: Props) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}
