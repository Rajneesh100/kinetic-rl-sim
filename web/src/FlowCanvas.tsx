import { useEffect, useRef, useState } from "react";
import type { PointerEvent } from "react";
import { fieldRange, fieldValues } from "./fluid";
import type { FluidObstacle, FlowState, FlowView, Probe } from "./fluid";

type Props = {
  state: FlowState | null;
  view: FlowView;
  vectors: boolean;
  streamlines: boolean;
  obstacles: FluidObstacle[];
  selected: string | null;
  probe: Probe | null;
  onProbe: (point: Probe) => void;
  onSelect: (name: string) => void;
  onMove: (name: string, x: number, y: number) => void;
};
type Point = [number, number];
const SIZE = 1024;

// Draft outlines are editing guides. The filled mask always comes from the solver.
function outline(obstacle: FluidObstacle): Point[] {
  let points: Point[] = [];
  if (obstacle.shape === "circle" || obstacle.shape === "ellipse") {
    for (let i = 0; i < 80; i++) {
      const a = i * Math.PI / 40;
      points.push([
        Math.cos(a) * obstacle.width / 2,
        Math.sin(a) * (obstacle.shape === "circle" ? obstacle.width : obstacle.height) / 2,
      ]);
    }
  } else if (obstacle.shape.startsWith("naca")) {
    const upper: Point[] = [], lower: Point[] = [];
    const m = obstacle.shape === "naca2412" ? 0.02 : 0;
    for (let i = 0; i <= 100; i++) {
      const x = (1 - Math.cos(i * Math.PI / 100)) / 2;
      const t = 0.6 * (0.2969 * Math.sqrt(x) - 0.126 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4);
      const p = 0.4;
      const camber = x < p ? m / p ** 2 * (2 * p * x - x ** 2)
        : m / (1 - p) ** 2 * (1 - 2 * p + 2 * p * x - x ** 2);
      const slope = x < p ? 2 * m / p ** 2 * (p - x)
        : 2 * m / (1 - p) ** 2 * (p - x);
      const theta = Math.atan(slope);
      upper.push([(x - t * Math.sin(theta) - 0.5) * obstacle.width, (camber + t * Math.cos(theta)) * obstacle.width]);
      lower.push([(x + t * Math.sin(theta) - 0.5) * obstacle.width, (camber - t * Math.cos(theta)) * obstacle.width]);
    }
    points = [...upper, ...lower.reverse()];
  } else {
    const vertices: Point[] = obstacle.shape === "polygon"
      ? obstacle.points ?? []
      : [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]];
    points = vertices.map(([x, y]) => [x * obstacle.width, y * obstacle.height]);
  }
  const angle = obstacle.angle * Math.PI / 180;
  return points.map(([x, y]) => [
    obstacle.x + x * Math.cos(angle) - y * Math.sin(angle),
    obstacle.y + x * Math.sin(angle) + y * Math.cos(angle),
  ]);
}

function inside(point: Probe, polygon: Point[]): boolean {
  let hit = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [xi, yi] = polygon[i], [xj, yj] = polygon[j];
    if ((yi > point.y) !== (yj > point.y) && point.x < (xj - xi) * (point.y - yi) / (yj - yi) + xi) hit = !hit;
  }
  return hit;
}

function sample(field: number[][], x: number, y: number): number {
  const n = field.length;
  const gx = Math.max(0, Math.min(n - 1, x * n - 0.5));
  const gy = Math.max(0, Math.min(n - 1, y * n - 0.5));
  const i = Math.floor(gx), j = Math.floor(gy), a = gx - i, b = gy - j;
  return (1 - b) * ((1 - a) * field[j][i] + a * field[j][Math.min(i + 1, n - 1)])
    + b * ((1 - a) * field[Math.min(j + 1, n - 1)][i] + a * field[Math.min(j + 1, n - 1)][Math.min(i + 1, n - 1)]);
}

const ramp = [[12, 24, 38], [24, 81, 106], [27, 146, 154], [148, 209, 159], [254, 214, 128]];
function color(value: number, maximum: number, view: FlowView): number[] {
  const normalized = Math.max(-1, Math.min(1, value / (maximum || 1)));
  if (view === "smoke") {
    const t = Math.pow(Math.max(0, normalized), 0.6);
    return [12 + t * 232, 21 + t * 182, 32 + t * 130];
  }
  if (view === "pressure" || view === "vorticity") {
    const t = Math.sqrt(Math.abs(normalized));
    const end = normalized < 0 ? [66, 182, 221] : [246, 125, 82];
    return end.map((v, i) => [21, 29, 42][i] + (v - [21, 29, 42][i]) * t);
  }
  const t = Math.max(0, normalized) * (ramp.length - 1);
  const index = Math.min(ramp.length - 2, Math.floor(t));
  return ramp[index].map((v, i) => v + (ramp[index + 1][i] - v) * (t - index));
}

