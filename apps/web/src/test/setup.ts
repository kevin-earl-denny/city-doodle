import "@testing-library/jest-dom";
import { vi } from "vitest";

// Mock PixiJS since it requires WebGL which isn't available in jsdom
vi.mock("pixi.js", () => ({
  Application: vi.fn().mockImplementation(() => ({
    init: vi.fn().mockResolvedValue(undefined),
    canvas: document.createElement("canvas"),
    stage: {
      addChild: vi.fn(),
    },
    renderer: {
      events: {},
    },
    destroy: vi.fn(),
  })),
  Container: vi.fn().mockImplementation(() => {
    const container = {
      addChild: vi.fn(),
      removeChild: vi.fn(),
      removeChildren: vi.fn(),
      destroy: vi.fn(),
      visible: true,
      label: "",
      children: [] as unknown[],
      destroyed: false,
    };
    // Make addChild actually add to children array for tests that check children.length
    container.addChild.mockImplementation((...args: unknown[]) => {
      container.children.push(...args);
      return args[0];
    });
    container.removeChild.mockImplementation((child: unknown) => {
      const index = container.children.indexOf(child);
      if (index > -1) {
        container.children.splice(index, 1);
      }
      return child;
    });
    // Like pixi: removes every child and returns them (layers reuse containers
    // via `removeChildren().forEach((c) => c.destroy())`, CITY-506).
    container.removeChildren.mockImplementation(() => container.children.splice(0));
    return container;
  }),
  Graphics: vi.fn().mockImplementation(() => ({
    setStrokeStyle: vi.fn().mockReturnThis(),
    moveTo: vi.fn().mockReturnThis(),
    lineTo: vi.fn().mockReturnThis(),
    stroke: vi.fn().mockReturnThis(),
    circle: vi.fn().mockReturnThis(),
    fill: vi.fn().mockReturnThis(),
    rect: vi.fn().mockReturnThis(),
    clear: vi.fn().mockReturnThis(),
    closePath: vi.fn().mockReturnThis(),
    destroy: vi.fn(),
    visible: true,
    label: "",
  })),
  // Like pixi v8: `new Text({ text, style })`, with a mutable `style` object
  // (layers update `text.style.fill` in place when reusing Text objects).
  Text: vi.fn().mockImplementation((options?: { text?: string; style?: object }) => ({
    text: options?.text ?? "",
    style: options?.style ?? {},
    anchor: { set: vi.fn() },
    position: { set: vi.fn() },
    rotation: 0,
    alpha: 1,
    visible: true,
    label: "",
    getBounds: vi.fn().mockReturnValue({ width: 50, height: 20 }),
    destroy: vi.fn(),
  })),
  TextStyle: vi.fn().mockImplementation(() => ({})),
}));

vi.mock("pixi-viewport", () => ({
  Viewport: vi.fn().mockImplementation(() => ({
    addChild: vi.fn(),
    drag: vi.fn().mockReturnThis(),
    pinch: vi.fn().mockReturnThis(),
    wheel: vi.fn().mockReturnThis(),
    decelerate: vi.fn().mockReturnThis(),
    clampZoom: vi.fn().mockReturnThis(),
    moveCenter: vi.fn(),
    resize: vi.fn(),
  })),
}));
