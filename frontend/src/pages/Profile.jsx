import { useState, useEffect, useRef } from 'react';
import api from '../api/axios';
import Navbar from '../components/Navbar';
import './Profile.css';

export default function Profile() {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploadingPic, setUploadingPic] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Edit form state
  const [editName, setEditName] = useState('');
  const [editSkills, setEditSkills] = useState('');
  const [editIntent, setEditIntent] = useState('');

  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [userRes, profileRes] = await Promise.allSettled([
        api.get('/v1/user/'),
        api.get('/v1/profile/'),
      ]);
      if (userRes.status === 'fulfilled') setUser(userRes.value.data);
      if (profileRes.status === 'fulfilled' && profileRes.value.status === 200) {
        setProfile(profileRes.value.data);
      }
    } catch (err) {
      console.error('Failed to fetch profile data:', err);
    } finally {
      setLoading(false);
    }
  };

  const startEditing = () => {
    setEditName(user?.name || '');
    setEditSkills(profile?.skills_text || '');
    setEditIntent(profile?.intent_text || '');
    setError('');
    setSuccess('');
    setEditing(true);
  };

  const cancelEditing = () => {
    setEditing(false);
    setError('');
  };

  const handleSave = async () => {
    if (!editName.trim()) { setError('Name is required.'); return; }
    if (!editSkills.trim()) { setError('Skills are required.'); return; }
    if (!editIntent.trim()) { setError('Project intent is required.'); return; }

    setSaving(true);
    setError('');
    try {
      // Update name
      await api.put('/v1/user/', { name: editName.trim() });

      // Update profile (regenerates embeddings)
      await api.post('/v1/profile/', {
        skills_text: editSkills.trim(),
        intent_text: editIntent.trim(),
      });

      // Refresh data
      await fetchData();

      // Update localStorage user name
      const stored = JSON.parse(localStorage.getItem('user') || '{}');
      stored.name = editName.trim();
      localStorage.setItem('user', JSON.stringify(stored));

      setEditing(false);
      setSuccess('Profile updated successfully.');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save changes.');
    } finally {
      setSaving(false);
    }
  };

  const handlePicChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingPic(true);
    try {
      const form = new FormData();
      form.append('profile_pic', file);
      await api.put('/v1/user/photo', form, { headers: { 'Content-Type': 'multipart/form-data' } });
      await fetchData();
    } catch (err) {
      setError('Failed to upload photo.');
    } finally {
      setUploadingPic(false);
    }
  };

  const getInitials = (name) => {
    if (!name) return '?';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  if (loading) {
    return (
      <div className="profile">
        <Navbar />
        <main className="profile__main">
          <div className="profile__skeleton-card" />
          <div className="profile__skeleton-section" />
          <div className="profile__skeleton-section" />
        </main>
      </div>
    );
  }

  return (
    <div className="profile">
      <Navbar />
      <main className="profile__main">

        {/* Header card */}
        <div className="profile__card">
          {/* Avatar + photo edit */}
          <div className="profile__avatar-wrap">
            <div className="profile__avatar">
              {user?.profile_pic
                ? <img src={user.profile_pic} alt={user.name} />
                : <span>{getInitials(user?.name)}</span>
              }
              <button
                className="profile__avatar-edit"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadingPic}
                title="Change photo"
              >
                {uploadingPic
                  ? <span className="profile__avatar-spinner" />
                  : (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
                      <circle cx="12" cy="13" r="4"/>
                    </svg>
                  )
                }
              </button>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              style={{ display: 'none' }}
              onChange={handlePicChange}
            />
          </div>

          {/* Info */}
          <div className="profile__header-info">
            {!editing ? (
              <>
                <h1 className="profile__name">{user?.name || '—'}</h1>
                <p className="profile__email">{user?.email}</p>
                <button className="profile__edit-btn" onClick={startEditing}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                  Edit Profile
                </button>
              </>
            ) : (
              <div className="profile__name-input-wrap">
                <label className="profile__label">Display Name</label>
                <input
                  className="profile__input"
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  placeholder="Your full name"
                  autoFocus
                />
                <p className="profile__email">{user?.email}</p>
              </div>
            )}
          </div>
        </div>

        {success && <div className="profile__success">{success}</div>}
        {error && <div className="profile__error">{error}</div>}

        {/* Skills section */}
        <div className="profile__section">
          <div className="profile__section-header">
            <h2 className="profile__section-title">Skills</h2>
          </div>
          {!editing ? (
            <p className="profile__section-text">
              {profile?.skills_text || <span className="profile__empty">Not set — click Edit Profile to add your skills.</span>}
            </p>
          ) : (
            <>
              <label className="profile__label">Describe your technical skills</label>
              <textarea
                className="profile__textarea"
                value={editSkills}
                onChange={e => setEditSkills(e.target.value)}
                placeholder="e.g. Python, machine learning, NLP, React, system design..."
                rows={4}
              />
            </>
          )}
        </div>

        {/* Intent section */}
        <div className="profile__section">
          <div className="profile__section-header">
            <h2 className="profile__section-title">Project Intent</h2>
          </div>
          {!editing ? (
            <p className="profile__section-text">
              {profile?.intent_text || <span className="profile__empty">Not set — click Edit Profile to describe what you want to build.</span>}
            </p>
          ) : (
            <>
              <label className="profile__label">What do you want to build?</label>
              <textarea
                className="profile__textarea"
                value={editIntent}
                onChange={e => setEditIntent(e.target.value)}
                placeholder="e.g. I want to build a recommendation system that uses collaborative filtering..."
                rows={4}
              />
            </>
          )}
        </div>

        {/* Edit mode actions */}
        {editing && (
          <div className="profile__actions">
            <p className="profile__save-note">
              Saving will regenerate your ML match embeddings.
            </p>
            <div className="profile__action-btns">
              <button className="profile__btn profile__btn--cancel" onClick={cancelEditing} disabled={saving}>
                Cancel
              </button>
              <button className="profile__btn profile__btn--save" onClick={handleSave} disabled={saving}>
                {saving ? 'Saving…' : 'Save Changes'}
              </button>
            </div>
          </div>
        )}

        {/* Last updated */}
        {profile?.updated_at && !editing && (
          <p className="profile__updated">
            Last updated {new Date(profile.updated_at).toLocaleDateString([], { month: 'long', day: 'numeric', year: 'numeric' })}
          </p>
        )}

      </main>
    </div>
  );
}
