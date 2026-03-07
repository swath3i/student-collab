import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { GoogleOAuthProvider } from '@react-oauth/google';
import Landing from './pages/Landing';
import Onboarding from './pages/Onboarding';
import ProtectedRoute from './auth/ProtectedRoute';

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

// Temporary placeholder until we build the real dashboard
function DashboardPlaceholder() {
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  return (
    <div style={{ padding: '48px', fontFamily: 'DM Sans, sans-serif' }}>
      <h1>Welcome, {user.name || 'Student'}!</h1>
      <p style={{ color: '#6B6965', marginTop: '8px' }}>Dashboard coming soon...</p>
      <button
        onClick={() => {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          localStorage.removeItem('user');
          window.location.href = '/';
        }}
        style={{
          marginTop: '24px',
          padding: '10px 20px',
          background: '#E85D2A',
          color: 'white',
          border: 'none',
          borderRadius: '8px',
          cursor: 'pointer',
          fontSize: '0.9rem',
        }}
      >
        Logout
      </button>
    </div>
  );
}

export default function App() {
  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/onboarding" element={
            <ProtectedRoute>
              <Onboarding />
            </ProtectedRoute>
          } />
          <Route path="/dashboard" element={
            <ProtectedRoute>
              <DashboardPlaceholder />
            </ProtectedRoute>
          } />
          {/* We'll add these as we build each screen */}
          {/* <Route path="/onboarding" element={<ProtectedRoute><Onboarding /></ProtectedRoute>} /> */}
          {/* <Route path="/search" element={<ProtectedRoute><Search /></ProtectedRoute>} /> */}
          {/* <Route path="/profile/:id" element={<ProtectedRoute><Profile /></ProtectedRoute>} /> */}
          {/* <Route path="/chat" element={<ProtectedRoute><Chat /></ProtectedRoute>} /> */}
          {/* <Route path="/chat/:connectionId" element={<ProtectedRoute><Chat /></ProtectedRoute>} /> */}
          {/* <Route path="/notifications" element={<ProtectedRoute><Notifications /></ProtectedRoute>} /> */}
        </Routes>
      </BrowserRouter>
    </GoogleOAuthProvider>
  );
}