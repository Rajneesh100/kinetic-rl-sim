import { useEffect, useRef, useState } from "react";
import {
  Activity, ArrowRight, Check, ChevronRight, Crosshair, Download, Info,
  LoaderCircle, Pause, Play, Plus, RotateCcw, SlidersHorizontal, StepForward,
  Trash2, Upload, Wind, X,
} from "lucide-react";
import { api } from "./types";
import FlowCanvas from "./FlowCanvas";
import {
  fieldLabels, fieldRange, initialConfig, presets,
  type Config, type FlowState, type FlowView, type FluidObstacle, type Probe,
} from "./fluid";
import "./flow-lab.css";

const format = (value: number | undefined, digits = 3) => value === undefined
  ? "—" : Math.abs(value) < 0.001 && value !== 0 ? value.toExponential(2) : value.toFixed(digits);
type NumericConfig = { [K in keyof Config]: Config[K] extends number ? K : never }[keyof Config];

function PresetGlyph({ id }: { id: string }) {
  return <svg viewBox="0 0 76 42" aria-hidden="true" className="tunnel-preset-glyph">
    <path d="M1 9H73 M1 21H73 M1 33H73" className="glyph-lines" />
    {id === "airfoil" ? <path d="M17 24C15 16 35 15 62 16C42 21 24 27 17 24Z" />
      : id === "bluff" ? <rect x="29" y="10" width="16" height="23" rx="1" />
      : id === "twin" ? <><circle cx="29" cy="14" r="7" /><circle cx="47" cy="28" r="7" /></>
      : <circle cx="37" cy="21" r="11" />}
  </svg>;
}

