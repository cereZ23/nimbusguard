"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import api from "@/lib/api";
import type {
  LoginRequest,
  MfaRequiredResponse,
  RegisterRequest,
  User,
} from "@/types";

// Access token lifetime in milliseconds (15 minutes)
const TOKEN_LIFETIME_MS = 15 * 60 * 1000;
// Warning fires 2 minutes before expiry
const WARNING_BEFORE_EXPIRY_MS = 2 * 60 * 1000;

/** Thrown when login succeeds but MFA verification is required. */
export class MfaRequiredError extends Error {
  mfaToken: string;
  constructor(mfaToken: string) {
    super("MFA verification required");
    this.name = "MfaRequiredError";
    this.mfaToken = mfaToken;
  }
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  showSessionWarning: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  completeMfaLogin: (mfaToken: string, code: string) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  extendSession: () => Promise<void>;
  dismissSessionWarning: () => void;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showSessionWarning, setShowSessionWarning] = useState(false);
  const [tokenExpiresAt, setTokenExpiresAt] = useState<number | null>(null);
  const warningTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isAuthenticated = user !== null;

  // Helper to set token expiry estimate from current time
  const markTokenIssued = useCallback(() => {
    const expiresAt = Date.now() + TOKEN_LIFETIME_MS;
    setTokenExpiresAt(expiresAt);
    setShowSessionWarning(false);
  }, []);

  // Clear any existing warning timer
  const clearWarningTimer = useCallback(() => {
    if (warningTimerRef.current !== null) {
      clearTimeout(warningTimerRef.current);
      warningTimerRef.current = null;
    }
  }, []);

  // Set up warning timer when tokenExpiresAt changes
  useEffect(() => {
    clearWarningTimer();

    if (tokenExpiresAt === null) {
      return;
    }

    const timeUntilWarning =
      tokenExpiresAt - WARNING_BEFORE_EXPIRY_MS - Date.now();

    if (timeUntilWarning <= 0) {
      // Already past the warning threshold — show immediately
      // (but only if token hasn't fully expired yet)
      if (tokenExpiresAt > Date.now()) {
        setShowSessionWarning(true);
      }
      return;
    }

    warningTimerRef.current = setTimeout(() => {
      setShowSessionWarning(true);
    }, timeUntilWarning);

    return () => {
      clearWarningTimer();
    };
  }, [tokenExpiresAt, clearWarningTimer]);

  // Check for existing session on mount by calling /auth/me
  // The httpOnly cookie is sent automatically via withCredentials
  useEffect(() => {
    api
      .get("/auth/me")
      .then((res) => {
        setUser(res.data.data as User);
        // Estimate token expiry from now — we don't know exactly when
        // the token was issued, so assume it was recently refreshed
        markTokenIssued();
      })
      .catch(() => {
        setUser(null);
      })
      .finally(() => setIsLoading(false));
  }, [markTokenIssued]);

  const login = useCallback(
    async (credentials: LoginRequest) => {
      // POST /auth/login sets httpOnly cookies automatically
      const loginRes = await api.post("/auth/login", credentials);

      // Check if MFA is required
      const responseData = loginRes.data.data as
        | MfaRequiredResponse
        | Record<string, unknown>;
      if (
        responseData &&
        "mfa_required" in responseData &&
        responseData.mfa_required
      ) {
        throw new MfaRequiredError(
          (responseData as MfaRequiredResponse).mfa_token,
        );
      }

      // Fetch user profile now that cookies are set
      const userResponse = await api.get("/auth/me");
      setUser(userResponse.data.data as User);
      markTokenIssued();
    },
    [markTokenIssued],
  );

  const completeMfaLogin = useCallback(
    async (mfaToken: string, code: string) => {
      // POST /auth/mfa/login verifies TOTP and sets httpOnly cookies
      await api.post("/auth/mfa/login", {
        mfa_token: mfaToken,
        code,
      });

      // Fetch user profile now that cookies are set
      const userResponse = await api.get("/auth/me");
      setUser(userResponse.data.data as User);
      markTokenIssued();
    },
    [markTokenIssued],
  );

  const register = useCallback(
    async (data: RegisterRequest) => {
      // POST /auth/register sets httpOnly cookies automatically
      await api.post("/auth/register", data);

      // Fetch user profile now that cookies are set
      const userResponse = await api.get("/auth/me");
      setUser(userResponse.data.data as User);
      markTokenIssued();
    },
    [markTokenIssued],
  );

  const logout = useCallback(async () => {
    clearWarningTimer();
    try {
      // POST /auth/logout clears cookies server-side
      await api.post("/auth/logout");
    } catch {
      // Even if the logout request fails, clear local state
    }
    setUser(null);
    setTokenExpiresAt(null);
    setShowSessionWarning(false);
    window.location.href = "/login";
  }, [clearWarningTimer]);

  const extendSession = useCallback(async () => {
    try {
      await api.post("/auth/refresh", {});
      markTokenIssued();
    } catch {
      // Refresh failed — the 401 interceptor will handle redirect
    }
  }, [markTokenIssued]);

  const dismissSessionWarning = useCallback(() => {
    setShowSessionWarning(false);
  }, []);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated,
      isLoading,
      showSessionWarning,
      login,
      completeMfaLogin,
      register,
      logout,
      extendSession,
      dismissSessionWarning,
    }),
    [
      user,
      isAuthenticated,
      isLoading,
      showSessionWarning,
      login,
      completeMfaLogin,
      register,
      logout,
      extendSession,
      dismissSessionWarning,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
