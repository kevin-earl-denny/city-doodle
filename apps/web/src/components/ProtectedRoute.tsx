/**
 * Protected route wrapper: sends signed-out visitors to the Clerk sign-in page
 * and waits for the API to accept the Clerk session before rendering.
 */

import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { ApiClientError } from "../api/types";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

function accountErrorMessage(error: Error): string {
  if (error instanceof ApiClientError && error.status === 403) {
    return "Please verify your email address with your sign-in provider, then try again.";
  }
  return "We couldn't load your account. Please try again.";
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isSignedIn, isAuthenticated, isLoading, error, retry, logout } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  if (!isSignedIn) {
    const returnTo = `${window.location.origin}${location.pathname}${location.search}`;
    return (
      <Navigate to={`/sign-in?redirect_url=${encodeURIComponent(returnTo)}`} replace />
    );
  }

  if (!isAuthenticated) {
    // Signed in with Clerk but the API rejected or could not resolve the
    // session. Don't auto sign-out: that would turn an API misconfiguration
    // into a sign-in loop.
    return (
      <div className="min-h-screen flex items-center justify-center" data-testid="account-error">
        <div className="text-center max-w-sm">
          <p className="text-gray-800 mb-4">
            {error ? accountErrorMessage(error) : "We couldn't load your account."}
          </p>
          <div className="flex justify-center gap-4">
            <button onClick={retry} className="text-blue-600 hover:underline">
              Try again
            </button>
            <button onClick={() => void logout()} className="text-gray-600 hover:underline">
              Sign out
            </button>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
