import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import GoogleAuth from '../auth/GoogleAuth';
import './Landing.css';

export default function Landing() {
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      navigate('/dashboard');
    }
  }, [navigate]);

  return (
    <div className="landing">
      {/* ── Decorative background ── */}
      <div className="landing__bg">
        <div className="landing__bg-circle landing__bg-circle--1" />
        <div className="landing__bg-circle landing__bg-circle--2" />
        <div className="landing__bg-circle landing__bg-circle--3" />
      </div>

      {/* ── Nav ── */}
      <nav className="landing__nav">
        <div className="landing__logo">
          <span className="landing__logo-icon">⬡</span>
          TeamUp
        </div>
      </nav>

      {/* ── Hero ── */}
      <main className="landing__hero">
        <div className="landing__hero-content">
          <div className="landing__badge">
            For university students
          </div>
          <h1 className="landing__title">
            Find teammates who
            <span className="landing__title-accent"> actually </span>
            match your project vision
          </h1>
          <p className="landing__subtitle">
            Stop settling for random group members. TeamUp uses smart matching 
            to connect you with students who share your goals, complement your 
            skills, and are ready to build something great together.
          </p>

          <div className="landing__cta">
            <GoogleAuth />
          </div>

          <p className="landing__footnote">
            Free for all university students. No credit card needed.
          </p>
        </div>

        <div className="landing__hero-visual">
          <div className="landing__card landing__card--1">
            <div className="landing__card-avatar" style={{ background: '#E85D2A' }}>AM</div>
            <div className="landing__card-info">
              <span className="landing__card-name">Arjun M.</span>
              <span className="landing__card-skill">Python • LSTM • Finance</span>
            </div>
            <span className="landing__card-match">94%</span>
          </div>
          <div className="landing__card landing__card--2">
            <div className="landing__card-avatar" style={{ background: '#2D8B5F' }}>PS</div>
            <div className="landing__card-info">
              <span className="landing__card-name">Priya S.</span>
              <span className="landing__card-skill">ML • Flask • Fintech</span>
            </div>
            <span className="landing__card-match">89%</span>
          </div>
          <div className="landing__card landing__card--3">
            <div className="landing__card-avatar" style={{ background: '#3B6CE1' }}>RK</div>
            <div className="landing__card-info">
              <span className="landing__card-name">Ravi K.</span>
              <span className="landing__card-skill">R • Tableau • Quant</span>
            </div>
            <span className="landing__card-match">87%</span>
          </div>
          <div className="landing__connector" />
        </div>
      </main>

      {/* ── How it works ── */}
      <section className="landing__steps">
        <h2 className="landing__steps-title">How it works</h2>
        <div className="landing__steps-grid">
          <div className="landing__step">
            <div className="landing__step-number">1</div>
            <h3>Tell us what you're building</h3>
            <p>Describe your skills and project vision in your own words. No rigid forms or dropdowns.</p>
          </div>
          <div className="landing__step">
            <div className="landing__step-number">2</div>
            <h3>Get matched intelligently</h3>
            <p>Our ML engine understands context — "ML + Finance" matches differently than "ML + Healthcare."</p>
          </div>
          <div className="landing__step">
            <div className="landing__step-number">3</div>
            <h3>Connect and collaborate</h3>
            <p>Send connection requests, chat in real-time, and start building your project together.</p>
          </div>
        </div>
      </section>
    </div>
  );
}