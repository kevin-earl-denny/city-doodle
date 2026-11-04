import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { ApiClientError, type WorldBrief, type WorldBriefResponse } from "../../api/types";
import { FoundCityModal } from "./FoundCityModal";

const createWorld = vi.fn();
const requestBrief = vi.fn();

vi.mock("../../api", async () => {
  const React = await vi.importActual<typeof import("react")>("react");
  const types = await vi.importActual<typeof import("../../api/types")>("../../api/types");
  return {
    ApiClientError: types.ApiClientError,
    useCreateWorld: () => ({ mutateAsync: createWorld, isPending: false }),
    // Tracks isPending like react-query so the surveying state renders.
    useWorldBrief: () => {
      const [isPending, setPending] = React.useState(false);
      return {
        isPending,
        mutateAsync: async (body: unknown) => {
          setPending(true);
          try {
            return await requestBrief(body);
          } finally {
            setPending(false);
          }
        },
      };
    },
  };
});

const BRIEF: WorldBrief = {
  archetype: "bay_harbor",
  water_side: "south_east",
  river: { count: 1, course: "meandering", axis: "north_south" },
  relief: "hilly",
  coast: "varied",
  growth_story: "hill_town",
  sliders: {
    grid_organic: 0.8,
    sprawl_compact: 0.8,
    transit_car: 0.3,
    historic_modern: 0.3,
    block_size_meters: 70,
    district_size_meters: 1400,
  },
  name: "Porto Gelo",
  name_suggestions: ["Wrenmouth", "Gull Harbor", "Saltmarsh", "Cold Quay"],
  founding_year: 1702,
  founding_story: "Fishermen settled the steep west bank in 1702, where the Wren slows into Gull Bay.",
  feels_like: ["Lisbon", "Porto", "Québec City"],
  legend: {
    water: "Bay opens to the south-east",
    river: "One river, winding in from the north",
    ground: "Hilly west bank, flat east bank",
    streets: "Hill Town, then Boomtown Grid",
  },
  unsupported: ["colder"],
};

const RESPONSE: WorldBriefResponse = {
  brief: BRIEF,
  settings: {
    geographic_setting: "bay_harbor",
    grid_organic: 0.8,
    sprawl_compact: 0.8,
    historic_modern: 0.3,
    transit_car: 0.3,
    block_size_meters: 70,
    district_size_meters: 1400,
    beach_enabled: true,
    beach_width_multiplier: 1,
    water_direction_deg: 135,
    river_axis_deg: 0,
    relief: "hilly",
  },
  warnings: ["Block size clamped to 70 m."],
};

const PROMPT = "A hilly port where a river spills into a sheltered bay, like Lisbon but colder.";

function renderModal() {
  const onClose = vi.fn();
  const onCreated = vi.fn();
  render(<FoundCityModal onClose={onClose} onCreated={onCreated} />);
  fireEvent.click(screen.getByRole("tab", { name: /Describe it/ }));
  return { onClose, onCreated };
}

async function surveyPrompt(text = PROMPT) {
  fireEvent.change(screen.getByLabelText("Describe the land"), { target: { value: text } });
  fireEvent.keyDown(screen.getByLabelText("Describe the land"), { key: "Enter" });
  return screen.findByRole("heading", { name: "Here's your survey." });
}

function legend() {
  return screen.getByRole("list", { name: "Survey legend" });
}

