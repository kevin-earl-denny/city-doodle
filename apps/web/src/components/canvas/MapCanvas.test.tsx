import { render as rtlRender, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect } from "vitest";
import { MapCanvas } from "./MapCanvas";

// The component reads from react-query, so every render needs a client.
function render(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return rtlRender(ui, {
    wrapper: ({ children }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  });
}

// PixiJS mocks are in test/setup.ts

describe("MapCanvas", () => {
  it("renders loading state initially", () => {
    render(<MapCanvas />);
    expect(screen.getByText("Loading canvas...")).toBeInTheDocument();
  });

  it("accepts className prop", () => {
    const { container } = render(<MapCanvas className="test-class" />);
    expect(container.firstChild).toHaveClass("test-class");
  });
});
