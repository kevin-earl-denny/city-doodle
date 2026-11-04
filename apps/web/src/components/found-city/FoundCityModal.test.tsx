import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { FoundCityModal } from "./FoundCityModal";
import { GROWTH_STORIES, getGrowthStory } from "./growthStories";
import { ARCHETYPES } from "./archetypes";

const mutateAsync = vi.fn();

vi.mock("../../api", () => ({
  useCreateWorld: () => ({ mutateAsync, isPending: false }),
}));

function renderModal() {
  const onClose = vi.fn();
  const onCreated = vi.fn();
  render(<FoundCityModal onClose={onClose} onCreated={onCreated} />);
  return { onClose, onCreated };
}

function next() {
  fireEvent.click(screen.getByRole("button", { name: /^Next:/ }));
}

function foundButton() {
  return screen.getByRole("button", { name: /^Found / });
}

describe("FoundCityModal", () => {
  beforeEach(() => {
    mutateAsync.mockReset();
    mutateAsync.mockResolvedValue({ id: "world-42" });
  });

  it("submits the chosen land, story and name as the world settings", async () => {
    const { onCreated } = renderModal();

    fireEvent.click(screen.getByRole("radio", { name: /^Bay & Harbor/ }));
    next();
    fireEvent.click(screen.getByRole("radio", { name: /^Grand Boulevards/ }));
    next();

    fireEvent.change(screen.getByLabelText("City name"), { target: { value: "  Gull Harbor " } });
    fireEvent.change(screen.getByLabelText(/SURVEY Nº/), { target: { value: "48213" } });
    fireEvent.click(foundButton());

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("world-42"));
    expect(mutateAsync).toHaveBeenCalledWith({
      name: "Gull Harbor",
      seed: 48213,
      settings: {
        geographic_setting: "bay_harbor",
        ...getGrowthStory("grand_boulevards").settings,
      },
    });
  });

  it("shows Inland as Plains but submits inland", async () => {
    renderModal();

    const plains = screen.getByRole("radio", { name: /^Plains/ });
    expect(within(plains).getByText("Plains")).toBeInTheDocument();
    expect(within(plains).getByText("Dallas · Calgary")).toBeInTheDocument();
    expect(screen.queryByText("Inland")).not.toBeInTheDocument();

    fireEvent.click(plains);
    expect(plains).toHaveAttribute("aria-checked", "true");
    next();
    next();
    fireEvent.click(foundButton());

    await waitFor(() => expect(mutateAsync).toHaveBeenCalled());
    expect(mutateAsync.mock.calls[0][0].settings.geographic_setting).toBe("inland");
  });

  it("Surprise me jumps to step 3 with valid settings", async () => {
    renderModal();

    fireEvent.click(screen.getByRole("button", { name: "Surprise me" }));

    expect(screen.getByRole("heading", { name: "Name it, and it's yours." })).toBeInTheDocument();
    expect(screen.getByLabelText("City name")).not.toHaveValue("");

    fireEvent.click(foundButton());
    await waitFor(() => expect(mutateAsync).toHaveBeenCalled());

    const { name, seed, settings } = mutateAsync.mock.calls[0][0];
    expect(name.length).toBeGreaterThan(0);
    expect(Number.isInteger(seed)).toBe(true);
    expect(ARCHETYPES.map((a) => a.value)).toContain(settings.geographic_setting);
    const street = { ...settings };
    delete street.geographic_setting;
    expect(GROWTH_STORIES.map((s) => s.settings)).toContainEqual(street);
  });

  it("a slider tweak overrides the story value and marks the story tweaked", async () => {
    renderModal();
    next();

    fireEvent.click(screen.getByRole("radio", { name: /^Motor Sprawl/ }));
    fireEvent.change(screen.getByRole("slider", { name: "Blocks" }), { target: { value: "120" } });
    // Transit shows transit-ness, so 0.8 on the slider is transit_car 0.2.
    fireEvent.change(screen.getByRole("slider", { name: "Transit" }), { target: { value: "0.8" } });

    const card = screen.getByRole("radio", { name: /^Motor Sprawl \(tweaked\)/ });
    expect(card).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText("120 m")).toBeInTheDocument();

    next();
    fireEvent.click(foundButton());
    await waitFor(() => expect(mutateAsync).toHaveBeenCalled());

    const motor = getGrowthStory("motor_sprawl").settings;
    expect(mutateAsync.mock.calls[0][0].settings).toEqual({
      geographic_setting: "coastal",
      ...motor,
      block_size_meters: 120,
      transit_car: 0.2,
    });
  });

  it("picking another story clears the tweaks", () => {
    renderModal();
    next();

    fireEvent.click(screen.getByRole("radio", { name: /^Hill Town/ }));
    fireEvent.change(screen.getByRole("slider", { name: "Blocks" }), { target: { value: "200" } });
    fireEvent.click(screen.getByRole("radio", { name: /^Boomtown Grid/ }));

    expect(screen.getByRole("radio", { name: /^Boomtown Grid:/ })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText("100 m")).toBeInTheDocument();
  });

  it("moves between land cards with arrow keys", () => {
    renderModal();

    const coastal = screen.getByRole("radio", { name: /^Coastal/ });
    fireEvent.keyDown(coastal, { key: "ArrowRight" });

    const bay = screen.getByRole("radio", { name: /^Bay & Harbor/ });
    expect(bay).toHaveAttribute("aria-checked", "true");
    expect(bay).toHaveFocus();
  });

  it("clicking a suggested name sets it", () => {
    renderModal();
    next();
    next();

    const list = screen.getByText("OTHER NAMES ON THE SURVEYOR'S LIST").nextElementSibling as HTMLElement;
    const chips = within(list).getAllByRole("button");
    expect(chips).toHaveLength(4);
    const pick = chips[2].textContent!;
    fireEvent.click(chips[2]);

    expect(screen.getByLabelText("City name")).toHaveValue(pick);
    expect(screen.getByRole("button", { name: `Found ${pick}` })).toBeInTheDocument();
  });

  it("goes back to completed steps from the route", () => {
    renderModal();
    next();
    next();

    fireEvent.click(screen.getByRole("button", { name: /The land/ }));
    expect(screen.getByRole("heading", { name: "Where does your city begin?" })).toBeInTheDocument();
  });

  it("shows the API error inline", async () => {
    mutateAsync.mockRejectedValueOnce(new Error("World limit reached"));
    renderModal();
    next();
    next();
    fireEvent.click(foundButton());

    expect(await screen.findByRole("alert")).toHaveTextContent("World limit reached");
  });

  it("closes on Escape", () => {
    const { onClose } = renderModal();
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("shows Describe it as a disabled, coming-soon tab", () => {
    renderModal();
    const describe = screen.getByRole("tab", { name: /Describe it/ });
    expect(describe).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(describe);
    expect(screen.getByRole("tab", { name: /Draw it/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tooltip")).toHaveTextContent("Coming soon");
  });
});
