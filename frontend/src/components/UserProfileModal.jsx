import { useEffect } from 'react';
import './UserProfileModal.css';

function getInitials(name) {
  if (!name) return '?';
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
}

export default function UserProfileModal({ user, actionButton, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="upm__overlay" onClick={onClose}>
      <div className="upm__panel" onClick={e => e.stopPropagation()}>
        <button className="upm__close" onClick={onClose} aria-label="Close">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>

        <div className="upm__header">
          <div className="upm__avatar">
            {user.profile_pic
              ? <img src={user.profile_pic} alt={user.name} />
              : <span>{getInitials(user.name)}</span>
            }
          </div>
          <div className="upm__info">
            <h2 className="upm__name">{user.name || '—'}</h2>
            <p className="upm__email">{user.email}</p>
          </div>
        </div>

        {user.skills_text && (
          <div className="upm__section">
            <h3 className="upm__section-title">Skills</h3>
            <p className="upm__section-text">{user.skills_text}</p>
          </div>
        )}

        {user.intent_text && (
          <div className="upm__section">
            <h3 className="upm__section-title">Looking to build</h3>
            <p className="upm__section-text">{user.intent_text}</p>
          </div>
        )}

        {actionButton && (
          <div className="upm__actions">{actionButton}</div>
        )}
      </div>
    </div>
  );
}
