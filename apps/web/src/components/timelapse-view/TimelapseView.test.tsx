import { render as rtlRender, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect, vi } from "vitest";
import { TimelapseView } from "./TimelapseView";

// The component reads from react-query, so every render needs a client.
function render(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return rtlRender(ui, {
    wrapper: ({ children }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  });
}

describe("TimelapseView", () => {
  it("renders children", () => {
    render(
      <TimelapseView>
        <div data-testid="content">Map Content</div>
      </TimelapseView>
    );
    expect(screen.getByTestId("content")).toBeInTheDocument();
  });

  it("displays date with month and year", () => {
    render(
      <TimelapseView initialDate={new Date(2023, 7, 1)}>
        <div>Content</div>
      </TimelapseView>
    );
    expect(screen.getByText("August 2023")).toBeInTheDocument();
  });

  it("displays year progress", () => {
    render(
      <TimelapseView
        startDate={new Date(2020, 0, 1)}
        endDate={new Date(2026, 1, 1)}
        initialDate={new Date(2023, 0, 1)}
      >
        <div>Content</div>
      </TimelapseView>
    );
    expect(screen.getByText("Year 4 of 7")).toBeInTheDocument();
  });

  it("renders changes panel", () => {
    render(
      <TimelapseView>
        <div>Content</div>
      </TimelapseView>
    );
    expect(screen.getByText("Changes This Year")).toBeInTheDocument();
  });

  it("displays default changes", () => {
    render(
      <TimelapseView>
        <div>Content</div>
      </TimelapseView>
    );
    expect(screen.getByText("3 new blocks built")).toBeInTheDocument();
    expect(screen.getByText("Transit line extended")).toBeInTheDocument();
    expect(screen.getByText("1 park added")).toBeInTheDocument();
  });

  it("displays custom changes", () => {
    const customChanges = [
      { id: "1", description: "New hospital built" },
      { id: "2", description: "Highway extended" },
    ];
    render(
      <TimelapseView changes={customChanges}>
        <div>Content</div>
      </TimelapseView>
    );
    expect(screen.getByText("New hospital built")).toBeInTheDocument();
    expect(screen.getByText("Highway extended")).toBeInTheDocument();
  });

  it("displays view-only mode notice", () => {
    render(
      <TimelapseView>
        <div>Content</div>
      </TimelapseView>
    );
    expect(screen.getByText("View-only mode")).toBeInTheDocument();
  });

  it("renders timeline scrubber", () => {
    render(
      <TimelapseView>
        <div>Content</div>
      </TimelapseView>
    );
    expect(screen.getByRole("slider")).toBeInTheDocument();
  });

  it("displays date range on timeline", () => {
    render(
      <TimelapseView
        startDate={new Date(2020, 0, 1)}
        endDate={new Date(2026, 1, 1)}
      >
        <div>Content</div>
      </TimelapseView>
    );
    // The start date is shown twice: in the current-date display (the
    // scrubber starts at startDate) and as the timeline's start label.
    expect(screen.getAllByText("January 2020")).toHaveLength(2);
    expect(screen.getByText("February 2026")).toBeInTheDocument();
  });

  it("displays year markers", () => {
    render(
      <TimelapseView yearMarkers={[2020, 2022, 2024, 2026]}>
        <div>Content</div>
      </TimelapseView>
    );
    expect(screen.getByText("2020")).toBeInTheDocument();
    expect(screen.getByText("2022")).toBeInTheDocument();
    expect(screen.getByText("2024")).toBeInTheDocument();
    expect(screen.getByText("2026")).toBeInTheDocument();
  });

  it("renders play button initially", () => {
    render(
      <TimelapseView>
        <div>Content</div>
      </TimelapseView>
    );
    expect(screen.getByLabelText("Play")).toBeInTheDocument();
  });

  it("toggles to pause button when clicked", () => {
    render(
      <TimelapseView>
        <div>Content</div>
      </TimelapseView>
    );
    fireEvent.click(screen.getByLabelText("Play"));
    expect(screen.getByLabelText("Pause")).toBeInTheDocument();
  });

  it("renders step back and forward buttons", () => {
    render(
      <TimelapseView>
        <div>Content</div>
      </TimelapseView>
    );
    expect(screen.getByLabelText("Step back")).toBeInTheDocument();
    expect(screen.getByLabelText("Step forward")).toBeInTheDocument();
  });

  it("renders speed selector buttons", () => {
    render(
      <TimelapseView>
        <div>Content</div>
      </TimelapseView>
    );
    expect(screen.getByLabelText("0.5x speed")).toBeInTheDocument();
    expect(screen.getByLabelText("1x speed")).toBeInTheDocument();
    expect(screen.getByLabelText("2x speed")).toBeInTheDocument();
    expect(screen.getByLabelText("4x speed")).toBeInTheDocument();
  });

  it("calls onDateChange when step forward is clicked", () => {
    const onDateChange = vi.fn();
    render(
      <TimelapseView
        initialDate={new Date(2023, 7, 1)}
        endDate={new Date(2026, 1, 1)}
        onDateChange={onDateChange}
      >
        <div>Content</div>
      </TimelapseView>
    );
    fireEvent.click(screen.getByLabelText("Step forward"));
    expect(onDateChange).toHaveBeenCalled();
    const newDate = onDateChange.mock.calls[0][0] as Date;
    expect(newDate.getFullYear()).toBe(2024);
  });

  it("calls onDateChange when step back is clicked", () => {
    const onDateChange = vi.fn();
    render(
      <TimelapseView
        initialDate={new Date(2023, 7, 1)}
        startDate={new Date(2020, 0, 1)}
        onDateChange={onDateChange}
      >
        <div>Content</div>
      </TimelapseView>
    );
    fireEvent.click(screen.getByLabelText("Step back"));
    expect(onDateChange).toHaveBeenCalled();
    const newDate = onDateChange.mock.calls[0][0] as Date;
    expect(newDate.getFullYear()).toBe(2022);
  });

  it("does not render build tools", () => {
    render(
      <TimelapseView>
        <div>Content</div>
      </TimelapseView>
    );
    expect(screen.queryByLabelText("Pan")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Zone")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Build")).not.toBeInTheDocument();
  });
});
