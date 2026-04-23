import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import api from '../api/axios';
import './Navbar.css';

export default function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = JSON.parse(localStorage.getItem('user') || '{}');

  const [pendingRequests, setPendingRequests] = useState([]);
  const [totalUnread, setTotalUnread] = useState(0);
  const [showNotifs, setShowNotifs] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [responding, setResponding] = useState(null);

  const bellRef = useRef(null);
  const userMenuRef = useRef(null);

  useEffect(() => {
    fetchConnectionsData();
    const interval = setInterval(fetchConnectionsData, 30000);
    return () => clearInterval(interval);
  }, []);

  // Close dropdowns on outside click
  useEffect(() => {
    const handler = (e) => {
      if (bellRef.current && !bellRef.current.contains(e.target)) setShowNotifs(false);
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) setShowUserMenu(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const fetchConnectionsData = async () => {
    try {
      const res = await api.get('/v1/connection/');
      setPendingRequests(res.data.filter(c => c.status === 'pending' && c.direction === 'received'));
      const unread = res.data
        .filter(c => c.status === 'accepted')
        .reduce((sum, c) => sum + (c.unread_count || 0), 0);
      setTotalUnread(unread);
    } catch (err) {
      console.error('Failed to fetch connections:', err);
    }
  };

  const handleRespond = async (connectionId, accept) => {
    setResponding(connectionId);
    try {
      await api.put(`/v1/connection/${connectionId}`, { accept });
      setPendingRequests(prev => prev.filter(r => r.connection_id !== connectionId));
    } catch (err) {
      console.error('Failed to respond to request:', err);
    } finally {
      setResponding(null);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('has_profile');
    localStorage.removeItem('user');
    navigate('/');
  };

  const isActive = (path) => location.pathname === path;

  const getInitials = (name) => {
    if (!name) return '?';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  return (
    <nav className="navbar">
      <div className="navbar__inner">
        {/* Logo */}
        <div className="navbar__logo" onClick={() => navigate('/dashboard')}>
          <span className="navbar__logo-icon">⬡</span>
          <span className="navbar__logo-text">TeamUp</span>
        </div>

        {/* Nav links */}
        <div className="navbar__links">
          {/* Home */}
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

          {/* Chat — with unread badge */}
          <button
            className={`navbar__link ${isActive('/chat') ? 'navbar__link--active' : ''}`}
            onClick={() => navigate('/chat')}
          >
            <div className="navbar__bell-wrap">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
              {totalUnread > 0 && !isActive('/chat') && (
                <span className="navbar__badge">{totalUnread > 99 ? '99+' : totalUnread}</span>
              )}
            </div>
            <span>Chat</span>
          </button>

          {/* Notification Bell — connection requests */}
          <div className="navbar__notif-wrap" ref={bellRef}>
            <button
              className={`navbar__link ${showNotifs ? 'navbar__link--active' : ''}`}
              onClick={() => setShowNotifs(v => !v)}
              aria-label="Connection requests"
            >
              <div className="navbar__bell-wrap">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                  <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                </svg>
                {pendingRequests.length > 0 && (
                  <span className="navbar__badge">{pendingRequests.length}</span>
                )}
              </div>
              <span>Requests</span>
            </button>

            {showNotifs && (
              <div className="navbar__notif-dropdown">
                <div className="navbar__notif-header">Connection Requests</div>
                {pendingRequests.length === 0 ? (
                  <p className="navbar__notif-empty">No pending requests</p>
                ) : (
                  <ul className="navbar__notif-list">
                    {pendingRequests.map(req => (
                      <li key={req.connection_id} className="navbar__notif-item">
                        <div className="navbar__notif-avatar">
                          {req.user.profile_pic
                            ? <img src={req.user.profile_pic} alt={req.user.name} />
                            : <span>{getInitials(req.user.name)}</span>
                          }
                        </div>
                        <div className="navbar__notif-info">
                          <span className="navbar__notif-name">{req.user.name}</span>
                          <span className="navbar__notif-sub">wants to connect</span>
                        </div>
                        <div className="navbar__notif-actions">
                          <button
                            className="navbar__notif-btn navbar__notif-btn--accept"
                            onClick={() => handleRespond(req.connection_id, true)}
                            disabled={responding === req.connection_id}
                            aria-label="Accept"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="20 6 9 17 4 12"/>
                            </svg>
                          </button>
                          <button
                            className="navbar__notif-btn navbar__notif-btn--decline"
                            onClick={() => handleRespond(req.connection_id, false)}
                            disabled={responding === req.connection_id}
                            aria-label="Decline"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                              <line x1="18" y1="6" x2="6" y2="18"/>
                              <line x1="6" y1="6" x2="18" y2="18"/>
                            </svg>
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>

          {/* Profile */}
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

        {/* User menu / Logout */}
        <div className="navbar__right">
          <div className="navbar__user-wrap" ref={userMenuRef}>
            <button
              className="navbar__avatar"
              onClick={() => setShowUserMenu(v => !v)}
              aria-label="User menu"
            >
              {getInitials(user.name)}
            </button>

            {showUserMenu && (
              <div className="navbar__user-dropdown">
                <div className="navbar__user-info">
                  <span className="navbar__user-name">{user.name || 'User'}</span>
                  <span className="navbar__user-email">{user.email}</span>
                </div>
                <div className="navbar__user-divider" />
                <button className="navbar__user-item navbar__user-item--profile" onClick={() => { setShowUserMenu(false); navigate('/profile'); }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                    <circle cx="12" cy="7" r="4"/>
                  </svg>
                  View Profile
                </button>
                <button className="navbar__user-item navbar__user-item--logout" onClick={handleLogout}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                    <polyline points="16 17 21 12 16 7"/>
                    <line x1="21" y1="12" x2="9" y2="12"/>
                  </svg>
                  Log out
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
