import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL!;

export type MeResponse =
  | { authenticated: false }
  | {
      authenticated: true;
      user: { email: string; name: string; picture: string; sub: string };
      google_connected: boolean;
    };


export type SessionResponse = {
  status: string;
  user: MeResponse;
};


export async function getMe(): Promise<MeResponse> {
  const res = await fetch(`${API}/auth/me`, {
    credentials: "include",
    cache: "no-store",
    headers: {
      "cache-control": "no-cache",
      pragma: "no-cache",
    },
  });
  return res.json();
}

export function loginWithGoogle() {
  window.location.href = `${API}/auth/google/login`;
}

export async function logout() {
  await fetch(`${API}/auth/logout`, { 
    method: "POST", 
    credentials: "include" 
  });
  window.location.reload();
}

// Additional helper for checking auth status
export async function checkAuth(): Promise<boolean> {
  try {
    const result = await getMe();
    return result.authenticated;
  } catch (error) {
    console.error('Auth check failed:', error);
    return false;
  }
}

export async function createSessionFromToken(token: string): Promise<MeResponse> {
  try {
    const response = await fetch(`${API}/auth/session`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ token }),
    });

    if (response.ok) {
      const data: SessionResponse = await response.json();
      console.log('Session created successfully', data.user);
      return data.user;
    } else {
      console.error('Failed to create session');
      return { authenticated: false };
    }
  } catch (error) {
    console.error('Error creating session:', error);
    return { authenticated: false };
  }
}

// Hook for React components
export function useAuth() {
  const [user, setUser] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const authStatus = await getMe();
      console.log("authStatus: ", authStatus);
      setUser(authStatus);
    } catch (error) {
      console.error('Auth check failed:', error);
      setUser({ authenticated: false });
    } finally {
      setLoading(false);
    }
  };

  return {
    user,
    loading,
    loginWithGoogle,
    logout,
    checkAuthStatus
  };
}