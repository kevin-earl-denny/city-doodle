import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider, ToastProvider, ToastContainer } from './contexts'
import { AuthNotConfigured } from './components/AuthNotConfigured'
import { ClerkWithRouter } from './components/ClerkWithRouter'
import { App } from './App'
import './index.css'

const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY?.trim()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,        // 30 seconds before data is considered stale
      gcTime: 5 * 60_000,       // 5 minutes garbage collection (keep unused cache)
      refetchOnWindowFocus: false, // Don't silently refetch when user returns to tab
      refetchOnReconnect: true,   // Do refetch after network recovery
      retry: 1,                   // Retry failed requests once before erroring
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {clerkPublishableKey ? (
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ClerkWithRouter publishableKey={clerkPublishableKey}>
            <AuthProvider>
              <ToastProvider>
                <App />
                <ToastContainer />
              </ToastProvider>
            </AuthProvider>
          </ClerkWithRouter>
        </BrowserRouter>
      </QueryClientProvider>
    ) : (
      // No key: show setup instructions rather than crash or run unauthenticated.
      <AuthNotConfigured />
    )}
  </StrictMode>,
)
