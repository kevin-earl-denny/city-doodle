import { lazy, Suspense } from 'react'
import { Routes, Route, Link, Navigate } from 'react-router-dom'
import { ProtectedRoute } from './components/ProtectedRoute'
import { CityLoader } from './components/ui'

// Route-level code splitting: each page is loaded on demand so that
// sign-in/sign-up never pull in PixiJS, MapCanvas, or EditorShell.
const SignInPage = lazy(() =>
  import('./pages/SignInPage').then((m) => ({ default: m.SignInPage }))
)
const SignUpPage = lazy(() =>
  import('./pages/SignUpPage').then((m) => ({ default: m.SignUpPage }))
)
const WorldsPage = lazy(() =>
  import('./pages/WorldsPage').then((m) => ({ default: m.WorldsPage }))
)
const WorldEditorPage = lazy(() =>
  import('./pages/WorldEditorPage').then((m) => ({ default: m.WorldEditorPage }))
)

function About() {
  return (
    <div className="p-8">
      <h1 className="text-4xl font-bold text-gray-900">About</h1>
      <p className="mt-2 text-gray-600">
        City Doodle is a lightweight planning sim disguised as a map doodle.
      </p>
      <nav className="mt-4">
        <Link to="/" className="text-blue-600 hover:underline">
          Home
        </Link>
      </nav>
    </div>
  )
}

export function App() {
  return (
    <Suspense fallback={<CityLoader variant="page" />}>
      <Routes>
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <WorldsPage />
            </ProtectedRoute>
          }
        />
        {/* Clerk renders multi-step flows (verification, SSO callbacks) under these paths. */}
        <Route path="/sign-in/*" element={<SignInPage />} />
        <Route path="/sign-up/*" element={<SignUpPage />} />
        {/* Pre-Clerk URLs (CITY-644) */}
        <Route path="/login" element={<Navigate to="/sign-in" replace />} />
        <Route path="/register" element={<Navigate to="/sign-up" replace />} />
        <Route path="/worlds" element={<Navigate to="/" replace />} />
        <Route
          path="/worlds/:worldId"
          element={
            <ProtectedRoute>
              <WorldEditorPage />
            </ProtectedRoute>
          }
        />
        <Route path="/about" element={<About />} />
      </Routes>
    </Suspense>
  )
}
