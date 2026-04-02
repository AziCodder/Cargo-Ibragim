import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

/**
 * Защищённый маршрут.
 * - Неавторизованный → /login
 * - adminOnly + не admin → /
 */
export default function ProtectedRoute({ children, adminOnly = false }) {
  const { token, isAdmin } = useAuth();

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  if (adminOnly && !isAdmin) {
    return <Navigate to="/" replace />;
  }

  return children;
}
