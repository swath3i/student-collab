import { GoogleLogin } from '@react-oauth/google';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';

export default function GoogleAuth() {
  const navigate = useNavigate();

  const handleSuccess = async (credentialResponse) => {
    try {
      // Send Google's ID token to Django Ninja backend
      const { data } = await api.post('/v1/auth/login', {
        idToken: credentialResponse.credential,
      });

      // Backend returns JWT + user info
      localStorage.setItem('access_token', data.token);
      localStorage.setItem('refresh_token', data.refresh);
      localStorage.setItem('has_profile', data.has_profile);
      localStorage.setItem('user', JSON.stringify(data.user));

      // Route based on profile status
      if (data.has_profile) {
        navigate('/dashboard');
      } else {
        navigate('/onboarding');
      }
    } catch (error) {
      console.error('Auth failed:', error);
    }
  };

  const handleError = () => {
    console.error('Google Sign-In failed');
  };

  return (
    <GoogleLogin
      onSuccess={handleSuccess}
      onError={handleError}
      theme="outline"
      size="large"
      text="continue_with"
      shape="pill"
      width="320"
    />
  );
}