import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { TransitView } from "./TransitView";
import { TransitLinesPanel, TransitLine } from "./TransitLinesPanel";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ViewModeProvider } from "../shell/ViewModeContext";

const mockLines: TransitLine[] = [
  { id: "red", name: "Red Line", color: "#DC2626", stations: 10, miles: 5.5, lineType: "subway" },
  { id: "blue", name: "Blue Line", color: "#2563EB", stations: 8, miles: 4.2, lineType: "rail" },
];

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ViewModeProvider>{ui}</ViewModeProvider>
    </QueryClientProvider>
  );
}

describe("TransitView", () => {
  it("renders children", () => {
    renderWithProviders(
      <TransitView>
        <div data-testid="content">Map Content</div>
      </TransitView>
    );
    expect(screen.getByTestId("content")).toBeInTheDocument();
  });

  it("renders transit lines panel", () => {
    renderWithProviders(
      <TransitView lines={mockLines}>
        <div>Content</div>
      </TransitView>
    );
    expect(screen.getByText("Transit Lines")).toBeInTheDocument();
  });

  it("displays transit line names", () => {
    renderWithProviders(
      <TransitView lines={mockLines}>
        <div>Content</div>
      </TransitView>
    );
    expect(screen.getByText("Red Line")).toBeInTheDocument();
    expect(screen.getByText("Blue Line")).toBeInTheDocument();
  });

  it("displays station and mile counts", () => {
    renderWithProviders(
      <TransitView lines={mockLines}>
        <div>Content</div>
      </TransitView>
    );
    expect(screen.getByText("10 stations · 5.5 mi")).toBeInTheDocument();
    expect(screen.getByText("8 stations · 4.2 mi")).toBeInTheDocument();
  });

  it("displays summary statistics in header", () => {
    renderWithProviders(
      <TransitView lines={mockLines}>
        <div>Content</div>
      </TransitView>
    );
    expect(screen.getByText("2 lines")).toBeInTheDocument();
    expect(screen.getByText("18 stations")).toBeInTheDocument();
    expect(screen.getByText("9.7 mi")).toBeInTheDocument();
  });

  it("calls onLineClick when a line is clicked", () => {
    const onLineClick = vi.fn();
    renderWithProviders(
      <TransitView lines={mockLines} onLineClick={onLineClick}>
        <div>Content</div>
      </TransitView>
    );

    fireEvent.click(screen.getByText("Red Line"));
    expect(onLineClick).toHaveBeenCalledWith(mockLines[0]);
  });

  it("does not render build tools", () => {
    renderWithProviders(
      <TransitView>
        <div>Content</div>
      </TransitView>
    );
    // Build tools should not be present in Transit View
    expect(screen.queryByLabelText("Pan")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Zone")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Build")).not.toBeInTheDocument();
  });

  it("shows station placement buttons in empty state", () => {
    renderWithProviders(
      <TransitView>
        <div>Content</div>
      </TransitView>
    );
    expect(screen.getByText("Subway")).toBeInTheDocument();
    expect(screen.getByText("Rail")).toBeInTheDocument();
    expect(screen.getByText("Draw New Line")).toBeInTheDocument();
  });

  it("does not highlight both buttons when no placement context is active", () => {
    renderWithProviders(
      <TransitView lines={mockLines}>
        <div>Content</div>
      </TransitView>
    );
    const subwayButton = screen.getByText("Subway").closest("button")!;
    const railButton = screen.getByText("Rail").closest("button")!;
    expect(subwayButton.className).toContain("bg-gray-100");
    expect(railButton.className).toContain("bg-gray-100");
    expect(subwayButton.className).not.toContain("bg-blue-100");
    expect(railButton.className).not.toContain("bg-blue-100");
  });

  it("clicking station button while no context does not throw", () => {
    renderWithProviders(
      <TransitView>
        <div>Content</div>
      </TransitView>
    );
    // Without PlacementContext or TransitLineDrawingContext, clicking should be a no-op
    expect(() => fireEvent.click(screen.getByText("Subway"))).not.toThrow();
    expect(() => fireEvent.click(screen.getByText("Rail"))).not.toThrow();
    expect(() => fireEvent.click(screen.getByText("Draw New Line"))).not.toThrow();
  });
});

describe("TransitLinesPanel station button highlighting", () => {
  it("highlights only subway button when placing subway", () => {
    render(
      <TransitLinesPanel
        lines={mockLines}
        placingStationType="subway"
        onPlaceSubwayStation={() => {}}
        onPlaceRailStation={() => {}}
      />
    );
    const subwayButton = screen.getByText("Subway").closest("button")!;
    const railButton = screen.getByText("Rail").closest("button")!;
    expect(subwayButton.className).toContain("bg-blue-100");
    expect(railButton.className).toContain("bg-gray-100");
    expect(railButton.className).not.toContain("bg-blue-100");
  });

  it("highlights only rail button when placing rail", () => {
    render(
      <TransitLinesPanel
        lines={mockLines}
        placingStationType="rail"
        onPlaceSubwayStation={() => {}}
        onPlaceRailStation={() => {}}
      />
    );
    const subwayButton = screen.getByText("Subway").closest("button")!;
    const railButton = screen.getByText("Rail").closest("button")!;
    expect(railButton.className).toContain("bg-blue-100");
    expect(subwayButton.className).toContain("bg-gray-100");
    expect(subwayButton.className).not.toContain("bg-blue-100");
  });

  it("highlights neither button when placingStationType is null", () => {
    render(
      <TransitLinesPanel
        lines={mockLines}
        placingStationType={null}
        onPlaceSubwayStation={() => {}}
        onPlaceRailStation={() => {}}
      />
    );
    const subwayButton = screen.getByText("Subway").closest("button")!;
    const railButton = screen.getByText("Rail").closest("button")!;
    expect(subwayButton.className).toContain("bg-gray-100");
    expect(railButton.className).toContain("bg-gray-100");
    expect(subwayButton.className).not.toContain("bg-blue-100");
    expect(railButton.className).not.toContain("bg-blue-100");
  });
});
