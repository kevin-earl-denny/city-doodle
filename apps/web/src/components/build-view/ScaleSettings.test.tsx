import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ScaleSettings, useScaleSettings } from "./ScaleSettings";
import { CITY_SCALE_PRESETS } from "../../api/types";
import { renderHook, act } from "@testing-library/react";

describe("ScaleSettings", () => {
  const defaultValues = {
    block_size_meters: 100,
    district_size_meters: 3200,
  };

  it("renders collapsed by default", () => {
    const onChange = vi.fn();
    render(<ScaleSettings values={defaultValues} onChange={onChange} />);

    expect(screen.getByText("City Scale")).toBeInTheDocument();
    expect(screen.queryByText("Presets")).not.toBeInTheDocument();
  });

  it("expands when clicked", () => {
    const onChange = vi.fn();
    render(<ScaleSettings values={defaultValues} onChange={onChange} />);

    fireEvent.click(screen.getByText("City Scale"));

    expect(screen.getByText("Presets")).toBeInTheDocument();
    expect(screen.getByText("Block Size")).toBeInTheDocument();
    expect(screen.getByText("District Size")).toBeInTheDocument();
  });

  it("displays current values", () => {
    const onChange = vi.fn();
    render(
      <ScaleSettings
        values={{ block_size_meters: 150, district_size_meters: 700 }}
        onChange={onChange}
      />
    );

    fireEvent.click(screen.getByText("City Scale"));

    expect(screen.getByText("150m")).toBeInTheDocument();
    expect(screen.getByText("700m")).toBeInTheDocument();
  });

  it("calls onChange when block size slider changes", () => {
    const onChange = vi.fn();
    render(<ScaleSettings values={defaultValues} onChange={onChange} />);

    fireEvent.click(screen.getByText("City Scale"));

    const blockSlider = screen.getAllByRole("slider")[0];
    fireEvent.change(blockSlider, { target: { value: "200" } });

    expect(onChange).toHaveBeenCalledWith({
      block_size_meters: 200,
      district_size_meters: 3200,
    });
  });

  it("calls onChange when district size slider changes", () => {
    const onChange = vi.fn();
    render(<ScaleSettings values={defaultValues} onChange={onChange} />);

    fireEvent.click(screen.getByText("City Scale"));

    const districtSlider = screen.getAllByRole("slider")[1];
    // Range is 1000-6000 m in 200 m steps (CITY-220).
    fireEvent.change(districtSlider, { target: { value: "4000" } });

    expect(onChange).toHaveBeenCalledWith({
      block_size_meters: 100,
      district_size_meters: 4000,
    });
  });

  it("renders all preset buttons", () => {
    const onChange = vi.fn();
    render(<ScaleSettings values={defaultValues} onChange={onChange} />);

    fireEvent.click(screen.getByText("City Scale"));

    for (const preset of Object.values(CITY_SCALE_PRESETS)) {
      expect(screen.getByText(preset.name)).toBeInTheDocument();
    }
  });

  it("calls onChange with preset values when preset is clicked", () => {
    const onChange = vi.fn();
    render(<ScaleSettings values={defaultValues} onChange={onChange} />);

    fireEvent.click(screen.getByText("City Scale"));
    fireEvent.click(screen.getByText("Manhattan"));

    expect(onChange).toHaveBeenCalledWith({
      block_size_meters: CITY_SCALE_PRESETS.manhattan.block_size_meters,
      district_size_meters: CITY_SCALE_PRESETS.manhattan.district_size_meters,
    });
  });

  it("highlights active preset", () => {
    const onChange = vi.fn();
    render(
      <ScaleSettings
        values={{
          block_size_meters: CITY_SCALE_PRESETS.portland.block_size_meters,
          district_size_meters: CITY_SCALE_PRESETS.portland.district_size_meters,
        }}
        onChange={onChange}
      />
    );

    fireEvent.click(screen.getByText("City Scale"));

    const portlandButton = screen.getByText("Portland");
    expect(portlandButton).toHaveClass("bg-blue-500");
  });

  it("disables controls when disabled prop is true", () => {
    const onChange = vi.fn();
    render(<ScaleSettings values={defaultValues} onChange={onChange} disabled />);

    const toggleButton = screen.getByText("City Scale").closest("button");
    expect(toggleButton).toBeDisabled();
  });

  it("shows info text about existing districts", () => {
    const onChange = vi.fn();
    render(<ScaleSettings values={defaultValues} onChange={onChange} />);

    fireEvent.click(screen.getByText("City Scale"));

    expect(
      screen.getByText(/Scale affects new districts/i)
    ).toBeInTheDocument();
  });
});

describe("useScaleSettings", () => {
  it("initializes with default values", () => {
    const { result } = renderHook(() => useScaleSettings());

    expect(result.current.values).toEqual({
      block_size_meters: 100,
      district_size_meters: 3200,
    });
  });

  it("initializes with provided values", () => {
    const { result } = renderHook(() =>
      useScaleSettings({
        block_size_meters: 150,
        district_size_meters: 600,
      })
    );

    expect(result.current.values).toEqual({
      block_size_meters: 150,
      district_size_meters: 600,
    });
  });

  it("updates values", () => {
    const { result } = renderHook(() => useScaleSettings());

    act(() => {
      result.current.updateValues({
        block_size_meters: 200,
        district_size_meters: 800,
      });
    });

    expect(result.current.values).toEqual({
      block_size_meters: 200,
      district_size_meters: 800,
    });
  });
});
