export type Vec3 = [number, number, number];
export type Primitive = {
  name: string;
  kind: "box" | "sphere" | "cylinder" | "capsule";
  size: Vec3;
  position: Vec3;
  rotation: Vec3;
  mass: number;
  static: boolean;
  color: [number, number, number, number];
};
export type SceneConfig = {
  name: string;
  robot: {
    kind: "car" | "quadruped" | "aircraft" | "none";
    position: Vec3;
    rotation: Vec3;
    velocity: Vec3;
    angular_velocity: Vec3;
    mass: number;
    motor_strength: number;
  };
  physics: {
    gravity: Vec3;
    timestep: number;
    substeps: number;
    iterations: number;
    friction: number;
    density: number;
    viscosity: number;
    wind: Vec3;
  };
  terrain: {
    kind: "flat" | "rough" | "stairs";
    size: [number, number];
    roughness: number;
    seed: number;
  };
  objects: Primitive[];
  max_episode_steps: number;
};
export type Geom = {
  id: number;
  name: string;
  type: string;
  position: Vec3;
  quaternion: [number, number, number, number];
  size: Vec3;
  rgba: [number, number, number, number];
};
export type Snapshot = {
  time: number;
  step: number;
  reward: number;
  terminated: boolean;
  truncated: boolean;
  observation: number[];
  info: {
    speed: number;
    height: number;
    distance: number;
    contacts: number;
    energy: number;
  };
  geoms: Geom[];
};
export type World = {
  id: string;
  scene: SceneConfig;
  description: {
    action_size: number;
    observation_size: number;
    action_names: string[];
    dt: number;
    backend: string;
  };
  state: Snapshot;
};
export type Template = {
  id: string;
  name: string;
  description: string;
  category: string;
  scene: SceneConfig;
};
export type Point = { time: number; speed: number; reward: number };
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch("/api/v1" + path, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    let message = await response.text();
    try {
      const parsed = JSON.parse(message);
      message =
        typeof parsed.detail === "string"
          ? parsed.detail
          : JSON.stringify(parsed.detail ?? parsed);
    } catch {}
    throw new Error(message || `${response.status} ${response.statusText}`);
  }
  return response.json();
}
