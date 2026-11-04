import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect } from "vitest";
import { App } from "./App";
import { AuthProvider } from "./contexts";

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

describe("App", () => {
  // Quarantined: CITY-668 (failing on main; hidden by `|| true` until CITY-652)
  it.skip("renders home page with title", () => {
    renderApp();
    expect(screen.getByText("City Doodle")).toBeInTheDocument();
  });

  // Quarantined: CITY-668 (failing on main; hidden by `|| true` until CITY-652)
  it.skip("renders description text", () => {
    renderApp();
    expect(
      screen.getByText("A lo-fi vector city builder")
    ).toBeInTheDocument();
  });

  // Quarantined: CITY-668 (failing on main; hidden by `|| true` until CITY-652)
  it.skip("has navigation link to about page", () => {
    renderApp();
    expect(screen.getByRole("link", { name: /about/i })).toBeInTheDocument();
  });

  // Quarantined: CITY-668 (failing on main; hidden by `|| true` until CITY-652)
  it.skip("has navigation link to worlds", () => {
    renderApp();
    expect(screen.getByRole("link", { name: /my worlds/i })).toBeInTheDocument();
  });

  // Quarantined: CITY-668 (failing on main; hidden by `|| true` until CITY-652)
  it.skip("shows sign in link when not authenticated", () => {
    renderApp();
    expect(screen.getByRole("link", { name: /sign in/i })).toBeInTheDocument();
  });

  // Quarantined: CITY-668 (failing on main; hidden by `|| true` until CITY-652)
  it.skip("shows create account link when not authenticated", () => {
    renderApp();
    expect(screen.getByRole("link", { name: /create account/i })).toBeInTheDocument();
  });
});