export default function FlowCanvas(props: Props) {
  const { state, view, vectors, streamlines, obstacles, selected, probe } = props;
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drag = useRef<{ name: string; start: Probe; origin: Probe; limits: number[]; moved: boolean } | null>(null);
  const [preview, setPreview] = useState<{ name: string; x: number; y: number } | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !state) return;
    const ctx = canvas.getContext("2d")!;
    canvas.width = SIZE;
    canvas.height = SIZE;
    const n = state.resolution;
    const off = document.createElement("canvas");
    off.width = n; off.height = n;
    const buffer = off.getContext("2d")!;
    const pixels = buffer.createImageData(n, n);
    const values = fieldValues(state, view);
    const [, maximum] = fieldRange(state, view);
    for (let y = 0; y < n; y++) {
      for (let x = 0; x < n; x++) {
        const i = ((n - y - 1) * n + x) * 4;
        const rgb = state.obstacle[y][x] ? [30, 37, 44] : color(values[y][x], maximum, view);
        pixels.data.set([...rgb.map(Math.round), 255], i);
      }
    }
    buffer.putImageData(pixels, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(off, 0, 0, SIZE, SIZE);
    ctx.strokeStyle = "rgba(159,191,207,.07)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i <= SIZE; i += SIZE / 10) {
      ctx.moveTo(i, 0); ctx.lineTo(i, SIZE);
      ctx.moveTo(0, i); ctx.lineTo(SIZE, i);
    }
    ctx.stroke();
    const fluid = (x: number, y: number) => x > 0 && x < 1 && y > 0 && y < 1
      && !state.obstacle[Math.floor(y * n)][Math.floor(x * n)];
    if (streamlines) {
      // Instantaneous streamlines from the current velocity field, never synthetic wakes.
      ctx.lineWidth = 1.35;
      ctx.strokeStyle = view === "smoke" ? "rgba(151,205,225,.48)" : "rgba(233,242,241,.42)";
      for (let seed = 0; seed < 31; seed++) {
        let x = 0.008, y = 0.035 + seed * 0.031;
        const ds = Math.min(0.004, 0.4 / n);
        ctx.beginPath(); ctx.moveTo(x * SIZE, (1 - y) * SIZE);
        for (let step = 0; step < 750; step++) {
          const u = sample(state.u, x, y), v = sample(state.v, x, y);
          const speed = Math.hypot(u, v);
          if (speed < 1e-7) break;
          const mx = x + ds * u / speed / 2, my = y + ds * v / speed / 2;
          if (!fluid(mx, my)) break;
          const um = sample(state.u, mx, my), vm = sample(state.v, mx, my);
          const midSpeed = Math.hypot(um, vm);
          if (midSpeed < 1e-7) break;
          x += ds * um / midSpeed; y += ds * vm / midSpeed;
          if (!fluid(x, y)) break;
          ctx.lineTo(x * SIZE, (1 - y) * SIZE);
        }
        ctx.stroke();
      }
    }
    if (vectors) {
      const stride = Math.max(3, Math.round(n / 18));
      for (let y = Math.floor(stride / 2); y < n; y += stride) {
        for (let x = Math.floor(stride / 2); x < n; x += stride) {
          if (state.obstacle[y][x]) continue;
          const u = state.u[y][x], v = state.v[y][x], speed = Math.hypot(u, v);
          if (speed < 1e-7) continue;
          const sx = (x + 0.5) / n * SIZE, sy = (1 - (y + 0.5) / n) * SIZE;
          const length = Math.min(22, 22 * speed / (state.metrics.max_speed || 1));
          const ex = sx + u / speed * length, ey = sy - v / speed * length;
          const a = Math.atan2(-v, u);
          ctx.strokeStyle = "rgba(213,232,235,.58)"; ctx.lineWidth = 1.5;
          ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(ex, ey);
          ctx.moveTo(ex - 4 * Math.cos(a - 0.5), ey - 4 * Math.sin(a - 0.5));
          ctx.lineTo(ex, ey); ctx.lineTo(ex - 4 * Math.cos(a + 0.5), ey - 4 * Math.sin(a + 0.5));
          ctx.stroke();
        }
      }
    }
    for (const item of obstacles) {
      const obstacle = preview?.name === item.name ? { ...item, ...preview } : item;
      const points = outline(obstacle);
      if (!points.length) continue;
      ctx.beginPath();
      points.forEach(([x, y], i) => i ? ctx.lineTo(x * SIZE, (1 - y) * SIZE) : ctx.moveTo(x * SIZE, (1 - y) * SIZE));
      ctx.closePath();
      ctx.strokeStyle = selected === item.name ? "#ff9e6b" : "#b3c9ca";
      ctx.lineWidth = selected === item.name ? 3 : 1.5;
      ctx.setLineDash(preview?.name === item.name ? [7, 4] : []);
      ctx.stroke(); ctx.setLineDash([]);
      if (selected === item.name) {
        const top = Math.max(...points.map((p) => p[1]));
        ctx.font = "18px 'IBM Plex Mono', monospace";
        ctx.textAlign = "center"; ctx.fillStyle = "#ffd7b8";
        ctx.fillText(item.name, obstacle.x * SIZE, (1 - top) * SIZE - 14);
      }
    }
    if (probe) {
      const x = probe.x * SIZE, y = (1 - probe.y) * SIZE;
      ctx.strokeStyle = "#f3f5d7"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(x, y, 8, 0, 2 * Math.PI);
      ctx.moveTo(x - 14, y); ctx.lineTo(x + 14, y);
      ctx.moveTo(x, y - 14); ctx.lineTo(x, y + 14); ctx.stroke();
    }
    ctx.font = "15px 'IBM Plex Mono', monospace";
    ctx.fillStyle = "#90a5ae"; ctx.textAlign = "left";
    ctx.fillText("INFLOW →", 22, SIZE - 24);
    ctx.textAlign = "right"; ctx.fillText("OUTFLOW →", SIZE - 22, SIZE - 24);
  }, [state, view, vectors, streamlines, obstacles, selected, probe, preview]);

  const coordinates = (event: PointerEvent<HTMLCanvasElement>): Probe | null => {
    const rect = event.currentTarget.getBoundingClientRect();
    const size = Math.min(rect.width, rect.height);
    const x = (event.clientX - rect.left - (rect.width - size) / 2) / size;
    const y = 1 - (event.clientY - rect.top - (rect.height - size) / 2) / size;
    return x >= 0 && x <= 1 && y >= 0 && y <= 1 ? { x, y } : null;
  };
  return (
    <canvas
      ref={canvasRef}
      className="flow-canvas"
      aria-label="Interactive wind tunnel: click fluid to probe; drag obstacles to edit"
      style={{ touchAction: "none", cursor: preview ? "grabbing" : "crosshair" }}
      onPointerDown={(event) => {
        if (event.button !== 0) return;
        const p = coordinates(event);
        if (!p) return;
        const item = [...obstacles].reverse().find((o) => inside(p, outline(o)));
        if (item) {
          props.onSelect(item.name);
          const points = outline(item);
          const xs = points.map(([x]) => x), ys = points.map(([, y]) => y);
          drag.current = { name: item.name, start: p, origin: { x: item.x, y: item.y }, moved: false,
            limits: [0.01 - Math.min(...xs), 0.99 - Math.max(...xs), 0.01 - Math.min(...ys), 0.99 - Math.max(...ys)] };
          event.currentTarget.setPointerCapture(event.pointerId);
        } else props.onProbe(p);
      }}
      onPointerMove={(event) => {
        const p = coordinates(event), d = drag.current;
        if (!p || !d) return;
        const dx = Math.max(d.limits[0], Math.min(d.limits[1], p.x - d.start.x));
        const dy = Math.max(d.limits[2], Math.min(d.limits[3], p.y - d.start.y));
        if (Math.hypot(dx, dy) < 0.002 && !d.moved) return;
        d.moved = true;
        setPreview({ name: d.name, x: d.origin.x + dx, y: d.origin.y + dy });
      }}
      onPointerUp={(event) => {
        if (drag.current?.moved && preview) {
          props.onMove(preview.name, Number(preview.x.toFixed(4)), Number(preview.y.toFixed(4)));
        }
        drag.current = null; setPreview(null);
        if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
      }}
      onPointerCancel={() => { drag.current = null; setPreview(null); }}
    />
  );
}
