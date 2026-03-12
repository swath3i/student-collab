import { useState, useEffect } from 'react';
import api from '../api/axios';
import Navbar from '../components/Navbar';
import './Dashboard.css';

export default function Dashboard() {
  const [recommendations, setRecommendations] = useState([]);
  const [connections, setConnections] = useState({});
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [recsRes, connsRes] = await Promise.all([
        api.get('/v1/recommendations/'),
        api.get('/v1/connection/'),
      ]);

      setRecommendations(recsRes.data);

      // Build a map of user_id → connection status
      const connMap = {};
      connsRes.data.forEach(conn => {
        connMap[conn.user.id] = {
          status: conn.status,
          direction: conn.direction,
          connection_id: conn.connection_id,
        };
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
      await api.post('/v1/connection/', { receiver_id: userId });
      // Update local state
      setConnections(prev => ({
        ...prev,
        [userId]: { status: 'pending', direction: 'sent' },
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
        [userId]: {
          ...prev[userId],
          status: accept ? 'accepted' : 'declined',
        },
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

  const renderButton = (userId) => {
    const conn = connections[userId];

    if (!conn) {
      return (
        <button
          className="dashboard__card-btn dashboard__card-btn--connect"
          onClick={() => handleConnect(userId)}
          disabled={sending === userId}
        >
          {sending === userId ? 'Sending...' : 'Connect'}
        </button>
      );
    }

    if (conn.status === 'pending' && conn.direction === 'sent') {
      return (
        <span className="dashboard__card-status dashboard__card-status--pending">
          Pending
        </span>
      );
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
        <span className="dashboard__card-status dashboard__card-status--connected">
          Connected
        </span>
      );
    }

    return null;
  };

  return (
    <div className="dashboard">
      <Navbar />

      <main className="dashboard__main">
        <div className="dashboard__header">
          <h1 className="dashboard__title">Recommended for you</h1>
          <p className="dashboard__subtitle">
            Students who match your skills and project vision
          </p>
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
            {recommendations.map(user => (
              <div className="dashboard__card" key={user.id}>
                <div className="dashboard__card-left">
                  <div className="dashboard__card-avatar">
                    {user.profile_pic ? (
                      <img src={user.profile_pic} alt={user.name} />
                    ) : (
                      <span>{getInitials(user.name)}</span>
                    )}
                  </div>
                </div>

                <div className="dashboard__card-body">
                  <div className="dashboard__card-top">
                    <div>
                      <h3 className="dashboard__card-name">{user.name}</h3>
                      <p className="dashboard__card-email">{user.email}</p>
                    </div>
                    <div
                      className="dashboard__card-score"
                      style={{ color: getScoreColor(user.match_score) }}
                    >
                      {user.match_score}% match
                    </div>
                  </div>

                  <div className="dashboard__card-section">
                    <h4>Skills</h4>
                    <p>{user.skills_text}</p>
                  </div>

                  <div className="dashboard__card-section">
                    <h4>Looking to build</h4>
                    <p>{user.intent_text}</p>
                  </div>

                  <div className="dashboard__card-footer">
                    {renderButton(user.id)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}