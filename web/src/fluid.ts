export type FluidObstacle = {
  name: string;
  shape: "circle" | "box" | "ellipse" | "naca0012" | "naca2412" | "polygon";
  x: number;
  y: number;
  width: number;
  height: number;
  angle: number;
  points?: [number, number][];
};

export type Config = {
  resolution: number;
  timestep: number;
  viscosity: number;
  diffusion: number;
  inflow: number;
  dye_source: number;
  source_x: number;
  source_y: number;
  source_radius: number;
  source_mode: "jet" | "rake";
  dissipation: number;
  obstacle: boolean;
  obstacle_x: number;
  obstacle_y: number;
  obstacle_radius: number;
  obstacles: FluidObstacle[];
  iterations: number;
};

export type FlowState = {
  time: number;
  resolution: number;
  density: number[][];
  u: number[][];
  v: number[][];
  speed: number[][];
  vorticity: number[][];
  pressure_correction: number[][];
  obstacle: boolean[][];
  metrics: {
    divergence_rms: number;
    kinetic_energy: number;
    dye_mass: number;
    max_speed: number;
    cfl: number;
  };
};

export type FlowView = "smoke" | "speed" | "pressure" | "vorticity";
export type Probe = { x: number; y: number };

export const fieldLabels: Record<FlowView, { label: string; unit: string }> = {
  smoke: { label: "Dye concentration", unit: "a.u." },
  speed: { label: "Velocity magnitude", unit: "m/s" },
  pressure: { label: "Pressure correction", unit: "m²/s²" },
  vorticity: { label: "Vorticity", unit: "1/s" },
};

export function fieldValues(state: FlowState, view: FlowView): number[][] {
  return view === "smoke" ? state.density
    : view === "speed" ? state.speed
    : view === "pressure" ? state.pressure_correction
    : state.vorticity;
}

export function fieldRange(state: FlowState | null, view: FlowView): [number, number] {
  if (!state) return [0, 1];
  let maximum = 0;
  const values = fieldValues(state, view);
  for (let y = 0; y < values.length; y++) {
    for (let x = 0; x < values[y].length; x++) {
      if (!state.obstacle[y][x] && Number.isFinite(values[y][x])) {
        maximum = Math.max(maximum, Math.abs(values[y][x]));
      }
    }
  }
  // Symmetric signed fields keep the zero color stable as the solution changes.
  return view === "pressure" || view === "vorticity"
    ? [-maximum, maximum] : [0, maximum];
}

const airfoil: FluidObstacle = {
  name: "Airfoil 1", shape: "naca0012", x: 0.48, y: 0.5,
  width: 0.45, height: 0.054, angle: 8,
};

export const initialConfig: Config = {
  resolution: 96,
  timestep: 0.02,
  viscosity: 0.0001,
  diffusion: 0.00001,
  inflow: 0.6,
  dye_source: 4,
  source_x: 0.06,
  source_y: 0.5,
  source_radius: 0.015,
  source_mode: "rake",
  dissipation: 0.03,
  obstacle: true,
  obstacle_x: 0.45,
  obstacle_y: 0.5,
  obstacle_radius: 0.1,
  obstacles: [airfoil],
  iterations: 160,
};

export const presets: {
  id: string; name: string; description: string; obstacles: FluidObstacle[];
}[] = [
  {
    id: "cylinder", name: "Cylinder flow", description: "Channel flow around a circular obstacle",
    obstacles: [{ name: "Cylinder 1", shape: "circle", x: 0.4, y: 0.5, width: 0.2, height: 0.2, angle: 0 }],
  },
  { id: "airfoil", name: "NACA airfoil", description: "Channel flow around a NACA 0012 profile", obstacles: [airfoil] },
  {
    id: "bluff", name: "Bluff body", description: "Channel flow around a rectangular obstacle",
    obstacles: [{ name: "Block 1", shape: "box", x: 0.42, y: 0.5, width: 0.16, height: 0.24, angle: 0 }],
  },
  {
    id: "twin", name: "Twin obstacles", description: "Channel flow around two circular obstacles",
    obstacles: [
      { name: "Cylinder 1", shape: "circle", x: 0.38, y: 0.36, width: 0.17, height: 0.17, angle: 0 },
      { name: "Cylinder 2", shape: "circle", x: 0.55, y: 0.63, width: 0.17, height: 0.17, angle: 0 },
    ],
  },
];
