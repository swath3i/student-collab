import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';
import Navbar from '../components/Navbar';
import UserProfileModal from '../components/UserProfileModal';
import './Dashboard.css';

export default function Dashboard() {
  const navigate = useNavigate();
  const [recommendations, setRecommendations] = useState([]);
  const [connections, setConnections] = useState({});
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(null);

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const debounceRef = useRef(null);

  // Profile modal
  const [modalUser, setModalUser] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  // Debounced search
  useEffect(() => {
    clearTimeout(debounceRef.current);
    if (searchQuery.trim().length < 2) {
      setSearchResults([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await api.get(`/v1/user/search?q=${encodeURIComponent(searchQuery.trim())}`);
        setSearchResults(res.data);
      } catch (err) {
        console.error('Search failed:', err);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [searchQuery]);

  const fetchData = async () => {
    try {
      const [recsRes, connsRes] = await Promise.all([
        api.get('/v1/recommendations/'),
        api.get('/v1/connection/'),
      ]);

      setRecommendations(recsRes.data);

      // Build map of user_id → connection info (from connections list + embedded in recs)
      const connMap = {};
      connsRes.data.forEach(conn => {
        connMap[conn.user.id] = {
          status: conn.status,
          direction: conn.direction,
          connection_id: conn.connection_id,
        };
      });
      // Also seed from recommendation's embedded connection field
      recsRes.data.forEach(rec => {
        if (rec.connection && !connMap[rec.id]) {
          connMap[rec.id] = rec.connection;
        }
      });
      setConnections(connMap);
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleConnect = async (userId) => {
    setSending(userId);
    try {
      const res = await api.post('/v1/connection/', { receiver_id: userId });
      // The API returns {status: "success"} — we need to get the connection_id
      // Re-fetch connections to get the new connection_id
      const connsRes = await api.get('/v1/connection/');
      const newConn = connsRes.data.find(c => c.user.id === userId);
      setConnections(prev => ({
        ...prev,
        [userId]: newConn
          ? { status: newConn.status, direction: newConn.direction, connection_id: newConn.connection_id }
          : { status: 'pending', direction: 'sent' },
      }));
    } catch (err) {
      console.error('Failed to send connection:', err);
    } finally {
      setSending(null);
    }
  };

  const handleRespond = async (connectionId, userId, accept) => {
    try {
      await api.put(`/v1/connection/${connectionId}`, { accept });
      setConnections(prev => ({
        ...prev,
        [userId]: { ...prev[userId], status: accept ? 'accepted' : 'declined' },
      }));
    } catch (err) {
      console.error('Failed to respond to connection:', err);
    }
  };

  const getInitials = (name) => {
    if (!name) return '?';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  const getScoreColor = (score) => {
    if (score >= 80) return 'var(--green)';
    if (score >= 60) return 'var(--accent)';
    return 'var(--text-muted)';
  };

  // conn can come from the global connections map OR directly from a search result
  const renderButton = (userId, directConn = null) => {
    const conn = connections[userId] || directConn;

    if (!conn) {
      return (
        <button
          className="dashboard__card-btn dashboard__card-btn--connect"
          onClick={() => handleConnect(userId)}
          disabled={sending === userId}
        >
          {sending === userId ? 'Sending…' : 'Connect'}
        </button>
      );
    }

    if (conn.status === 'pending' && conn.direction === 'sent') {
      return <span className="dashboard__card-status dashboard__card-status--pending">Pending</span>;
    }

    if (conn.status === 'pending' && conn.direction === 'received') {
      return (
        <div className="dashboard__card-actions">
          <button
            className="dashboard__card-btn dashboard__card-btn--accept"
            onClick={() => handleRespond(conn.connection_id, userId, true)}
          >
            Accept
          </button>
          <button
            className="dashboard__card-btn dashboard__card-btn--decline"
            onClick={() => handleRespond(conn.connection_id, userId, false)}
          >
            Decline
          </button>
        </div>
      );
    }

    if (conn.status === 'accepted') {
      return (
        <button
          className="dashboard__card-btn dashboard__card-btn--message"
          onClick={() => navigate('/chat', { state: { connectionId: conn.connection_id } })}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
          Message
        </button>
      );
    }

    return null;
  };

  const renderCard = (user, { showScore = false } = {}) => (
    <div
      className="dashboard__card dashboard__card--clickable"
      key={user.id}
      onClick={() => setModalUser(user)}
    >
      <div className="dashboard__card-left">
        <div className="dashboard__card-avatar">
          {user.profile_pic
            ? <img src={user.profile_pic} alt={user.name} />
            : <span>{getInitials(user.name)}</span>
          }
        </div>
      </div>
      <div className="dashboard__card-body">
        <div className="dashboard__card-top">
          <div>
            <h3 className="dashboard__card-name">{user.name}</h3>
            <p className="dashboard__card-email">{user.email}</p>
          </div>
          {showScore && user.match_score != null && (
            <div className="dashboard__card-score" style={{ color: getScoreColor(user.match_score) }}>
              {user.match_score}% match
            </div>
          )}
        </div>
        {user.skills_text && (
          <div className="dashboard__card-section">
            <h4>Skills</h4>
            <p>{user.skills_text}</p>
          </div>
        )}
        {user.intent_text && (
          <div className="dashboard__card-section">
            <h4>Looking to build</h4>
            <p>{user.intent_text}</p>
          </div>
        )}
        <div className="dashboard__card-footer" onClick={e => e.stopPropagation()}>
          {renderButton(user.id, user.connection || null)}
        </div>
      </div>
    </div>
  );

  const isSearching = searchQuery.trim().length >= 2;

  return (
    <div className="dashboard">
      <Navbar />
      {modalUser && (
        <UserProfileModal
          user={modalUser}
          actionButton={renderButton(modalUser.id, modalUser.connection || null)}
          onClose={() => setModalUser(null)}
        />
      )}

      <main className="dashboard__main">
        {/* Search bar */}
        <div className="dashboard__search-wrap">
          <div className="dashboard__search-box">
            <svg className="dashboard__search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"/>
              <line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              className="dashboard__search-input"
              type="text"
              placeholder="Search students by name…"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              autoComplete="off"
            />
            {searchQuery && (
              <button className="dashboard__search-clear" onClick={() => setSearchQuery('')} aria-label="Clear">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"/>
                  <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            )}
          </div>
        </div>

        {isSearching ? (
          /* ── Search results ── */
          <>
            <div className="dashboard__header">
              <h1 className="dashboard__title">Search results</h1>
              <p className="dashboard__subtitle">
                {searching ? 'Searching…' : `${searchResults.length} student${searchResults.length !== 1 ? 's' : ''} found`}
              </p>
            </div>
            {searching ? (
              <div className="dashboard__loading">
                <div className="dashboard__loading-card" />
                <div className="dashboard__loading-card" />
              </div>
            ) : searchResults.length === 0 ? (
              <div className="dashboard__empty">
                <p>No students found for "{searchQuery}"</p>
              </div>
            ) : (
              <div className="dashboard__feed">
                {searchResults.map(user => renderCard(user))}
              </div>
            )}
          </>
        ) : (
          /* ── Recommendations ── */
          <>
            <div className="dashboard__header">
              <h1 className="dashboard__title">Recommended for you</h1>
              <p className="dashboard__subtitle">Students who match your skills and project vision</p>
            </div>
            {loading ? (
              <div className="dashboard__loading">
                <div className="dashboard__loading-card" />
                <div className="dashboard__loading-card" />
                <div className="dashboard__loading-card" />
              </div>
            ) : recommendations.length === 0 ? (
              <div className="dashboard__empty">
                <p>No recommendations yet. More students need to join!</p>
              </div>
            ) : (
              <div className="dashboard__feed">
                {recommendations.map(user => renderCard(user, { showScore: true }))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
