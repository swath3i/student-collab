import { Navigate, useLocation } from 'react-router-dom';

export default function ProtectedRoute({ children }) {
  const token = localStorage.getItem('access_token');
  const hasProfile = localStorage.getItem('has_profile');
  const location = useLocation();

  if (!token) {
    return <Navigate to="/" replace />;
  }

  // If no profile and not on onboarding, redirect to onboarding
  if (hasProfile !== 'true' && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />;
  }

  // If has profile and on onboarding, redirect to dashboard
  if (hasProfile === 'true' && location.pathname === '/onboarding') {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}