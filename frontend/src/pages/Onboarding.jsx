import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';
import './Onboarding.css';

export default function Onboarding() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const user = JSON.parse(localStorage.getItem('user') || '{}');

  const [formData, setFormData] = useState({
    name: user.name || '',
    skills_text: '',
    intent_text: '',
  });
  const [profilePic, setProfilePic] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setError('');
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) {
        setError('Image must be less than 5MB');
        return;
      }
      setProfilePic(file);
      setPreviewUrl(URL.createObjectURL(file));
    }
  };

  const getInitials = (name) => {
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const canProceed = () => {
    if (step === 1) return formData.name.trim().length > 0;
    if (step === 2) return formData.skills_text.trim().length > 0;
    if (step === 3) return formData.intent_text.trim().length > 0;
    return true;
  };

  const handleNext = () => {
    if (canProceed()) {
      setStep(prev => prev + 1);
    }
  };

  const handleBack = () => {
    setStep(prev => prev - 1);
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError('');

    try {
      const payload = new FormData();
      payload.append('name', formData.name);
      payload.append('skills_text', formData.skills_text);
      payload.append('intent_text', formData.intent_text);
      if (profilePic) {
        payload.append('profile_pic', profilePic);
      }

      await api.post('/v1/profile/', payload, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      // Update local user data
      const updatedUser = { ...user, name: formData.name };
      localStorage.setItem('user', JSON.stringify(updatedUser));

      navigate('/dashboard');
    } catch (err) {
      console.error('Onboarding failed:', err);
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="onboarding">
      <div className="onboarding__container">
        {/* ── Header ── */}
        <div className="onboarding__header">
          <span className="onboarding__logo">⬡ TeamUp</span>
          <div className="onboarding__progress">
            {[1, 2, 3, 4].map(s => (
              <div
                key={s}
                className={`onboarding__progress-dot ${s === step ? 'onboarding__progress-dot--active' : ''} ${s < step ? 'onboarding__progress-dot--done' : ''}`}
              />
            ))}
          </div>
        </div>

        {/* ── Step 1: Name & Photo ── */}
        {step === 1 && (
          <div className="onboarding__step" key="step1">
            <h1 className="onboarding__title">Let's set up your profile</h1>
            <p className="onboarding__desc">How should other students know you?</p>

            <div className="onboarding__photo-section">
              <div
                className="onboarding__photo"
                onClick={() => fileInputRef.current?.click()}
              >
                {previewUrl ? (
                  <img src={previewUrl} alt="Profile" className="onboarding__photo-img" />
                ) : (
                  <span className="onboarding__photo-initials">
                    {formData.name ? getInitials(formData.name) : '?'}
                  </span>
                )}
                <div className="onboarding__photo-overlay">
                  <span>Upload</span>
                </div>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />
              <span className="onboarding__photo-hint">Click to upload (optional)</span>
            </div>

            <div className="onboarding__field">
              <label className="onboarding__label">Your name</label>
              <input
                type="text"
                className="onboarding__input"
                value={formData.name}
                onChange={(e) => handleChange('name', e.target.value)}
                placeholder="e.g. Arjun Mehta"
                autoFocus
              />
            </div>
          </div>
        )}

        {/* ── Step 2: Skills ── */}
        {step === 2 && (
          <div className="onboarding__step" key="step2">
            <h1 className="onboarding__title">What are your skills?</h1>
            <p className="onboarding__desc">
              List your technical skills, tools, languages — anything you bring to a team.
              Just type naturally.
            </p>

            <div className="onboarding__field">
              <label className="onboarding__label">Your skills</label>
              <textarea
                className="onboarding__textarea"
                value={formData.skills_text}
                onChange={(e) => handleChange('skills_text', e.target.value)}
                placeholder="e.g. Python, TensorFlow, LSTM networks, data visualization, SQL, Flask..."
                rows={5}
                autoFocus
              />
              <span className="onboarding__hint">
                Tip: Be specific. "TensorFlow" is better than just "Machine Learning"
              </span>
            </div>
          </div>
        )}

        {/* ── Step 3: Intent ── */}
        {step === 3 && (
          <div className="onboarding__step" key="step3">
            <h1 className="onboarding__title">What do you want to build?</h1>
            <p className="onboarding__desc">
              Describe the kind of project you're looking for or currently working on.
              This is what helps us find your perfect teammates.
            </p>

            <div className="onboarding__field">
              <label className="onboarding__label">Your project vision</label>
              <textarea
                className="onboarding__textarea"
                value={formData.intent_text}
                onChange={(e) => handleChange('intent_text', e.target.value)}
                placeholder="e.g. I want to build a stock price prediction model using deep learning and historical financial data from Yahoo Finance..."
                rows={5}
                autoFocus
              />
              <span className="onboarding__hint">
                Tip: The more detail you give, the better your matches will be
              </span>
            </div>
          </div>
        )}

        {/* ── Step 4: Review ── */}
        {step === 4 && (
          <div className="onboarding__step" key="step4">
            <h1 className="onboarding__title">Looking good!</h1>
            <p className="onboarding__desc">
              Here's a quick summary. You can always edit this later.
            </p>

            <div className="onboarding__review">
              <div className="onboarding__review-header">
                <div className="onboarding__review-avatar">
                  {previewUrl ? (
                    <img src={previewUrl} alt="Profile" className="onboarding__photo-img" />
                  ) : (
                    <span className="onboarding__photo-initials">
                      {getInitials(formData.name)}
                    </span>
                  )}
                </div>
                <div>
                  <h3 className="onboarding__review-name">{formData.name}</h3>
                  <span className="onboarding__review-email">{user.email}</span>
                </div>
              </div>

              <div className="onboarding__review-section">
                <h4>Skills</h4>
                <p>{formData.skills_text}</p>
              </div>

              <div className="onboarding__review-section">
                <h4>Project Vision</h4>
                <p>{formData.intent_text}</p>
              </div>
            </div>
          </div>
        )}

        {/* ── Error ── */}
        {error && <div className="onboarding__error">{error}</div>}

        {/* ── Actions ── */}
        <div className="onboarding__actions">
          {step > 1 && (
            <button className="onboarding__btn onboarding__btn--back" onClick={handleBack}>
              Back
            </button>
          )}

          {step < 4 ? (
            <button
              className="onboarding__btn onboarding__btn--next"
              onClick={handleNext}
              disabled={!canProceed()}
            >
              Continue
            </button>
          ) : (
            <button
              className="onboarding__btn onboarding__btn--submit"
              onClick={handleSubmit}
              disabled={loading}
            >
              {loading ? 'Setting up...' : 'Start finding teammates'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}