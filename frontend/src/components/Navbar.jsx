import { useNavigate, useLocation } from 'react-router-dom';
import './Navbar.css';

export default function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = JSON.parse(localStorage.getItem('user') || '{}');

  const isActive = (path) => location.pathname === path;

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('has_profile');
    localStorage.removeItem('user');
    navigate('/');
  };

  const getInitials = (name) => {
    if (!name) return '?';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  return (
    <nav className="navbar">
      <div className="navbar__inner">
        <div className="navbar__logo" onClick={() => navigate('/dashboard')}>
          <span className="navbar__logo-icon">⬡</span>
          <span className="navbar__logo-text">TeamUp</span>
        </div>

        <div className="navbar__links">
          <button
            className={`navbar__link ${isActive('/dashboard') ? 'navbar__link--active' : ''}`}
            onClick={() => navigate('/dashboard')}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
              <polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
            <span>Home</span>
          </button>

          <button
            className={`navbar__link ${isActive('/chat') ? 'navbar__link--active' : ''}`}
            onClick={() => navigate('/chat')}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            <span>Chat</span>
          </button>

          <button
            className={`navbar__link ${isActive('/profile') ? 'navbar__link--active' : ''}`}
            onClick={() => navigate('/profile')}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
            <span>Profile</span>
          </button>
        </div>

        <div className="navbar__right">
          <div className="navbar__avatar" onClick={handleLogout} title="Logout">
            {getInitials(user.name)}
          </div>
        </div>
      </div>
    </nav>
  );
}