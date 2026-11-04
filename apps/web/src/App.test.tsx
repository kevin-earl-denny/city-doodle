import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { App } from "./App";
import { AuthProvider } from "./contexts";
import { AuthNotConfigured } from "./components/AuthNotConfigured";
import { getAuthToken, setTokenGetter } from "./api";

// Controllable stand-in for Clerk's session state.
const clerkState = vi.hoisted(() => ({
  isLoaded: true,
  isSignedIn: false,
  userId: null as string | null,
  getToken: async (): Promise<string | null> => null,
  signOut: async () => {},
}));

vi.mock("@clerk/clerk-react", () => ({
  useAuth: () => clerkState,
  SignIn: () => <div data-testid="clerk-sign-in" />,
  SignUp: () => <div data-testid="clerk-sign-up" />,
}));

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function jsonResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: String(status),
    json: () => Promise.resolve(body),
  };
}

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname + location.search}</div>;
}

function renderApp(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <App />
          <LocationProbe />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function signIn() {
  clerkState.isSignedIn = true;
  clerkState.userId = "user_123";
  clerkState.getToken = async () => "clerk-session-jwt";
}

describe("App auth routing (Clerk)", () => {
  beforeEach(() => {
    clerkState.isLoaded = true;
    clerkState.isSignedIn = false;
    clerkState.userId = null;
    clerkState.getToken = async () => null;
    mockFetch.mockReset();
  });

  afterEach(() => {
    setTokenGetter(null);
  });

  it("redirects signed-out visitors from a protected route to Clerk sign-in", async () => {
    renderApp("/worlds/abc");
    expect(await screen.findByTestId("clerk-sign-in")).toBeInTheDocument();
    const location = screen.getByTestId("location").textContent ?? "";
    expect(location.startsWith("/sign-in?redirect_url=")).toBe(true);
    expect(decodeURIComponent(location)).toContain("/worlds/abc");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("renders Clerk sign-up at /sign-up", async () => {
    renderApp("/sign-up");
    expect(await screen.findByTestId("clerk-sign-up")).toBeInTheDocument();
  });

  it("redirects the old /login URL to sign-in", async () => {
    renderApp("/login");
    expect(await screen.findByTestId("clerk-sign-in")).toBeInTheDocument();
  });

  it("redirects /register to sign-up", async () => {
    renderApp("/register");
    expect(await screen.findByTestId("clerk-sign-up")).toBeInTheDocument();
  });

  it("shows a loading state until Clerk has loaded", () => {
    clerkState.isLoaded = false;
    renderApp("/");
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("injects Clerk's getToken into the API client", async () => {
    signIn();
    mockFetch.mockImplementation(() => new Promise(() => {}));
    renderApp("/about");
    await waitFor(async () => expect(await getAuthToken()).toBe("clerk-session-jwt"));
  });

  it("loads the dashboard for a signed-in user, sending the Clerk token", async () => {
    signIn();
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(
        url.includes("/auth/me")
          ? jsonResponse(200, { id: "u1", email: "linked@example.com", created_at: "2024-01-01" })
          : jsonResponse(200, [])
      )
    );

    renderApp("/");

    expect(await screen.findByTestId("dashboard-header")).toBeInTheDocument();
    expect(screen.getByText("linked@example.com")).toBeInTheDocument();
    const meCall = mockFetch.mock.calls.find(([url]) => String(url).includes("/auth/me"));
    expect(meCall?.[1].headers.Authorization).toBe("Bearer clerk-session-jwt");
  });

  it("explains an unverified email instead of looping when the API returns 403", async () => {
    signIn();
    mockFetch.mockResolvedValue(
      jsonResponse(403, { detail: "A verified primary email address is required" })
    );

    renderApp("/");

    expect(await screen.findByTestId("account-error")).toBeInTheDocument();
    expect(screen.getByText(/verify your email address/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
  });

  it("renders the public about page without signing in", async () => {
    renderApp("/about");
    expect(await screen.findByRole("heading", { name: "About" })).toBeInTheDocument();
  });
});

describe("AuthNotConfigured", () => {
  it("tells the developer which env var to set", () => {
    render(<AuthNotConfigured />);
    expect(screen.getByText("VITE_CLERK_PUBLISHABLE_KEY")).toBeInTheDocument();
  });
});