describe("Describe it", () => {
  beforeEach(() => {
    createWorld.mockReset();
    createWorld.mockResolvedValue({ id: "world-7" });
    requestBrief.mockReset();
    requestBrief.mockResolvedValue(RESPONSE);
  });

  it("surveys the prompt and renders the legend from the response", async () => {
    renderModal();
    await surveyPrompt();

    expect(requestBrief).toHaveBeenCalledWith({ prompt: PROMPT });
    const rows = within(legend()).getAllByRole("button");
    expect(rows.map((r) => r.getAttribute("aria-label"))).toEqual([
      "LAND: Bay & Harbor. Change",
      "WATER: Bay opens to the south-east. Change",
      "RIVER: One river, winding in from the north. Change",
      "GROUND: Hilly west bank, flat east bank. Change",
      "STREETS: Hill Town, then Boomtown Grid. Change",
      "FEELS LIKE: Lisbon · Porto · Québec City. Change",
    ]);
    expect(screen.getByText(BRIEF.founding_story)).toBeInTheDocument();
    expect(screen.getByText(/“colder” noted, but I can't draw that yet/)).toBeInTheDocument();
    expect(screen.getByText("Block size clamped to 70 m.")).toBeInTheDocument();
  });

  it("shows Plains for an inland archetype", async () => {
    requestBrief.mockResolvedValueOnce({ ...RESPONSE, brief: { ...BRIEF, archetype: "inland" } });
    renderModal();
    await surveyPrompt();
    expect(within(legend()).getByText("Plains")).toBeInTheDocument();
  });

  it("asks for a few words before surveying", () => {
    renderModal();
    fireEvent.change(screen.getByLabelText("Describe the land"), { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: "Survey it" }));
    expect(requestBrief).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(/a few words/);
  });

  it("Shift+Enter does not survey", () => {
    renderModal();
    const box = screen.getByLabelText("Describe the land");
    fireEvent.change(box, { target: { value: PROMPT } });
    fireEvent.keyDown(box, { key: "Enter", shiftKey: true });
    expect(requestBrief).not.toHaveBeenCalled();
  });

  it("an example chip fills the prompt", () => {
    renderModal();
    const chips = within(screen.getByText("OR STEAL ONE").nextElementSibling as HTMLElement).getAllByRole("button");
    expect(chips).toHaveLength(4);
    fireEvent.click(chips[1]);
    expect(screen.getByLabelText("Describe the land")).toHaveValue(chips[1].textContent);
  });

  it("shows the surveyor while the request is in flight", async () => {
    let resolve!: (r: WorldBriefResponse) => void;
    requestBrief.mockReturnValueOnce(new Promise((r) => (resolve = r)));
    renderModal();
    fireEvent.change(screen.getByLabelText("Describe the land"), { target: { value: PROMPT } });
    fireEvent.click(screen.getByRole("button", { name: "Survey it" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Surveying the land");
    resolve(RESPONSE);
    await screen.findByRole("heading", { name: "Here's your survey." });
  });

  it("a legend option sends a refinement with the previous brief", async () => {
    renderModal();
    await surveyPrompt();
    const refined = { ...RESPONSE, brief: { ...BRIEF, water_side: "west" as const } };
    requestBrief.mockResolvedValueOnce(refined);

    fireEvent.click(within(legend()).getByRole("button", { name: /^WATER/ }));
    const menu = screen.getByRole("menu", { name: "Change water" });
    expect(within(menu).getByRole("menuitemradio", { name: "south-east" })).toHaveAttribute("aria-checked", "true");
    fireEvent.click(within(menu).getByRole("menuitemradio", { name: "west" }));

    await waitFor(() => expect(requestBrief).toHaveBeenCalledTimes(2));
    expect(requestBrief).toHaveBeenLastCalledWith({
      prompt: PROMPT,
      previous: BRIEF,
      refinement: "Change the water to the west",
    });
  });

  it("keeps focus on the legend row while a refinement redraws", async () => {
    renderModal();
    await surveyPrompt();
    let resolve!: (r: WorldBriefResponse) => void;
    requestBrief.mockReturnValueOnce(new Promise((r) => (resolve = r)));

    const row = within(legend()).getByRole("button", { name: /^RIVER/ });
    fireEvent.click(row);
    fireEvent.click(screen.getByRole("menuitemradio", { name: "braided" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Surveying the land");
    expect(within(legend()).getByRole("button", { name: /^RIVER/ })).toHaveFocus();
    expect(requestBrief.mock.calls[1][0].refinement).toBe("Make the river braided");
    resolve(RESPONSE);
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
  });

  it("the refine bar sends free text", async () => {
    renderModal();
    await surveyPrompt();
    const bar = screen.getByLabelText("Anything to change?");
    fireEvent.change(bar, { target: { value: "Put the river on the east side" } });
    fireEvent.keyDown(bar, { key: "Enter" });

    await waitFor(() => expect(requestBrief).toHaveBeenCalledTimes(2));
    expect(requestBrief.mock.calls[1][0]).toEqual({
      prompt: PROMPT,
      previous: BRIEF,
      refinement: "Put the river on the east side",
    });
  });

  it("on 503 shows the message and a Draw it fallback", async () => {
    requestBrief.mockRejectedValueOnce(
      new ApiClientError("The surveyor is off duty right now.", 503, { detail: "The surveyor is off duty right now." }),
    );
    renderModal();
    fireEvent.change(screen.getByLabelText("Describe the land"), { target: { value: PROMPT } });
    fireEvent.click(screen.getByRole("button", { name: "Survey it" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The surveyor is off duty right now.");
    fireEvent.click(within(alert).getByRole("button", { name: "Try Draw it instead" }));
    expect(screen.getByRole("tab", { name: /Draw it/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { name: "Where does your city begin?" })).toBeInTheDocument();
  });

  it("shows other errors without the fallback", async () => {
    requestBrief.mockRejectedValueOnce(new ApiClientError("Too many surveys, try again in a minute.", 429));
    renderModal();
    fireEvent.change(screen.getByLabelText("Describe the land"), { target: { value: PROMPT } });
    fireEvent.click(screen.getByRole("button", { name: "Survey it" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Too many surveys");
    expect(within(alert).queryByRole("button")).not.toBeInTheDocument();
  });

  it("founding sends the compiled settings unchanged", async () => {
    const { onCreated } = renderModal();
    await surveyPrompt();
    fireEvent.click(screen.getByRole("button", { name: "Next: name it" }));

    expect(screen.getByLabelText("City name")).toHaveValue("Porto Gelo");
    fireEvent.change(screen.getByLabelText(/SURVEY Nº/), { target: { value: "48213" } });
    fireEvent.click(screen.getByRole("button", { name: "Found Porto Gelo" }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("world-7"));
    expect(createWorld).toHaveBeenCalledWith({ name: "Porto Gelo", seed: 48213, settings: RESPONSE.settings });
    expect(createWorld.mock.calls[0][0].settings).toBe(RESPONSE.settings);
  });

  it("offers the brief's name suggestions as stamps", async () => {
    renderModal();
    await surveyPrompt();
    fireEvent.click(screen.getByRole("button", { name: "Next: name it" }));
    fireEvent.click(screen.getByRole("button", { name: "Saltmarsh" }));
    expect(screen.getByLabelText("City name")).toHaveValue("Saltmarsh");
  });

  it("Edit in Draw it prefills the manual flow", async () => {
    renderModal();
    await surveyPrompt();
    fireEvent.click(screen.getByRole("button", { name: "Edit in Draw it" }));

    expect(screen.getByRole("tab", { name: /Draw it/ })).toHaveAttribute("aria-selected", "true");
    // Opens on "How it grew" with the brief's story picked and its sliders applied.
    expect(screen.getByRole("heading", { name: "How did Porto Gelo grow?" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /^Hill Town/ })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("slider", { name: "Blocks" })).toHaveValue("70");

    fireEvent.click(screen.getByRole("button", { name: /The land/ }));
    expect(screen.getByRole("radio", { name: /^Bay & Harbor/ })).toHaveAttribute("aria-checked", "true");
  });

  it("switching tabs keeps each mode's progress", async () => {
    render(<FoundCityModal onClose={vi.fn()} onCreated={vi.fn()} />);
    fireEvent.click(screen.getByRole("radio", { name: /^Island/ }));
    fireEvent.click(screen.getByRole("button", { name: "Next: how it grew" }));

    fireEvent.click(screen.getByRole("tab", { name: /Describe it/ }));
    await surveyPrompt();

    fireEvent.click(screen.getByRole("tab", { name: /Draw it/ }));
    expect(screen.getByRole("heading", { name: /^How did .+ grow\?$/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: /Describe it/ }));
    expect(screen.getByRole("heading", { name: "Here's your survey." })).toBeInTheDocument();
  });
});
