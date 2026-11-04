/** Rendered instead of the app when VITE_CLERK_PUBLISHABLE_KEY is missing. Never bypasses auth. */
export function AuthNotConfigured() {
  return (
    <div
      className="min-h-screen flex items-center justify-center bg-gray-50 p-6"
      data-testid="auth-not-configured"
    >
      <div className="max-w-md text-center">
        <h1 className="text-3xl font-bold text-gray-900">City Doodle</h1>
        <h2 className="mt-4 text-xl font-semibold text-gray-900">Sign-in is not configured</h2>
        <p className="mt-2 text-gray-600">
          Set <code>VITE_CLERK_PUBLISHABLE_KEY</code> (see <code>apps/web/.env.example</code>) and
          restart the dev server or redeploy.
        </p>
      </div>
    </div>
  )
}