export default function FlowLab({ notify }: { notify: (s: string) => void }) {
  const [id, setId] = useState("");
  const [state, setState] = useState<FlowState | null>(null);
  const [config, setConfig] = useState<Config>(() => structuredClone(initialConfig));
  const [applied, setApplied] = useState<Config>(() => structuredClone(initialConfig));
  const [selected, setSelected] = useState<string | null>(initialConfig.obstacles[0].name);
  const [playing, setPlaying] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [view, setView] = useState<FlowView>("smoke");
  const [vectors, setVectors] = useState(false);
  const [streamlines, setStreamlines] = useState(true);
  const [probe, setProbe] = useState<Probe | null>(null);
  const [tab, setTab] = useState<"geometry" | "fluid" | "solver">("geometry");
  const ownedSessions = useRef(new Set<string>());
  const alive = useRef(true);
  const busyRef = useRef(false);
  const playingRef = useRef(false);
  const idRef = useRef("");
  const generation = useRef(0);
  const importInput = useRef<HTMLInputElement>(null);
  const dirty = JSON.stringify(config) !== JSON.stringify(applied);
  const selectedObstacle = config.obstacles.find((obstacle) => obstacle.name === selected);
  const selectedPreset = presets.find((preset) => JSON.stringify(preset.obstacles) === JSON.stringify(config.obstacles));
  const range = fieldRange(state, view);

  const stop = () => { playingRef.current = false; setPlaying(false); };
  const release = async (session: string) => {
    await api(`/fluids/${session}`, "DELETE").catch(() => {});
    ownedSessions.current.delete(session);
  };
  const create = async (draft: Config) => {
    const next = structuredClone(draft);
    const request = ++generation.current;
    stop(); setBusy(true); setError("");
    let createdId: string | null = null;
    try {
      while (busyRef.current) await new Promise((resolve) => setTimeout(resolve, 20));
      if (!alive.current || request !== generation.current) return;
      const result = await api<{ id: string; state: FlowState }>("/fluids", "POST", next);
      createdId = result.id;
      ownedSessions.current.add(result.id);
      if (!alive.current || request !== generation.current) { await release(result.id); return; }
      let preview = result.state;
      for (let batch = 0; batch < 2; batch++) {
        preview = await api<FlowState>(`/fluids/${result.id}/step`, "POST", { steps: 20 });
        if (!alive.current || request !== generation.current) { await release(result.id); return; }
      }
      if (!alive.current || request !== generation.current) { await release(result.id); return; }
      const previous = idRef.current;
      idRef.current = result.id;
      setId(result.id); setState(preview); setApplied(next);
      if (previous) await release(previous);
    } catch (e) {
      if (createdId) await release(createdId);
      if (alive.current && request === generation.current) setError((e as Error).message);
    } finally {
      if (alive.current && request === generation.current) setBusy(false);
    }
  };

  useEffect(() => {
    alive.current = true;
    void create(initialConfig);
    const cleanup = () => {
      for (const session of ownedSessions.current) {
        void fetch(`/api/v1/fluids/${session}`, { method: "DELETE", keepalive: true }).catch(() => {});
      }
      ownedSessions.current.clear();
    };
    window.addEventListener("pagehide", cleanup);
    return () => {
      alive.current = false; generation.current++; playingRef.current = false;
      window.removeEventListener("pagehide", cleanup); cleanup();
    };
  }, []);

  useEffect(() => {
    if (!playing || !id) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      if (stopped || !playingRef.current) return;
      let ownsStep = false;
      try {
        while (busyRef.current) await new Promise((resolve) => setTimeout(resolve, 20));
        if (stopped || !playingRef.current || !alive.current) return;
        busyRef.current = true;
        ownsStep = true;
        const next = await api<FlowState>(`/fluids/${id}/step`, "POST", { steps: 2 });
        if (!stopped && playingRef.current && alive.current) {
          setState(next); timer = setTimeout(tick, 25);
        }
      } catch (e) {
        if (!stopped && alive.current) { setError((e as Error).message); stop(); }
      } finally { if (ownsStep) busyRef.current = false; }
    };
    void tick();
    return () => { stopped = true; clearTimeout(timer); };
  }, [playing, id]);

  const advance = async (reset: boolean) => {
    stop(); setBusy(true); setError("");
    try {
      while (busyRef.current) await new Promise((resolve) => setTimeout(resolve, 20));
      if (!alive.current) return;
      busyRef.current = true;
      const result = await api<FlowState>(`/fluids/${id}/${reset ? "reset" : "step"}`, "POST", reset ? undefined : { steps: 1 });
      if (alive.current) setState(result);
      if (reset && alive.current) notify("Flow field reset");
    } catch (e) { if (alive.current) setError((e as Error).message); }
    finally { busyRef.current = false; if (alive.current) setBusy(false); }
  };

  const updateObstacle = (name: string, changes: Partial<FluidObstacle>) => {
    setConfig((current) => ({ ...current, obstacles: current.obstacles.map((obstacle) => obstacle.name === name ? { ...obstacle, ...changes } : obstacle) }));
  };
  const addObstacle = () => {
    let index = 1;
    while (config.obstacles.some((obstacle) => obstacle.name === `Body ${index}`)) index++;
    const obstacle: FluidObstacle = { name: `Body ${index}`, shape: "circle", x: 0.7, y: 0.7, width: 0.14, height: 0.14, angle: 0 };
    setConfig((current) => ({ ...current, obstacles: [...current.obstacles, obstacle] }));
    setSelected(obstacle.name);
  };
  const number = (label: string, key: NumericConfig, unit: string, step: number, min: number, max: number) => (
    <label className="field"><span>{label}</span><div className="number-input">
      <input type="number" aria-label={label} value={config[key]} min={min} max={max} step={step}
        onChange={(event) => setConfig((current) => ({ ...current, [key]: Number(event.target.value) }))} />
      <em>{unit}</em>
    </div></label>
  );
  const obstacleNumber = (label: string, key: "x" | "y" | "width" | "height" | "angle", unit: string, min: number, max: number, step = 0.01) => (
    <label className="field"><span>{label}</span><div className="number-input">
      <input type="number" aria-label={label} value={selectedObstacle![key]} min={min} max={max} step={step}
        onChange={(event) => updateObstacle(selectedObstacle!.name, { [key]: Number(event.target.value) })} />
      <em>{unit}</em>
    </div></label>
  );

  const sample = state && probe ? (() => {
    const x = Math.min(state.resolution - 1, Math.max(0, Math.floor(probe.x * state.resolution)));
    const y = Math.min(state.resolution - 1, Math.max(0, Math.floor(probe.y * state.resolution)));
    return { x, y, solid: state.obstacle[y][x], speed: state.speed[y][x], u: state.u[y][x], v: state.v[y][x],
      dye: state.density[y][x], pressure: state.pressure_correction[y][x], vorticity: state.vorticity[y][x] };
  })() : null;

  const exportExperiment = () => {
    const payload = {
      format: "kinetic-flow-experiment", version: 1, config: applied,
      diagnostics: state ? { simulation_time: state.time, metrics: state.metrics, probe: sample } : null,
      view: { field: view, vectors, streamlines },
      description: "Initial configuration and measured diagnostics, not a simulation checkpoint. Pressure correction is a projection diagnostic, not calibrated aerodynamic pressure. No lift or drag is calculated.",
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = "kinetic-flow-experiment.json"; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    notify("Applied experiment and diagnostics exported");
  };
  const importExperiment = async (file: File) => {
    try {
      const payload = JSON.parse(await file.text());
      const candidate = payload?.config ?? payload;
      if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) throw new Error("Expected a fluid configuration object or an exported experiment.");
      const next = {
        ...structuredClone(initialConfig), resolution: 64, dye_source: 2,
        source_x: 0.12, source_radius: 0.06, source_mode: "jet", iterations: 60,
        ...candidate,
      } as Config;
      const numericKeys = Object.keys(initialConfig).filter((key) => typeof initialConfig[key as keyof Config] === "number") as NumericConfig[];
      if (numericKeys.some((key) => typeof next[key] !== "number" || !Number.isFinite(next[key]))) throw new Error("Fluid settings must contain finite numeric values.");
      if (!["jet", "rake"].includes(next.source_mode) || typeof next.obstacle !== "boolean") throw new Error("Source mode must be jet or rake and obstacle must be a boolean.");
      if (candidate.obstacles == null) {
        next.obstacles = next.obstacle ? [{ name: "Cylinder 1", shape: "circle", x: next.obstacle_x,
          y: next.obstacle_y, width: next.obstacle_radius * 2, height: next.obstacle_radius * 2, angle: 0 }] : [];
      }
      if (!Array.isArray(next.obstacles) || next.obstacles.length > 16) throw new Error("Obstacles must be an array containing at most 16 bodies.");
      next.obstacles = next.obstacles.map((obstacle) => {
        if (!obstacle || typeof obstacle !== "object" || Array.isArray(obstacle)) throw new Error("Every obstacle must be an object.");
        return Object.assign({ shape: "circle" as const, x: 0.45, y: 0.5, width: 0.2, height: 0.2, angle: 0 }, obstacle);
      });
      const names = new Set<string>();
      for (const obstacle of next.obstacles) {
        if (!obstacle || typeof obstacle.name !== "string" || !obstacle.name.trim() || names.has(obstacle.name)) throw new Error("Each obstacle requires a unique non-empty name.");
        names.add(obstacle.name);
        if (!["circle", "box", "ellipse", "naca0012", "naca2412", "polygon"].includes(obstacle.shape)) throw new Error(`Unsupported obstacle shape: ${obstacle.shape}`);
        if ([obstacle.x, obstacle.y, obstacle.width, obstacle.height, obstacle.angle].some((value) => typeof value !== "number" || !Number.isFinite(value))) throw new Error(`Obstacle ${obstacle.name} requires numeric x, y, width, height and angle.`);
        if (obstacle.shape === "polygon" && (!Array.isArray(obstacle.points) || obstacle.points.length < 3 || obstacle.points.some((point) => !Array.isArray(point) || point.length !== 2 || point.some((value) => typeof value !== "number" || !Number.isFinite(value) || Math.abs(value) > 0.5)))) throw new Error(`Polygon ${obstacle.name} requires at least 3 local [x,y] points between -0.5 and 0.5.`);
      }
      setConfig(next); setSelected(next.obstacles[0]?.name ?? null); setError(""); setTab("geometry");
      notify("Experiment imported as a draft. Apply & restart to validate and run it.");
    } catch (e) { setError(`Import failed: ${(e as Error).message}`); }
  };

  return <div className="flow-page tunnel-page">
    <header className="flow-title">
      <div><span className="eyebrow orange">FLUID DYNAMICS / 2D</span><h1>2D Wind Tunnel</h1>
        <p>Obstacle configuration, flow-field visualization, and local measurements.</p></div>
      <div className="tunnel-header-actions"><span className="flow-method"><Wind size={16} />2D INCOMPRESSIBLE</span>
        <button className="button tunnel-import-button" onClick={() => importInput.current?.click()} disabled={busy} title="Import experiment JSON"><Upload size={14} /><span>Import</span></button>
        <input ref={importInput} type="file" accept=".json,application/json" hidden onChange={(event) => { const file = event.target.files?.[0]; if (file) void importExperiment(file); event.target.value = ""; }} />
        <button className="button" onClick={exportExperiment} disabled={!state || busy}><Download size={14} />Export experiment</button></div>
    </header>

    <div className="tunnel-presets" aria-label="Experiment presets">
      {presets.map((preset, index) => <button key={preset.id} className={`tunnel-preset ${selectedPreset?.id === preset.id ? "active" : ""}`}
        disabled={busy} onClick={() => { setConfig(structuredClone({ ...initialConfig, obstacles: preset.obstacles })); setSelected(preset.obstacles[0].name); setTab("geometry"); }}>
        <PresetGlyph id={preset.id} /><span><small>0{index + 1} / PRESET</small><strong>{preset.name}</strong><em>{preset.description}</em></span><ChevronRight size={14} />
      </button>)}
    </div>

    {error && <div className="flow-error" role="alert">{error}</div>}
    <div className="flow-workspace">
      <section className="flow-display" aria-label="Wind tunnel">
        <div className="tunnel-toolbar"><div className="tunnel-field-tabs" aria-label="Displayed field">
          {([ ["smoke", "Smoke"], ["speed", "Speed"], ["pressure", "Pressure correction"], ["vorticity", "Vorticity"] ] as [FlowView, string][]).map(([key, label]) =>
            <button key={key} aria-pressed={view === key} className={view === key ? "active" : ""} onClick={() => setView(key)}>{label}</button>)}
        </div><div className="tunnel-overlays">
          <label><input type="checkbox" checked={streamlines} onChange={(event) => setStreamlines(event.target.checked)} />Streamlines</label>
          <label><input type="checkbox" checked={vectors} onChange={(event) => setVectors(event.target.checked)} />Vectors</label>
        </div></div>
        <div className="flow-transport tunnel-top-transport"><div>
          <button className="icon-button" disabled={!id || busy} aria-label="Reset flow" title="Reset current experiment" onClick={() => void advance(true)}><RotateCcw size={16} /></button>
          <button className="play-button" disabled={!id || busy} onClick={() => { playingRef.current = !playing; setPlaying(!playing); }}>
            {playing ? <Pause size={14} /> : <Play size={14} fill="currentColor" />}{playing ? "Pause flow" : "Run flow"}</button>
          <button className="icon-button" disabled={!id || busy || playing} aria-label="Advance one step" title="Advance one simulation step" onClick={() => void advance(false)}><StepForward size={16} /></button>
        </div><span><Activity size={13} />MAC solver · native CPU</span></div>
        <div className="flow-canvas-wrap">
          <FlowCanvas state={state} view={view} vectors={vectors} streamlines={streamlines} obstacles={config.obstacles}
            selected={selected} probe={probe} onProbe={setProbe} onSelect={(name) => { setSelected(name); setTab("geometry"); }}
            onMove={(name, x, y) => updateObstacle(name, { x, y })} />
          <div className="flow-overlay-top"><span><span className={playing ? "status-dot" : "idle-dot"} />{playing ? "SOLVING" : "PAUSED"}</span>
            <span>{state?.resolution ?? applied.resolution} × {state?.resolution ?? applied.resolution} / 1 m × 1 m DOMAIN</span></div>
          <div className={`flow-legend tunnel-legend legend-${view}`}><span>{fieldLabels[view].label.toUpperCase()} · {fieldLabels[view].unit}</span>
            <div /><span>{format(range[0], 2)}</span><span>{format(range[1], 2)}</span></div>
          <div className="tunnel-inlet"><ArrowRight size={16} /><span>INLET</span><strong>{format(applied.inflow, 2)} m/s</strong></div>
          <div className="flow-overlay-bottom"><span>SIMULATION TIME <strong>{(state?.time ?? 0).toFixed(2)} s</strong></span>
            <span>{dirty ? "DRAFT OUTLINES · APPLY TO SOLVE" : view === "pressure" ? "PROJECTION DIAGNOSTIC" : "FREE-SLIP SOLID BOUNDARIES"}</span></div>
          {busy && <div className="scene-loading"><LoaderCircle className="spin" size={24} /><span>Preparing flow field</span></div>}
        </div>
        <div className={`tunnel-probe ${sample ? "has-sample" : ""}`}>
          <Crosshair size={14} />{sample && probe ? <>
            <span className="probe-position">PROBE {probe.x.toFixed(2)}, {probe.y.toFixed(2)}</span>
            {sample.solid ? <span>Solid obstacle cell</span> : <div className="probe-values">
              <span>Speed <strong>{format(sample.speed)} <em>m/s</em></strong></span>
              <span title={`u ${format(sample.u)} m/s · v ${format(sample.v)} m/s`}>Dye <strong>{format(sample.dye)}</strong></span>
              <span>ω <strong>{format(sample.vorticity)} <em>1/s</em></strong></span>
              <span title="Projection pressure correction; not calibrated pressure">p corr. <strong>{format(sample.pressure)} <em>m²/s²</em></strong></span>
            </div>}
            <button className="icon-button" aria-label="Clear probe" onClick={() => setProbe(null)}><X size={13} /></button>
          </> : <span>Click the flow to probe a cell. Drag an obstacle to reposition it.</span>}
        </div>

      </section>

      <aside className="flow-settings">
        <div className="inspector-heading"><SlidersHorizontal size={15} /><strong>Experiment controls</strong>{dirty && <span className="tunnel-unsaved">DRAFT</span>}</div>
        <div className="tunnel-settings-tabs">{(["geometry", "fluid", "solver"] as const).map((key) =>
          <button key={key} className={tab === key ? "active" : ""} aria-pressed={tab === key} onClick={() => setTab(key)}>{key}</button>)}</div>
        <div className="tunnel-settings-content">
          {tab === "geometry" && <>
            <div className="property-group"><div className="tunnel-group-heading"><h3>Obstacles <span>{config.obstacles.length} / 16</span></h3>
              <button className="icon-button" aria-label="Add obstacle" disabled={config.obstacles.length >= 16 || busy} onClick={addObstacle}><Plus size={14} /></button></div>
              <div className="tunnel-obstacle-list">{config.obstacles.map((obstacle) => <button key={obstacle.name} className={selected === obstacle.name ? "active" : ""} onClick={() => setSelected(obstacle.name)}>
                <span className={`obstacle-symbol ${obstacle.shape}`} /><span>{obstacle.name}<small>{obstacle.shape.startsWith("naca") ? `NACA ${obstacle.shape.slice(4)}` : obstacle.shape}</small></span><ChevronRight size={12} />
              </button>)}{config.obstacles.length === 0 && <p className="tunnel-note">Empty channel. Add an obstacle to study the flow around a body.</p>}</div>
            </div>
            {selectedObstacle && <div className="property-group"><div className="tunnel-group-heading"><h3>Selected body</h3>
              <button className="icon-button tunnel-delete" aria-label={`Remove ${selectedObstacle.name}`} onClick={() => {
                const remaining = config.obstacles.filter((obstacle) => obstacle.name !== selectedObstacle.name);
                setConfig((current) => ({ ...current, obstacles: remaining })); setSelected(remaining[0]?.name ?? null);
              }}><Trash2 size={13} /></button></div>
              <label className="field"><span>Shape</span><select aria-label="Obstacle shape" value={selectedObstacle.shape} onChange={(event) => {
                const shape = event.target.value as FluidObstacle["shape"];
                updateObstacle(selectedObstacle.name, { shape, points: shape === "polygon" ? [[-0.5, -0.5], [0.5, 0], [-0.5, 0.5]] : undefined });
              }}><option value="circle">Cylinder</option><option value="box">Rectangle</option><option value="ellipse">Ellipse</option><option value="naca0012">NACA 0012</option><option value="naca2412">NACA 2412</option><option value="polygon">Polygon</option></select></label>
              {obstacleNumber("Position X", "x", "m", 0, 1)}
              {obstacleNumber("Position Y", "y", "m", 0, 1)}
              {obstacleNumber(selectedObstacle.shape.startsWith("naca") ? "Chord" : selectedObstacle.shape === "circle" ? "Diameter" : "Width", "width", "m", 0.02, 0.9)}
              {!selectedObstacle.shape.startsWith("naca") && selectedObstacle.shape !== "circle" && obstacleNumber("Height", "height", "m", 0.02, 0.9)}
              {obstacleNumber("Rotation (CCW)", "angle", "deg", -180, 180, 1)}
              <p className="tunnel-note">{selectedObstacle.shape.startsWith("naca") ? "12% thickness-to-chord ratio. Angle is counterclockwise from the inlet direction." : selectedObstacle.shape === "polygon" ? "Defaults to a triangle. Import JSON to supply custom local vertices, each between -0.5 and 0.5." : "Coordinates start at the lower left. Bodies must fit inside the 1 m domain."}</p>
            </div>}
          </>}
          {tab === "fluid" && <><div className="property-group"><h3>Fluid properties</h3>
            {number("Inlet velocity", "inflow", "m/s", 0.1, 0, 3)}
            {number("Kinematic viscosity", "viscosity", "m²/s", 0.0001, 0, 0.1)}
            {number("Dye diffusion", "diffusion", "m²/s", 0.00001, 0, 0.1)}
            {number("Dissipation", "dissipation", "/s", 0.01, 0, 5)}
          </div><div className="property-group"><h3>Dye injection</h3>
            <label className="field"><span>Source pattern</span><select aria-label="Source pattern" value={config.source_mode} onChange={(event) => setConfig((current) => ({ ...current, source_mode: event.target.value as "rake" | "jet" }))}><option value="rake">Smoke rake</option><option value="jet">Single jet</option></select></label>
            {number("Dye source", "dye_source", "/s", 0.25, 0, 20)}
            {number("Source X", "source_x", "m", 0.01, 0, 1)}
            {config.source_mode === "jet" && number("Source Y", "source_y", "m", 0.01, 0, 1)}
            {config.source_mode === "jet" && number("Source radius", "source_radius", "m", 0.005, 0.01, 0.3)}
            <p className="tunnel-note">{config.source_mode === "rake" ? "Nine one-cell dye sources span Y = 0.1 to 0.9. " : "Passive dye traces the moving fluid. "}Streamlines follow the current velocity field.</p>
          </div></>}
          {tab === "solver" && <><div className="property-group"><h3>Numerical settings</h3>
            <label className="field"><span>Resolution</span><select aria-label="Resolution" value={config.resolution} onChange={(event) => setConfig((current) => ({ ...current, resolution: Number(event.target.value) }))}>{[32, 64, 96, 128].map((resolution) => <option key={resolution} value={resolution}>{resolution} × {resolution}</option>)}</select></label>
            {number("Timestep", "timestep", "s", 0.001, 0.001, 0.1)}
            {number("Pressure iterations", "iterations", "max", 10, 10, 200)}
            <p className="tunnel-note">Higher resolution and more iterations cost more compute. Divergence RMS reports the remaining incompressibility error.</p>
          </div><div className="property-group tunnel-solver-info"><h3>Model assumptions</h3><p>2D incompressible channel with free-slip solid boundaries and a passive dye field.</p><p>Pressure correction is a solver diagnostic. It does not calculate calibrated aerodynamic pressure, lift or drag.</p><p>This fluid session runs independently of the rigid-body simulator.</p></div></>}
        </div>
        <div className="flow-apply"><button className={`button ${dirty || !id ? "primary" : ""}`} disabled={(!dirty && !!id) || busy} onClick={() => void create(config)}>
          {busy ? <LoaderCircle size={14} className="spin" /> : <Check size={14} />}{busy ? "Preparing experiment…" : dirty ? "Apply & restart" : !id ? "Retry experiment" : "Configuration applied"}</button>
          <p>{dirty ? "Edits take effect when you restart the field." : "Edit obstacle properties or select a preset configuration."}</p></div>
      </aside>
    </div>
    <div className="flow-metrics">{[
      ["Max velocity", state?.metrics.max_speed, "m/s"], ["Kinetic energy", state?.metrics.kinetic_energy, "a.u."],
      ["Divergence RMS", state?.metrics.divergence_rms, "1/s"], ["CFL number", state?.metrics.cfl, "dimensionless"],
    ].map(([label, value, unit]) => <div key={String(label)}><span>{label}</span><strong>{format(typeof value === "number" ? value : undefined, 4)}<small>{unit}</small></strong></div>)}</div>
    <div className="tunnel-footnote"><Info size={12} /><span>Educational 2D flow. Grid-resolved geometry and free-slip walls; no coupled 3D CFD or aerodynamic force prediction.</span><span>LOCAL COMPUTE <span className="idle-dot" /></span></div>
  </div>;
}
