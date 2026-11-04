/**
 * Authentication context, backed by Clerk (CITY-644).
 *
 * Must be rendered inside <ClerkProvider>. It:
 * - injects Clerk's `getToken` into the API client (layout effect, so it is in
 *   place before any child query's passive effect fires a request);
 * - loads the City Doodle user from GET /auth/me once Clerk reports a session
 *   (the API links/creates the local user on first sign-in);
 * - clears the React Query cache whenever the signed-in Clerk user changes, so
 *   one user's worlds never carry over to the next on the same tab.
 */

import {
  createContext,
  useContext,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  ReactNode,
} from "react";
import { useAuth as useClerkAuth } from "@clerk/clerk-react";
import { useQueryClient } from "@tanstack/react-query";
import { useCurrentUser, setTokenGetter } from "../api";
import type { UserResponse } from "../api";

interface AuthContextValue {
  /** The City Doodle user (from /auth/me), once loaded. */
  user: UserResponse | null;
  /** True while Clerk or /auth/me is still loading. */
  isLoading: boolean;
  /** Clerk has an active session. */
  isSignedIn: boolean;
  /** Signed in with Clerk AND the API accepted the session (/auth/me succeeded). */
  isAuthenticated: boolean;
  /** /auth/me failure for a signed-in Clerk user (e.g. unverified email, API misconfig). */
  error: Error | null;
  /** Re-run /auth/me (e.g. after verifying an email). */
  retry: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, userId, getToken, signOut } = useClerkAuth();
  const queryClient = useQueryClient();
  const signedIn = isLoaded && !!isSignedIn;

  useLayoutEffect(() => {
    setTokenGetter((options) => getToken(options));
    return () => setTokenGetter(null);
  }, [getToken]);

  const lastUserId = useRef<string | null | undefined>(undefined);
  useEffect(() => {
    if (!isLoaded) return;
    if (lastUserId.current !== undefined && lastUserId.current !== userId) {
      queryClient.clear();
    }
    lastUserId.current = userId ?? null;
  }, [isLoaded, userId, queryClient]);

  const {
    data: user,
    isLoading: isLoadingUser,
    error,
    refetch,
  } = useCurrentUser({
    enabled: signedIn,
    retry: false,
  });

  const logout = useCallback(async () => {
    await signOut();
    queryClient.clear();
  }, [signOut, queryClient]);

  const retry = useCallback(() => {
    void refetch();
  }, [refetch]);

  const value: AuthContextValue = useMemo(
    () => ({
      user: signedIn ? user ?? null : null,
      isLoading: !isLoaded || (signedIn && isLoadingUser),
      isSignedIn: signedIn,
      isAuthenticated: signedIn && !!user,
      error: signedIn ? error ?? null : null,
      retry,
      logout,
    }),
    [signedIn, user, isLoaded, isLoadingUser, error, retry, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
