import { useState, useEffect, useRef, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import api from '../api/axios';
import Navbar from '../components/Navbar';
import './Chat.css';

function formatTime(isoString) {
  if (!isoString) return '';
  const date = new Date(isoString);
  const now = new Date();
  const isToday =
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear();
  if (isToday) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function formatFullTime(isoString) {
  if (!isoString) return '';
  const date = new Date(isoString);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function getInitials(name) {
  if (!name) return '?';
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
}

export default function Chat() {
  const location = useLocation();
  const [connections, setConnections] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loadingConns, setLoadingConns] = useState(true);
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  const [unreadCounts, setUnreadCounts] = useState({});
  const [mobileShowConv, setMobileShowConv] = useState(false);

  const wsRef = useRef(null);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const currentUser = JSON.parse(localStorage.getItem('user') || '{}');

  useEffect(() => {
    fetchConnections(location.state?.connectionId);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const fetchConnections = async (autoSelectId = null) => {
    setLoadingConns(true);
    try {
      const res = await api.get('/v1/connection/');
      const accepted = res.data.filter(c => c.status === 'accepted');
      accepted.sort((a, b) => {
        const ta = a.last_message?.sent_at || a.connection_id;
        const tb = b.last_message?.sent_at || b.connection_id;
        return tb > ta ? 1 : -1;
      });
      setConnections(accepted);
      const counts = {};
      accepted.forEach(c => { counts[c.connection_id] = c.unread_count || 0; });
      setUnreadCounts(counts);
      if (autoSelectId && accepted.find(c => c.connection_id === autoSelectId)) {
        selectConnection(autoSelectId);
      }
    } catch (err) {
      console.error('Failed to fetch connections:', err);
    } finally {
      setLoadingConns(false);
    }
  };

  const selectConnection = useCallback(async (connId) => {
    if (selectedId === connId) return;
    setSelectedId(connId);
    setMobileShowConv(true);
    setMessages([]);
    setLoadingMsgs(true);

    // Close existing WS
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    // Load messages
    try {
      const res = await api.get(`/v1/connection/${connId}/messages`);
      setMessages(res.data);
    } catch (err) {
      console.error('Failed to load messages:', err);
    } finally {
      setLoadingMsgs(false);
    }

    // Mark read
    try {
      await api.put(`/v1/connection/${connId}/messages/read`);
      setUnreadCounts(prev => ({ ...prev, [connId]: 0 }));
    } catch (_) {}

    // Connect WebSocket
    const token = localStorage.getItem('access_token');
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/chat/${connId}/?token=${token}`);

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      msg.is_mine = msg.sender_id === currentUser.id;
      setMessages(prev => [...prev, msg]);
      if (!msg.is_mine) {
        // Auto-mark read since we're looking at this conversation
        api.put(`/v1/connection/${connId}/messages/read`).catch(() => {});
      }
    };

    ws.onerror = (err) => console.error('WS error:', err);
    wsRef.current = ws;
    setTimeout(() => inputRef.current?.focus(), 100);
  }, [selectedId, currentUser.id]);

  // Cleanup WS on unmount
  useEffect(() => {
    return () => wsRef.current?.close();
  }, []);

  const sendMessage = (e) => {
    e.preventDefault();
    const content = input.trim();
    if (!content) return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      // Fallback to REST
      api.post(`/v1/connection/${selectedId}/messages`, { content })
        .then(res => {
          setMessages(prev => [...prev, {
            id: res.data.id,
            sender_id: currentUser.id,
            content,
            sent_at: res.data.sent_at,
            is_mine: true,
          }]);
        })
        .catch(err => console.error('Send failed:', err));
    } else {
      wsRef.current.send(JSON.stringify({ content }));
    }
    setInput('');
  };

  const selectedConn = connections.find(c => c.connection_id === selectedId);

  return (
    <div className="chat">
      <Navbar />
      <div className="chat__layout">
        {/* Sidebar */}
        <aside className={`chat__sidebar ${mobileShowConv ? 'chat__sidebar--hidden' : ''}`}>
          <div className="chat__sidebar-header">
            <h2 className="chat__sidebar-title">Messages</h2>
          </div>

          {loadingConns ? (
            <div className="chat__sidebar-loading">
              {[1, 2, 3].map(i => (
                <div key={i} className="chat__sidebar-skeleton" />
              ))}
            </div>
          ) : connections.length === 0 ? (
            <div className="chat__sidebar-empty">
              <p>No connections yet.</p>
              <p>Accept a connection request to start chatting.</p>
            </div>
          ) : (
            <ul className="chat__sidebar-list">
              {connections.map(conn => {
                const unread = unreadCounts[conn.connection_id] || 0;
                const isActive = conn.connection_id === selectedId;
                return (
                  <li
                    key={conn.connection_id}
                    className={`chat__sidebar-item ${isActive ? 'chat__sidebar-item--active' : ''}`}
                    onClick={() => selectConnection(conn.connection_id)}
                  >
                    <div className="chat__sidebar-avatar">
                      {conn.user.profile_pic ? (
                        <img src={conn.user.profile_pic} alt={conn.user.name} />
                      ) : (
                        <span>{getInitials(conn.user.name)}</span>
                      )}
                    </div>
                    <div className="chat__sidebar-info">
                      <div className="chat__sidebar-top">
                        <span className="chat__sidebar-name">{conn.user.name}</span>
                        {conn.last_message && (
                          <span className="chat__sidebar-time">
                            {formatTime(conn.last_message.sent_at)}
                          </span>
                        )}
                      </div>
                      <div className="chat__sidebar-bottom">
                        <span className="chat__sidebar-preview">
                          {conn.last_message
                            ? (conn.last_message.sender_id === currentUser.id ? 'You: ' : '') +
                              conn.last_message.content
                            : 'No messages yet'}
                        </span>
                        {unread > 0 && (
                          <span className="chat__sidebar-badge">{unread}</span>
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </aside>

        {/* Conversation */}
        <main className={`chat__conversation ${!mobileShowConv ? 'chat__conversation--hidden-mobile' : ''}`}>
          {!selectedId ? (
            <div className="chat__empty-state">
              <div className="chat__empty-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
              </div>
              <h3>Select a conversation</h3>
              <p>Choose a connection from the left to start chatting</p>
            </div>
          ) : (
            <>
              {/* Header */}
              <div className="chat__conv-header">
                <button
                  className="chat__back-btn"
                  onClick={() => setMobileShowConv(false)}
                  aria-label="Back"
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="15 18 9 12 15 6"/>
                  </svg>
                </button>
                <div className="chat__conv-avatar">
                  {selectedConn?.user.profile_pic ? (
                    <img src={selectedConn.user.profile_pic} alt={selectedConn.user.name} />
                  ) : (
                    <span>{getInitials(selectedConn?.user.name)}</span>
                  )}
                </div>
                <div className="chat__conv-user">
                  <span className="chat__conv-name">{selectedConn?.user.name}</span>
                  <span className="chat__conv-email">{selectedConn?.user.email}</span>
                </div>
              </div>

              {/* Messages */}
              <div className="chat__messages">
                {loadingMsgs ? (
                  <div className="chat__messages-loading">
                    {[1, 2, 3, 4].map(i => (
                      <div key={i} className={`chat__msg-skeleton chat__msg-skeleton--${i % 2 === 0 ? 'right' : 'left'}`} />
                    ))}
                  </div>
                ) : messages.length === 0 ? (
                  <div className="chat__no-messages">
                    <p>No messages yet. Say hello!</p>
                  </div>
                ) : (
                  <>
                    {messages.map((msg, idx) => {
                      const showTime =
                        idx === 0 ||
                        new Date(msg.sent_at) - new Date(messages[idx - 1].sent_at) > 5 * 60 * 1000;
                      return (
                        <div key={msg.id || idx}>
                          {showTime && (
                            <div className="chat__time-divider">
                              {formatFullTime(msg.sent_at)}
                            </div>
                          )}
                          <div className={`chat__msg ${msg.is_mine ? 'chat__msg--mine' : 'chat__msg--theirs'}`}>
                            <div className="chat__msg-bubble">
                              {msg.content}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                    <div ref={bottomRef} />
                  </>
                )}
              </div>

              {/* Input */}
              <form className="chat__input-bar" onSubmit={sendMessage}>
                <input
                  ref={inputRef}
                  className="chat__input"
                  type="text"
                  placeholder="Type a message…"
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  autoComplete="off"
                />
                <button
                  className="chat__send-btn"
                  type="submit"
                  disabled={!input.trim()}
                  aria-label="Send"
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13"/>
                    <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                  </svg>
                </button>
              </form>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
