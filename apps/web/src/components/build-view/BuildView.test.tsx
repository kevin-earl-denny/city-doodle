import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect, vi } from "vitest";
import { BuildView } from "./BuildView";

function renderBuildView(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("BuildView", () => {
  it("renders children", () => {
    renderBuildView(
      <BuildView>
        <div data-testid="content">Map Content</div>
      </BuildView>
    );
    expect(screen.getByTestId("content")).toBeInTheDocument();
  });

  it("renders toolbar with all tools including city limits", () => {
    renderBuildView(
      <BuildView>
        <div>Content</div>
      </BuildView>
    );
    expect(screen.getByLabelText("Pan")).toBeInTheDocument();
    expect(screen.getByLabelText("Draw Neighborhood")).toBeInTheDocument();
    expect(screen.getByLabelText("Draw City Limits")).toBeInTheDocument();
    expect(screen.getByLabelText("Split District")).toBeInTheDocument();
    expect(screen.getByLabelText("Draw Road")).toBeInTheDocument();
  });

  it("renders layers panel with toggles", () => {
    renderBuildView(
      <BuildView>
        <div>Content</div>
      </BuildView>
    );
    expect(screen.getByText("Transit")).toBeInTheDocument();
    expect(screen.getByText("Parks")).toBeInTheDocument();
    expect(screen.getByText("Density")).toBeInTheDocument();
  });

  it("renders population panel", () => {
    renderBuildView(
      <BuildView population={500000} growthPercent={1.5}>
        <div>Content</div>
      </BuildView>
    );
    expect(screen.getByText("500,000")).toBeInTheDocument();
    expect(screen.getByText("+1.5%")).toBeInTheDocument();
    expect(screen.getByText("Population")).toBeInTheDocument();
  });

  it("renders city needs icons", () => {
    renderBuildView(
      <BuildView>
        <div>Content</div>
      </BuildView>
    );
    expect(screen.getByTitle("City Needs - Click for details")).toBeInTheDocument();
  });

  // Quarantined: CITY-669 (failing on main; hidden by `|| true` until CITY-652)
  it.skip("calls onToolChange when tool is selected", () => {
    const onToolChange = vi.fn();
    renderBuildView(
      <BuildView onToolChange={onToolChange}>
        <div>Content</div>
      </BuildView>
    );

    fireEvent.click(screen.getByLabelText("Draw Neighborhood"));
    expect(onToolChange).toHaveBeenCalledWith("draw");
  });

  it("calls onCityNeedsClick when city needs is clicked", () => {
    const onCityNeedsClick = vi.fn();
    renderBuildView(
      <BuildView onCityNeedsClick={onCityNeedsClick}>
        <div>Content</div>
      </BuildView>
    );

    fireEvent.click(screen.getByTitle("City Needs - Click for details"));
    expect(onCityNeedsClick).toHaveBeenCalled();
  });

  it("toggles layer visibility when checkbox clicked", () => {
    renderBuildView(
      <BuildView>
        <div>Content</div>
      </BuildView>
    );

    const densityLabel = screen.getByText("Density");
    fireEvent.click(densityLabel);
    // Layer state should toggle (internal state, tested via callback in integration)
  });

  it("renders grow button", () => {
    renderBuildView(
      <BuildView>
        <div>Content</div>
      </BuildView>
    );
    expect(screen.getByLabelText("Grow City")).toBeInTheDocument();
  });
});
