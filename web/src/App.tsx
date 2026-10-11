import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpFromLine,
  Box,
  Boxes,
  CarFront,
  Check,
  ChevronDown,
  ChevronRight,
  Code2,
  Copy,
  Dog,
  ExternalLink,
  Focus,
  Globe2,
  Grid2X2,
  HelpCircle,
  Layers3,
  Link2,
  LoaderCircle,
  Maximize2,
  Pause,
  Plane,
  Play,
  Plus,
  Radio,
  RotateCcw,
  Save,
  Settings2,
  SlidersHorizontal,
  StepForward,
  Terminal,
  Trash2,
  Wind,
  X,
  Zap,
} from "lucide-react";
import SceneView from "./SceneView";
import FlowLab from "./FlowLab";
import {
  api,
  type Point,
  type Primitive,
  type SceneConfig,
  type Snapshot,
  type Template,
  type World,
} from "./types";
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));
const templateIcons: Record<string, typeof CarFront> = {
  driving: CarFront,
  quadruped: Dog,
  flight: Plane,
  sandbox: Boxes,
};
const templateLabels: Record<string, string> = {
  driving: "Vehicle dynamics",
  quadruped: "Quadruped locomotion",
  flight: "Aircraft dynamics",
  sandbox: "Rigid-body dynamics",
};
function Field({
  label,
  value,
  onChange,
  unit,
  min,
  max,
  step = 0.1,
  disabled = false,
}: {
  label: string;
  value: number;
  onChange: (n: number) => void;
  unit?: string;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <div className="number-input">
        <input
          aria-label={label}
          type="number"
          value={Number.isFinite(value) ? value : 0}
          onChange={(e) => {
            if (e.target.value !== "") onChange(Number(e.target.value));
          }}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
        />
        {unit && <em>{unit}</em>}
      </div>
    </label>
  );
}
function VectorField({
  label,
  value,
  onChange,
  unit,
  disabled = false,
}: {
  label: string;
  value: number[];
  onChange: (v: [number, number, number]) => void;
  unit?: string;
  disabled?: boolean;
}) {
  return (
    <div className="vector-field">
      <label>
        {label}
        <span>{unit}</span>
      </label>
      <div className="vector-inputs">
        {value.map((v, i) => (
          <div key={i}>
            <span className={"axis-" + i}>{"XYZ"[i]}</span>
            <input
              aria-label={`${label} ${"XYZ"[i]}`}
              value={Number(v.toFixed(5))}
              type="number"
              step="0.1"
              disabled={disabled}
              onChange={(e) => {
                const next = [...value] as [number, number, number];
                next[i] = Number(e.target.value);
                onChange(next);
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
function Sparkline({
  points,
  field,
  color,
}: {
  points: Point[];
  field: "speed" | "reward";
  color: string;
}) {
  const values = points.map((p) => p[field]);
  const min = Math.min(0, ...values),
    max = Math.max(1, ...values);
  const path = values
    .map(
      (v, i) =>
        `${i ? "L" : "M"} ${(i / Math.max(1, values.length - 1)) * 400} ${48 - ((v - min) / (max - min)) * 40}`,
    )
    .join(" ");
  return (
    <svg
      className="sparkline"
      viewBox="0 0 400 58"
      preserveAspectRatio="none"
      aria-label={`${field} history`}
    >
      <line
        x1="0"
        y1="48"
        x2="400"
        y2="48"
        stroke="#33383e"
        strokeDasharray="3 5"
      />
      {values.length > 1 && (
        <>
          <path d={`${path} L400,58 L0,58 Z`} fill={color} opacity=".06" />
          <path
            d={path}
            fill="none"
            stroke={color}
            strokeWidth="1.6"
            vectorEffect="non-scaling-stroke"
          />
        </>
      )}
    </svg>
  );
}
function Modal({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  return (
    <div
      className="modal-scrim"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <section
        className={`modal ${wide ? "wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header>
          <h2>{title}</h2>
          <button
            className="icon-button"
            aria-label="Close dialog"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}
export default function App() {
  const [templates, setTemplates] = useState<Template[]>([]),
    [world, setWorld] = useState<World | null>(null),
    [draft, setDraft] = useState<SceneConfig | null>(null),
    [state, setState] = useState<Snapshot | null>(null),
    [activeTemplate, setActiveTemplate] = useState("driving"),
    [tab, setTab] = useState<"world" | "flow" | "connect">("world"),
    [playing, setPlaying] = useState(false),
    [attached, setAttached] = useState(false),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [toast, setToast] = useState(""),
    [history, setHistory] = useState<Point[]>([]),
    [selected, setSelected] = useState("robot"),
    [inspectorTab, setInspectorTab] = useState<"world" | "object">("world"),
    [view, setView] = useState<"orbit" | "top" | "follow">("orbit"),
    [followSubject, setFollowSubject] = useState("robot"),
    [cameraReset, setCameraReset] = useState(0),
    [grid, setGrid] = useState(true),
    [modal, setModal] = useState<
      "add" | "json" | "sessions" | "help" | "saved" | null
    >(null),
    [json, setJson] = useState(""),
    [sessions, setSessions] = useState<
      { id: string; name: string; robot: string; time: number }[]
    >([]),
    [saved, setSaved] = useState<
      { name: string; filename: string; scene: SceneConfig }[]
    >([]),
    [connectLang, setConnectLang] = useState<"python" | "javascript" | "curl">(
      "python",
    );
  const fileInput = useRef<HTMLInputElement>(null);
  const ownedWorld = useRef<string | null>(null);
  const busyRef = useRef(false);
  const notify = (message: string) => {
    setToast(message);
  };
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 3600);
    return () => clearTimeout(timer);
  }, [toast]);
  const receive = useCallback((next: Snapshot) => {
    setState(next);
    setHistory((h) =>
      [
        ...h,
        { time: next.time, speed: next.info.speed, reward: next.reward },
      ].slice(-150),
    );
  }, []);
  const adopt = useCallback((next: World, isAttached = false) => {
    const previous = ownedWorld.current;
    ownedWorld.current = isAttached ? null : next.id;
    if (previous && previous !== next.id)
      void api(`/worlds/${previous}`, "DELETE").catch(() => {});
    setWorld(next);
    setDraft(clone(next.scene));
    setState(next.state);
    setHistory([]);
    setPlaying(false);
    setAttached(isAttached);
    setSelected("robot");
    setInspectorTab("world");
    setError("");
  }, []);
  const loadTemplate = useCallback(
    async (id: string) => {
      setPlaying(false);
      setBusy(true);
      setError("");
      try {
        const next = await api<World>("/worlds", "POST", { template: id });
        adopt(next);
        setActiveTemplate(id);
        setTab("world");
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [adopt],
  );
  useEffect(() => {
    const cleanup = () => {
      if (ownedWorld.current) {
        void fetch("/api/v1/worlds/" + ownedWorld.current, {
          method: "DELETE",
          keepalive: true,
        });
        ownedWorld.current = null;
      }
    };
    window.addEventListener("pagehide", cleanup);
    return () => {
      window.removeEventListener("pagehide", cleanup);
      cleanup();
    };
  }, []);
  const initialize = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const list = await api<Template[]>("/templates");
      setTemplates(list);
      const next = await api<World>("/worlds", "POST", { template: "driving" });
      adopt(next);
    } catch (e) {
      setError(
        "Unable to connect to the physics server. " + (e as Error).message,
      );
    } finally {
      setLoading(false);
    }
  }, [adopt]);
  useEffect(() => {
    void initialize();
  }, [initialize]);
  useEffect(() => {
    if (!playing || !world || attached || tab !== "world") return;
    let canceled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function tick() {
      if (canceled) return;
      try {
        busyRef.current = true;
        const next = await api<Snapshot>(`/worlds/${world!.id}/step`, "POST", {
          demo: true,
        });
        if (!canceled) {
          receive(next);
          if (next.terminated || next.truncated) {
            setPlaying(false);
            notify(
              next.truncated
                ? "Episode limit reached. Reset to run again."
                : "Episode finished. Reset to run again.",
            );
            return;
          }
          timer = setTimeout(tick, Math.max(0, world!.description.dt * 1000));
        }
      } catch (e) {
        if (!canceled) {
          setError((e as Error).message);
          setPlaying(false);
        }
      } finally {
        busyRef.current = false;
      }
    }
    void tick();
    return () => {
      canceled = true;
      clearTimeout(timer);
    };
  }, [playing, world, attached, receive, tab]);
  useEffect(() => {
    if (!attached || !world) return;
    let cancel = false;
    const poll = async () => {
      try {
        const next = await api<Snapshot>(`/worlds/${world.id}/state`);
        if (!cancel) receive(next);
      } catch (e) {
        if (!cancel) setError((e as Error).message);
      }
    };
    void poll();
    const timer = setInterval(poll, 200);
    return () => {
      cancel = true;
      clearInterval(timer);
    };
  }, [attached, world, receive]);
  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const reset = () => {
    setPlaying(false);
    void run(async () => {
      if (!world) return;
      while (busyRef.current)
        await new Promise((resolve) => setTimeout(resolve, 20));
      const next = await api<Snapshot>(`/worlds/${world.id}/reset`, "POST", {
        seed: draft?.terrain.seed ?? 0,
      });
      setHistory([]);
      receive(next);
    });
  };
  const step = () => {
    void run(async () => {
      if (world)
        receive(
          await api<Snapshot>(`/worlds/${world.id}/step`, "POST", {
            demo: true,
          }),
        );
    });
  };
  const apply = async (next = draft) => {
    if (!world || !next) return;
    setPlaying(false);
    await run(async () => {
      while (busyRef.current)
        await new Promise((resolve) => setTimeout(resolve, 20));
      const updated = await api<World>(
        `/worlds/${world.id}/scene`,
        "PUT",
        next,
      );
      const oldSelected = selected;
      adopt(updated);
      setSelected(oldSelected);
      notify("Scene compiled · simulation reset");
    });
  };
  const mutate = (fn: (s: SceneConfig) => void) =>
    setDraft((previous) => {
      if (!previous) return previous;
      const next = clone(previous);
      fn(next);
      return next;
    });
  const dirty =
    !!world && !!draft && JSON.stringify(world.scene) !== JSON.stringify(draft);
  const object = draft?.objects.find((o) => o.name === selected);
  const selectedRobot = selected === "robot";
  // Camera tracking is independent of inspector selection and unapplied edits.
  const robotSubjects = {
    car: { id: "robot", label: "Vehicle", geom: "robot_chassis" },
    quadruped: { id: "robot", label: "Quadruped", geom: "robot_torso" },
    aircraft: { id: "robot", label: "Aircraft", geom: "robot_fuselage" },
    none: null,
  };
  const robotSubject = robotSubjects[world?.scene.robot.kind ?? "none"];
  const cameraSubjects = [
    ...(robotSubject ? [robotSubject] : []),
    ...(world?.scene.objects ?? []).map((item) => ({
      id: `object:${item.name}`,
      label: item.name,
      geom: item.name,
    })),
  ];
  const cameraSubject =
    cameraSubjects.find((item) => item.id === followSubject) ??
    robotSubject ??
    cameraSubjects.find((item) =>
      world?.scene.objects.some(
        (object) => object.name === item.geom && !object.static,
      ),
    ) ??
    cameraSubjects[0];
  const following = view === "follow" && !!cameraSubject;
  const chooseObject = (name: string) => {
    if (draft?.objects.some((o) => o.name === name)) setSelected(name);
    else {
      const obj = draft?.objects.find(
        (o) => name === o.name + "_geom" || name.startsWith(o.name + ":"),
      );
      setSelected(obj?.name ?? "robot");
    }
    setInspectorTab("object");
  };
  const save = () =>
    void run(async () => {
      if (!draft) return;
      const result = await api<{ name: string; filename: string }>(
        "/scenes",
        "POST",
        draft,
      );
      notify(`Saved ${result.name} locally`);
    });
  const exportScene = () => {
    if (!draft) return;
    const blob = new Blob([JSON.stringify(draft, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download =
      draft.name.replace(/[^a-z0-9]+/gi, "-").toLowerCase() + ".json";
    link.click();
    URL.revokeObjectURL(url);
    notify("Scene JSON exported");
  };
  const importScene = async (text: string) => {
    await run(async () => {
      const scene = JSON.parse(text);
      const next = await api<World>("/worlds", "POST", { scene });
      adopt(next);
      setActiveTemplate("custom");
      setModal(null);
      notify("Scene imported");
    });
  };
  const addObject = async (kind: Primitive["kind"]) => {
    if (!draft) return;
    const next = clone(draft);
    let n = 1;
    while (next.objects.some((o) => o.name === `${kind}_${n}`)) n++;
    const name = `${kind}_${n}`;
    next.objects.push({
      name,
      kind,
      size: kind === "box" ? [0.6, 0.6, 0.6] : [0.5, 0.6, 0.5],
      position: [3, 1, 2],
      rotation: [0, 0, 0],
      mass: 2,
      static: false,
      color: [0.98, 0.36, 0.16, 1],
    });
    setDraft(next);
    setSelected(name);
    setInspectorTab("object");
    setModal(null);
    await apply(next);
    setSelected(name);
    setInspectorTab("object");
  };
  const showSessions = () => {
    setPlaying(false);
    setModal("sessions");
    void run(async () => setSessions(await api("/worlds")));
  };
  const snippet =
    connectLang === "python"
      ? `import httpx\n\nBASE = "http://127.0.0.1:8000/api/v1"\nworld_id = "${world?.id ?? "YOUR_WORLD_ID"}"\n\n# Reset this session before training.\nstate = httpx.post(\n    f"{BASE}/worlds/{world_id}/reset",\n    json={"seed": 42}\n).json()\n\n# Replace zeros with your policy's normalized actions.\naction = [0.0] * ${world?.description.action_size ?? 2}\nstate = httpx.post(\n    f"{BASE}/worlds/{world_id}/step",\n    json={"action": action}\n).json()\n\nprint(state["observation"], state["reward"])`
      : connectLang === "javascript"
        ? `const base = 'http://127.0.0.1:8000/api/v1';\nconst worldId = '${world?.id ?? "YOUR_WORLD_ID"}';\n\nasync function step(action) {\n  const response = await fetch(\n    \u0060\u0024{base}/worlds/\u0024{worldId}/step\u0060,\n    {\n      method: 'POST',\n      headers: { 'Content-Type': 'application/json' },\n      body: JSON.stringify({ action })\n    }\n  );\n  if (!response.ok) throw new Error(await response.text());\n  return response.json();\n}\n\nconst state = await step(Array(${world?.description.action_size ?? 2}).fill(0));\nconsole.log(state.observation, state.reward);`
        : `curl -X POST \\\n  http://127.0.0.1:8000/api/v1/worlds/${world?.id ?? "YOUR_WORLD_ID"}/step \\\n  -H 'Content-Type: application/json' \\\n  -d '{"action": ${JSON.stringify(Array(world?.description.action_size ?? 2).fill(0))}}'`;
  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      notify("Copied to clipboard");
    } catch {
      setError(
        "Clipboard access is unavailable. Select and copy the code manually.",
      );
    }
  };
  const worldName = world?.scene.name ?? "Initializing world";
  return (
    <div className="studio-app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">K</span>
          <strong>
            KINETIC<span> / SIMULATION</span>
          </strong>
          <span className="version-badge">STUDIO</span>
        </div>
        <nav className="main-nav">
          <button
            className={tab === "world" ? "active" : ""}
            onClick={() => setTab("world")}
          >
            <Layers3 size={15} />
            Scene editor
          </button>
          <button
            className={tab === "flow" ? "active" : ""}
            onClick={() => {
              setPlaying(false);
              setTab("flow");
            }}
          >
            <Wind size={16} />
            Fluid dynamics<span className="tiny-tag">2D</span>
          </button>
          <button
            className={tab === "connect" ? "active" : ""}
            onClick={() => {
              setPlaying(false);
              setTab("connect");
            }}
          >
            <Code2 size={16} />
            Policy integration
          </button>
        </nav>
        <div className="header-right">
          <span className={`connection ${world ? "online" : ""}`}>
            <i />
            {world ? "Local engine" : "Connecting"}
          </span>
          <button
            className="icon-button"
            aria-label="User guide"
            onClick={() => setModal("help")}
          >
            <HelpCircle size={18} />
          </button>
          <div className="avatar">L</div>
        </div>
      </header>
      {error && (
        <div className="error-banner">
          <Activity size={16} />
          <span>{error}</span>
          {!world && (
            <button onClick={() => void initialize()}>Retry connection</button>
          )}
          <button
            className="icon-button"
            aria-label="Dismiss error"
            onClick={() => setError("")}
          >
            <X size={15} />
          </button>
        </div>
      )}
      {tab === "flow" ? (
        <FlowLab notify={notify} />
      ) : tab === "connect" ? (
        <main className="connect-page">
          <div className="connect-intro">
            <span className="eyebrow orange">REINFORCEMENT LEARNING</span>
            <h1>Policy integration</h1>
            <p>
              Control isolated simulation sessions through the HTTP API.
              Submit policy actions, retrieve observations, and manage simulation steps.
            </p>
            <div className="connection-card">
              <span className="status-dot" />
              <div>
                <strong>Local HTTP / JSON API</strong>
                <code>127.0.0.1:8000/api/v1</code>
              </div>
              <a
                className="icon-button"
                href="/docs"
                target="_blank"
                rel="noreferrer"
                aria-label="Open API documentation"
              >
                <ExternalLink size={18} />
              </a>
            </div>
            <div className="contract-stats">
              <div>
                <strong>{world?.description.action_size ?? "—"}</strong>
                <span>action dimensions</span>
              </div>
              <div>
                <strong>{world?.description.observation_size ?? "—"}</strong>
                <span>observation dimensions</span>
              </div>
              <div>
                <strong>
                  {world ? (world.description.dt * 1000).toFixed(0) : "—"}
                  <small>ms</small>
                </strong>
                <span>simulation step</span>
              </div>
            </div>
            <div className="connect-note">
              <Link2 size={18} />
              <div>
                <strong>Session monitoring</strong>
                <p>
                  Attach to a running session to inspect its state. The viewer
                  polls without stepping your environment.
                </p>
                <button className="text-button" onClick={showSessions}>
                  Browse active sessions <ArrowRight size={14} />
                </button>
              </div>
            </div>
            <a
              className="text-button muted"
              href="/api/v1/schema"
              target="_blank"
              rel="noreferrer"
            >
              View scene schema <ExternalLink size={13} />
            </a>
          </div>
          <div className="code-panel">
            <div className="code-header">
              <div>
                {(["python", "javascript", "curl"] as const).map((lang) => (
                  <button
                    key={lang}
                    className={connectLang === lang ? "active" : ""}
                    onClick={() => setConnectLang(lang)}
                  >
                    {lang === "python"
                      ? "Python"
                      : lang === "javascript"
                        ? "JavaScript"
                        : "cURL"}
                  </button>
                ))}
              </div>
              <button
                className="icon-button"
                aria-label="Copy integration code"
                onClick={() => void copy(snippet)}
              >
                <Copy size={16} />
              </button>
            </div>
            <div className="code-caption">
              <Terminal size={14} /> Connect to {worldName}
            </div>
            <pre>
              <code>{snippet}</code>
            </pre>
            <div className="code-footer">
              <span className="status-dot" />
              Normalized actions in [−1, 1] · deterministic fixed steps
            </div>
          </div>
        </main>
      ) : (
        <>
          <div className="workspace-bar">
            <div className="breadcrumbs">
              <span>Workspace</span>
              <ChevronRight size={13} />
              <strong>{worldName}</strong>
              <span className="local-tag">LOCAL</span>
              {dirty && (
                <span className="unsaved-dot" title="Unapplied changes" />
              )}
            </div>
            <div className="workspace-actions">
              <button
                className="ghost-button"
                onClick={() => {
                  setJson(JSON.stringify(draft, null, 2));
                  setModal("json");
                }}
                disabled={!draft}
              >
                <Code2 size={14} />
                Scene JSON
              </button>
              <button
                className="ghost-button"
                onClick={() => fileInput.current?.click()}
              >
                <ArrowUpFromLine size={14} />
                Import
              </button>
              <button
                className="ghost-button"
                disabled={!draft}
                onClick={exportScene}
              >
                <ArrowDownToLine size={14} />
                Export
              </button>
              <button
                className="button small"
                disabled={!draft || busy}
                onClick={save}
              >
                <Save size={14} />
                Save world
              </button>
              <input
                ref={fileInput}
                type="file"
                accept="application/json,.json"
                className="hidden"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (file) await importScene(await file.text());
                  e.target.value = "";
                }}
              />
            </div>
          </div>
          <main className="workbench">
            <aside className="left-panel">
              <div className="panel-heading">
                <span>WORLD LIBRARY</span>
                <button
                  className="icon-button"
                  title="Open saved worlds"
                  aria-label="Open saved worlds"
                  onClick={() => {
                    setModal("saved");
                    void run(async () => setSaved(await api("/scenes")));
                  }}
                >
                  <Save size={14} />
                </button>
              </div>
              <div className="template-list">
                {templates.map((template) => {
                  const Icon = templateIcons[template.id] ?? Boxes;
                  return (
                    <button
                      key={template.id}
                      className={`template-card ${activeTemplate === template.id ? "selected" : ""}`}
                      onClick={() => void loadTemplate(template.id)}
                      disabled={busy}
                    >
                      <div className={`template-art ${template.id}`}>
                        <Icon size={34} strokeWidth={1.25} />
                        <span className="art-grid" />
                      </div>
                      <div>
                        <strong>
                          {templateLabels[template.id] ?? template.name}
                        </strong>
                        <span>{template.category ?? template.id}</span>
                      </div>
                      {activeTemplate === template.id && (
                        <span className="template-indicator" />
                      )}
                    </button>
                  );
                })}
              </div>
              <div className="section-divider" />
              <div className="panel-heading">
                <span>SCENE HIERARCHY</span>
                <button
                  className="icon-button"
                  aria-label="Add object"
                  title="Add object"
                  disabled={attached || !draft}
                  onClick={() => setModal("add")}
                >
                  <Plus size={16} />
                </button>
              </div>
              <div className="hierarchy">
                <button
                  className={selected === "world" ? "active" : ""}
                  onClick={() => {
                    setSelected("world");
                    setInspectorTab("world");
                  }}
                >
                  <ChevronDown size={12} />
                  <Globe2 size={15} />
                  <span>{worldName}</span>
                </button>
                <div className="tree-children">
                  <button
                    onClick={() => {
                      setSelected("terrain");
                      setInspectorTab("world");
                    }}
                    className={selected === "terrain" ? "active" : ""}
                  >
                    <Grid2X2 size={14} />
                    <span>Ground / terrain</span>
                    <span className="item-badge">static</span>
                  </button>
                  {draft?.robot.kind !== "none" && (
                    <button
                      className={selectedRobot ? "active" : ""}
                      onClick={() => {
                        setSelected("robot");
                        setInspectorTab("object");
                      }}
                    >
                      <Box size={14} />
                      <span>
                        {draft?.robot.kind === "car"
                          ? "Vehicle"
                          : draft?.robot.kind === "quadruped"
                            ? "Quadruped"
                            : "Aircraft"}
                      </span>
                      <span className="item-live" />
                    </button>
                  )}
                  {draft?.objects.map((item) => (
                    <button
                      key={item.name}
                      className={selected === item.name ? "active" : ""}
                      onClick={() => {
                        setSelected(item.name);
                        setInspectorTab("object");
                      }}
                    >
                      <Box size={13} />
                      <span>{item.name.replaceAll("_", " ")}</span>
                      {item.static && (
                        <span className="item-badge">static</span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
              <div className="left-bottom">
                <div className="engine-card">
                  <div className="engine-icon">
                    <Zap size={17} />
                  </div>
                  <div>
                    <strong>MuJoCo</strong>
                    <span>Native CPU · Apple Silicon ready</span>
                  </div>
                  <span className="status-dot" />
                </div>
                <button className="session-link" onClick={showSessions}>
                  <Radio size={14} />
                  <span>
                    {attached ? "Attached session" : "Local simulation session"}
                  </span>
                  <ChevronRight size={13} />
                </button>
              </div>
            </aside>
            <section className="center-panel">
              <div className="viewport">
                <SceneView
                  key={world?.id}
                  state={state}
                  robot={world?.scene.robot.kind ?? "car"}
                  track={activeTemplate === "driving"}
                  selected={selected}
                  view={view === "follow" && !cameraSubject ? "orbit" : view}
                  followTarget={cameraSubject?.geom ?? null}
                  cameraReset={cameraReset}
                  grid={grid}
                  onSelect={chooseObject}
                />
                <div className="viewport-top">
                  <div className="viewport-label">
                    <span className={playing ? "status-dot" : "idle-dot"} />
                    {attached
                      ? "LIVE VIEW"
                      : playing
                        ? "SIMULATING"
                        : "SCENE VIEW"}
                    <span className="label-divider" />
                    {following
                      ? "SUBJECT LOCKED"
                      : view === "top" ? "Top view" : "Perspective"}
                  </div>
                  <div className="viewport-tools">
                    <button
                      className={grid ? "active" : ""}
                      title="Toggle ground grid"
                      aria-label="Toggle ground grid"
                      onClick={() => setGrid(!grid)}
                    >
                      <Grid2X2 size={16} />
                    </button>
                    <button
                      className={view === "top" ? "active" : ""}
                      title="Top view"
                      aria-label="Top view"
                      onClick={() => setView(view === "top" ? "orbit" : "top")}
                    >
                      <Layers3 size={16} />
                    </button>
                    <button
                      className={`follow-button ${following ? "active" : ""}`}
                      title="Keep the subject centered while the world moves around it"
                      aria-label="Follow subject"
                      aria-pressed={following}
                      disabled={!cameraSubject}
                      onClick={() =>
                        setView(view === "follow" ? "orbit" : "follow")
                      }
                    >
                      <Focus size={16} />
                      <span>Follow subject</span>
                    </button>
                    {following && (
                      <select
                        className="camera-subject"
                        aria-label="Camera subject"
                        title="Choose the subject to follow"
                        value={cameraSubject.id}
                        onChange={(event) => setFollowSubject(event.target.value)}
                      >
                        {cameraSubjects.map((subject) => (
                          <option key={subject.id} value={subject.id}>
                            {subject.label}
                          </option>
                        ))}
                      </select>
                    )}
                    <button
                      title="Reset camera"
                      aria-label="Reset camera"
                      onClick={() => {
                        setView("orbit");
                        setCameraReset((value) => value + 1);
                      }}
                    >
                      <Maximize2 size={16} />
                    </button>
                  </div>
                </div>
                <div className="scene-caption">
                  <span className="scene-number">
                    {templates.some((t) => t.id === activeTemplate)
                      ? String(
                          templates.findIndex((t) => t.id === activeTemplate) +
                            1,
                        ).padStart(2, "0")
                      : "—"}{" "}
                    / {String(templates.length || 4).padStart(2, "0")}
                  </span>
                  <h2>{templateLabels[activeTemplate] ?? "Custom world"}</h2>
                  <p>
                    {activeTemplate === "driving"
                      ? "Vehicle dynamics · contact-rich rigid body simulation"
                      : activeTemplate === "quadruped"
                        ? "Articulated joints · contact-rich locomotion"
                        : activeTemplate === "flight"
                          ? "Rigid body flight · approximate aerodynamics"
                          : "Configurable geometry and rigid-body contact dynamics"}
                  </p>
                </div>
                <div className="viewport-bottom">
                  <div className="axis-gizmo">
                    <i className="z">Z</i>
                    <i className="x">X</i>
                    <i className="y">Y</i>
                  </div>
                  <span className="viewport-hint">
                    Drag to orbit <b>·</b> Scroll to zoom <b>·</b>{" "}
                    {following ? "Subject stays centered" : "Right-drag to pan"}
                  </span>
                  <span className="units-badge">METERS / Z-UP</span>
                </div>
                {(loading || busy) && (
                  <div className={`scene-loading ${state ? "subtle" : ""}`}>
                    <LoaderCircle size={23} className="spin" />
                    <span>
                      {loading ? "Starting physics engine" : "Compiling world"}
                    </span>
                  </div>
                )}
                {!world && !loading && (
                  <div className="offline-state">
                    <Activity size={28} />
                    <h3>Physics server unavailable</h3>
                    <p>Start the local API to load a simulation.</p>
                    <code>python -m rl_sim.server</code>
                    <button
                      className="button"
                      onClick={() => void initialize()}
                    >
                      Reconnect
                    </button>
                  </div>
                )}
              </div>
              <div className="telemetry">
                <div className="telemetry-heading">
                  <div>
                    <Activity size={14} />
                    <strong>Live telemetry</strong>
                    <span>{state?.step ?? 0} steps</span>
                  </div>
                  <span className="telemetry-source">
                    ENGINE DATA <i />
                  </span>
                </div>
                <div className="telemetry-grid">
                  <div className="metric-chart">
                    <div className="metric-label">
                      Speed <span>m/s</span>
                    </div>
                    <strong className="metric-value">
                      {(state?.info.speed ?? 0).toFixed(2)}
                    </strong>
                    <Sparkline points={history} field="speed" color="#ff865e" />
                  </div>
                  <div className="metric-chart">
                    <div className="metric-label">
                      Step reward <span>task score</span>
                    </div>
                    <strong className="metric-value">
                      {(state?.reward ?? 0).toFixed(3)}
                    </strong>
                    <Sparkline
                      points={history}
                      field="reward"
                      color="#86c8b6"
                    />
                  </div>
                  <div className="metric-stack">
                    <div>
                      <span>Simulation time</span>
                      <strong>
                        {(state?.time ?? 0).toFixed(2)} <small>s</small>
                      </strong>
                    </div>
                    <div>
                      <span>Active contacts</span>
                      <strong>{state?.info.contacts ?? 0}</strong>
                    </div>
                    <div>
                      <span>Engine geometries</span>
                      <strong>{state?.geoms.length ?? 0}</strong>
                    </div>
                  </div>
                </div>
              </div>
              <div className="transport">
                <div className="transport-controls">
                  <button
                    className="icon-button"
                    onClick={reset}
                    disabled={!world || busy || attached}
                    title="Reset simulation"
                    aria-label="Reset simulation"
                  >
                    <RotateCcw size={17} />
                  </button>
                  <button
                    className={`play-button ${playing ? "playing" : ""}`}
                    onClick={() => setPlaying(!playing)}
                    disabled={
                      !world ||
                      busy ||
                      attached ||
                      !!state?.terminated ||
                      !!state?.truncated
                    }
                    aria-label={
                      playing ? "Pause simulation" : "Run scripted demo"
                    }
                  >
                    {playing ? (
                      <Pause size={16} fill="currentColor" />
                    ) : (
                      <Play size={16} fill="currentColor" />
                    )}
                    <span>{playing ? "Pause" : "Run"}</span>
                  </button>
                  <button
                    className="icon-button"
                    onClick={step}
                    disabled={!world || playing || busy || attached}
                    title="Advance one simulation step"
                    aria-label="Advance one simulation step"
                  >
                    <StepForward size={18} />
                  </button>
                  <span className="transport-divider" />
                  <span className="controller-badge">
                    <Code2 size={13} />
                    {attached ? "External controller" : "Scripted demo"}
                    <span className="micro-dot" />
                  </span>
                </div>
                <div className="transport-info">
                  <span>{world?.description.action_size ?? 0} actions</span>
                  <i>·</i>
                  <span>
                    {world ? (world.description.dt * 1000).toFixed(0) : "—"} ms
                    / step
                  </span>
                </div>
              </div>
            </section>
            <aside className="inspector">
              <div className="inspector-heading">
                <Settings2 size={16} />
                <strong>Inspector</strong>
                <span className="inspector-badge">SI</span>
              </div>
              <div className="inspector-tabs">
                <button
                  className={inspectorTab === "world" ? "active" : ""}
                  onClick={() => setInspectorTab("world")}
                >
                  World settings
                </button>
                <button
                  className={inspectorTab === "object" ? "active" : ""}
                  onClick={() => setInspectorTab("object")}
                >
                  Selected object
                </button>
              </div>
              {draft && (
                <div className="inspector-scroll">
                  {attached && (
                    <div className="read-only-note">
                      <Radio size={14} />
                      Attached session · read only
                    </div>
                  )}
                  {inspectorTab === "world" ? (
                    <>
                      <div className="property-group">
                        <h3>
                          <Globe2 size={14} />
                          Environment
                        </h3>
                        <label className="text-field">
                          <span>World name</span>
                          <input
                            value={draft.name}
                            disabled={attached}
                            onChange={(e) =>
                              mutate((s) => (s.name = e.target.value))
                            }
                          />
                        </label>
                        <Field
                          label="Gravity"
                          value={Math.abs(draft.physics.gravity[2])}
                          onChange={(v) =>
                            mutate((s) => (s.physics.gravity[2] = -Math.abs(v)))
                          }
                          min={0}
                          max={100}
                          unit="m/s²"
                          disabled={attached}
                        />
                        <div className="gravity-presets">
                          {[
                            ["Earth", 9.81],
                            ["Moon", 1.62],
                            ["Mars", 3.71],
                          ].map(([label, v]) => (
                            <button
                              key={label}
                              className={
                                Math.abs(draft.physics.gravity[2] + Number(v)) <
                                0.01
                                  ? "active"
                                  : ""
                              }
                              disabled={attached}
                              onClick={() =>
                                mutate(
                                  (s) => (s.physics.gravity[2] = -Number(v)),
                                )
                              }
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                        <Field
                          label="Air density"
                          value={draft.physics.density}
                          onChange={(v) =>
                            mutate((s) => (s.physics.density = v))
                          }
                          min={0}
                          unit="kg/m³"
                          step={0.01}
                          disabled={attached}
                        />
                        <Field
                          label="Viscosity"
                          value={draft.physics.viscosity}
                          onChange={(v) =>
                            mutate((s) => (s.physics.viscosity = v))
                          }
                          min={0}
                          unit="Pa·s"
                          step={0.00001}
                          disabled={attached}
                        />
                        <VectorField
                          label="Wind velocity"
                          value={draft.physics.wind}
                          unit="m/s"
                          disabled={attached}
                          onChange={(v) => mutate((s) => (s.physics.wind = v))}
                        />
                      </div>
                      <div className="property-group">
                        <h3>
                          <Grid2X2 size={14} />
                          Ground & contact
                        </h3>
                        <label className="field">
                          <span>Terrain</span>
                          <select
                            value={draft.terrain.kind}
                            disabled={attached}
                            onChange={(e) =>
                              mutate(
                                (s) =>
                                  (s.terrain.kind = e.target.value as
                                    "flat" | "rough" | "stairs"),
                              )
                            }
                          >
                            <option value="flat">Flat plane</option>
                            <option value="rough">Rough terrain</option>
                            <option value="stairs">Stair course</option>
                          </select>
                        </label>
                        <Field
                          label="Surface friction"
                          value={draft.physics.friction}
                          onChange={(v) =>
                            mutate((s) => (s.physics.friction = v))
                          }
                          min={0}
                          max={5}
                          step={0.05}
                          disabled={attached}
                        />
                        <Field
                          label="Roughness"
                          value={draft.terrain.roughness}
                          onChange={(v) =>
                            mutate((s) => (s.terrain.roughness = v))
                          }
                          min={0}
                          max={2}
                          step={0.01}
                          unit="m"
                          disabled={attached}
                        />
                        <Field
                          label="Terrain seed"
                          value={draft.terrain.seed}
                          onChange={(v) =>
                            mutate((s) => (s.terrain.seed = Math.round(v)))
                          }
                          min={0}
                          step={1}
                          disabled={attached}
                        />
                      </div>
                      <div className="property-group">
                        <h3>
                          <SlidersHorizontal size={14} />
                          Physics solver
                        </h3>
                        <Field
                          label="Timestep"
                          value={draft.physics.timestep * 1000}
                          onChange={(v) =>
                            mutate((s) => (s.physics.timestep = v / 1000))
                          }
                          min={0.1}
                          max={20}
                          unit="ms"
                          disabled={attached}
                        />
                        <Field
                          label="Substeps"
                          value={draft.physics.substeps}
                          onChange={(v) =>
                            mutate((s) => (s.physics.substeps = Math.round(v)))
                          }
                          min={1}
                          max={100}
                          step={1}
                          disabled={attached}
                        />
                        <Field
                          label="Solver iterations"
                          value={draft.physics.iterations}
                          onChange={(v) =>
                            mutate(
                              (s) => (s.physics.iterations = Math.round(v)),
                            )
                          }
                          min={1}
                          max={500}
                          step={1}
                          disabled={attached}
                        />
                        <Field
                          label="Episode limit"
                          value={draft.max_episode_steps}
                          onChange={(v) =>
                            mutate((s) => (s.max_episode_steps = Math.round(v)))
                          }
                          min={1}
                          step={100}
                          disabled={attached}
                        />
                      </div>
                    </>
                  ) : (
                    <>
                      {selectedRobot && draft.robot.kind !== "none" ? (
                        <>
                          <div className="selection-title">
                            <div className="selection-icon">
                              <Box size={23} />
                            </div>
                            <div>
                              <h3>
                                {draft.robot.kind === "car"
                                  ? "Vehicle"
                                  : draft.robot.kind === "quadruped"
                                    ? "Quadruped"
                                    : "Aircraft"}
                              </h3>
                              <span>Articulated rigid body</span>
                            </div>
                          </div>
                          <div className="property-group">
                            <h3>Physical properties</h3>
                            <Field
                              label="Body mass"
                              value={draft.robot.mass}
                              min={0.01}
                              unit="kg"
                              disabled={attached}
                              onChange={(v) =>
                                mutate((s) => (s.robot.mass = v))
                              }
                            />
                            <Field
                              label="Actuator strength"
                              value={draft.robot.motor_strength}
                              min={0.01}
                              disabled={attached}
                              onChange={(v) =>
                                mutate((s) => (s.robot.motor_strength = v))
                              }
                            />
                            <VectorField
                              label="Spawn position"
                              value={draft.robot.position}
                              unit="m"
                              disabled={attached}
                              onChange={(v) =>
                                mutate((s) => (s.robot.position = v))
                              }
                            />
                            <VectorField
                              label="Spawn rotation"
                              value={draft.robot.rotation ?? [0, 0, 0]}
                              unit="rad"
                              disabled={attached}
                              onChange={(v) =>
                                mutate((s) => (s.robot.rotation = v))
                              }
                            />
                            <VectorField
                              label="Initial velocity"
                              value={draft.robot.velocity ?? [0, 0, 0]}
                              unit="m/s"
                              disabled={attached}
                              onChange={(v) =>
                                mutate((s) => (s.robot.velocity = v))
                              }
                            />
                            <VectorField
                              label="Initial angular velocity"
                              value={draft.robot.angular_velocity ?? [0, 0, 0]}
                              unit="rad/s"
                              disabled={attached}
                              onChange={(v) =>
                                mutate((s) => (s.robot.angular_velocity = v))
                              }
                            />
                          </div>
                          <div className="property-group">
                            <h3>Control interface</h3>
                            <div className="action-list">
                              {world?.description.action_names.map(
                                (name, i) => (
                                  <div key={name}>
                                    <span>{String(i).padStart(2, "0")}</span>
                                    <strong>{name}</strong>
                                    <em>−1 … 1</em>
                                  </div>
                                ),
                              )}
                            </div>
                            <p className="property-note">
                              The Run button uses a scripted demonstration.
                              Connect your own policy through the API.
                            </p>
                          </div>
                        </>
                      ) : object ? (
                        <>
                          <div className="selection-title">
                            <div className="selection-icon">
                              <Box size={23} />
                            </div>
                            <div>
                              <h3>{object.name}</h3>
                              <span>
                                {object.static ? "Static" : "Dynamic"}{" "}
                                {object.kind}
                              </span>
                            </div>
                          </div>
                          <div className="property-group">
                            <h3>Transform</h3>
                            <VectorField
                              label="Position"
                              value={object.position}
                              unit="m"
                              disabled={attached}
                              onChange={(v) =>
                                mutate(
                                  (s) =>
                                    (s.objects.find(
                                      (o) => o.name === selected,
                                    )!.position = v),
                                )
                              }
                            />
                            <VectorField
                              label="Rotation"
                              value={object.rotation}
                              unit="rad"
                              disabled={attached}
                              onChange={(v) =>
                                mutate(
                                  (s) =>
                                    (s.objects.find(
                                      (o) => o.name === selected,
                                    )!.rotation = v),
                                )
                              }
                            />
                            <VectorField
                              label="Dimensions (half-size)"
                              value={object.size}
                              unit="m"
                              disabled={attached}
                              onChange={(v) =>
                                mutate(
                                  (s) =>
                                    (s.objects.find(
                                      (o) => o.name === selected,
                                    )!.size = v),
                                )
                              }
                            />
                            <p className="property-note">
                              Boxes use half-extents. Sphere X is radius;
                              cylinder / capsule X is radius and Y is
                              half-length.
                            </p>
                          </div>
                          <div className="property-group">
                            <h3>Physical properties</h3>
                            <Field
                              label="Mass"
                              value={object.mass}
                              min={0.01}
                              unit="kg"
                              disabled={attached}
                              onChange={(v) =>
                                mutate(
                                  (s) =>
                                    (s.objects.find(
                                      (o) => o.name === selected,
                                    )!.mass = v),
                                )
                              }
                            />
                            <label className="checkbox-field">
                              <span>Static body</span>
                              <input
                                type="checkbox"
                                checked={object.static}
                                disabled={attached}
                                onChange={(e) =>
                                  mutate(
                                    (s) =>
                                      (s.objects.find(
                                        (o) => o.name === selected,
                                      )!.static = e.target.checked),
                                  )
                                }
                              />
                            </label>
                            <label className="field">
                              <span>Material color</span>
                              <input
                                aria-label="Material color"
                                type="color"
                                value={
                                  "#" +
                                  object.color
                                    .slice(0, 3)
                                    .map((v) =>
                                      Math.round(v * 255)
                                        .toString(16)
                                        .padStart(2, "0"),
                                    )
                                    .join("")
                                }
                                disabled={attached}
                                onChange={(e) => {
                                  const hex = e.target.value;
                                  mutate(
                                    (s) =>
                                      (s.objects.find(
                                        (o) => o.name === selected,
                                      )!.color = [
                                        parseInt(hex.slice(1, 3), 16) / 255,
                                        parseInt(hex.slice(3, 5), 16) / 255,
                                        parseInt(hex.slice(5, 7), 16) / 255,
                                        1,
                                      ]),
                                  );
                                }}
                              />
                            </label>
                          </div>
                          <button
                            className="delete-object"
                            disabled={attached}
                            onClick={async () => {
                              const next = clone(draft);
                              next.objects = next.objects.filter(
                                (o) => o.name !== selected,
                              );
                              setDraft(next);
                              await apply(next);
                              setSelected("robot");
                            }}
                          >
                            <Trash2 size={14} />
                            Remove object
                          </button>
                        </>
                      ) : (
                        <div className="inspector-empty">
                          <Box size={30} />
                          <h3>Select a scene object</h3>
                          <p>
                            Choose an object in the hierarchy or click it in the
                            viewport to edit its properties.
                          </p>
                          <button
                            className="button"
                            onClick={() => setModal("add")}
                            disabled={attached}
                          >
                            <Plus size={14} />
                            Add an object
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
              <div className="inspector-footer">
                <button
                  className={`button apply-button ${dirty ? "primary" : ""}`}
                  disabled={!dirty || busy || attached}
                  onClick={() => void apply()}
                >
                  {busy ? (
                    <LoaderCircle size={15} className="spin" />
                  ) : dirty ? (
                    <Check size={15} />
                  ) : (
                    <Check size={15} />
                  )}{" "}
                  {dirty ? "Apply changes & reset" : "All changes applied"}
                </button>
                <span>
                  {dirty
                    ? "Recompiles physics and resets the episode"
                    : "Parameters are stored in your scene JSON"}
                </span>
              </div>
            </aside>
          </main>
        </>
      )}
      <footer className="statusbar">
        <div>
          <span className={world ? "status-dot" : "idle-dot"} />
          {world ? "MuJoCo connected" : "Waiting for physics server"}
          <span className="footer-divider" />
          {attached ? "READ-ONLY SESSION" : "LOCAL WORKSPACE"}
        </div>
        <span>
          Physics simulation environment
          <span className="footer-divider" />
          KINETIC v0.1
        </span>
      </footer>
      {toast && (
        <div className="toast">
          <Check size={16} />
          {toast}
        </div>
      )}
      {modal === "add" && (
        <Modal title="Add to your world" onClose={() => setModal(null)}>
          <p className="modal-description">
            Add a physical primitive, then tune its transform and material in
            the inspector.
          </p>
          <div className="primitive-grid">
            {(["box", "sphere", "cylinder", "capsule"] as const).map((kind) => (
              <button key={kind} onClick={() => void addObject(kind)}>
                <div className={`primitive-preview ${kind}`} />
                <strong>{kind[0].toUpperCase() + kind.slice(1)}</strong>
                <span>Dynamic rigid body</span>
              </button>
            ))}
          </div>
        </Modal>
      )}
      {modal === "json" && (
        <Modal title="Portable scene JSON" onClose={() => setModal(null)} wide>
          <p className="modal-description">
            Edit a complete scene definition. The physics server validates every
            field before creating a new world.
          </p>
          <textarea
            className="json-editor"
            aria-label="Scene JSON"
            value={json}
            onChange={(e) => setJson(e.target.value)}
            spellCheck={false}
          />
          <div className="modal-actions">
            <a
              className="text-button"
              href="/api/v1/schema"
              target="_blank"
              rel="noreferrer"
            >
              View schema <ExternalLink size={13} />
            </a>
            <button
              className="button primary"
              disabled={busy || attached}
              onClick={() => void importScene(json)}
            >
              <Check size={15} />
              Create from JSON
            </button>
          </div>
        </Modal>
      )}
      {modal === "sessions" && (
        <Modal
          title="Active simulation sessions"
          onClose={() => setModal(null)}
        >
          <p className="modal-description">
            Attach a read-only viewer to a session controlled by your training
            process. Viewing never advances physics.
          </p>
          <div className="session-list">
            {sessions.map((item) => (
              <button
                key={item.id}
                onClick={() =>
                  void run(async () => {
                    adopt(await api<World>(`/worlds/${item.id}`), true);
                    setActiveTemplate("custom");
                    setTab("world");
                    setModal(null);
                  })
                }
              >
                <div className="session-icon">
                  <Radio size={20} />
                </div>
                <div>
                  <strong>{item.name}</strong>
                  <code>{item.id}</code>
                  <span>
                    {item.robot} · {item.time.toFixed(2)} s
                  </span>
                </div>
                <ArrowRight size={16} />
              </button>
            ))}
            {!sessions.length && (
              <p className="empty-copy">
                No active sessions yet. Create a world to get started.
              </p>
            )}
          </div>
        </Modal>
      )}
      {modal === "saved" && (
        <Modal title="Saved worlds" onClose={() => setModal(null)}>
          <p className="modal-description">
            Load a scene saved locally on this machine into a fresh simulation
            session.
          </p>
          <div className="session-list">
            {saved.map((item) => (
              <button
                key={item.filename}
                onClick={() => void importScene(JSON.stringify(item.scene))}
              >
                <div className="session-icon">
                  <Save size={20} />
                </div>
                <div>
                  <strong>{item.name}</strong>
                  <code>{item.filename}</code>
                </div>
                <ArrowRight size={16} />
              </button>
            ))}
            {!saved.length && (
              <p className="empty-copy">
                No saved worlds. Use Save world to keep your scene.
              </p>
            )}
          </div>
        </Modal>
      )}
      {modal === "help" && (
        <Modal title="Kinetic user guide" onClose={() => setModal(null)}>
          <p className="modal-description">
            Scene configuration, simulation controls, and reinforcement
            learning policy integration.
          </p>
          <div className="guide-list">
            <div>
              <span>01</span>
              <section>
                <h3>Select an environment</h3>
                <p>
                  Select a vehicle, quadruped, aircraft, or rigid-body scene.
                  Scene geometry and motion are provided by the MuJoCo engine.
                </p>
              </section>
            </div>
            <div>
              <span>02</span>
              <section>
                <h3>Configure the environment</h3>
                <p>
                  Edit gravity, friction, terrain and body properties. Apply
                  changes to compile the scene. Save or export reusable JSON.
                </p>
              </section>
            </div>
            <div>
              <span>03</span>
              <section>
                <h3>Connect a policy</h3>
                <p>
                  Run previews with the scripted controller. Open Policy integration for
                  a session-specific API example, or attach a read-only viewer
                  to training.
                </p>
              </section>
            </div>
          </div>
          <div className="scope-note">
            <Wind size={17} />
            <p>
              Fluid dynamics uses an independent educational 2D solver. Flight uses
              approximate aerodynamics. These environments are a research
              foundation, not validated engineering models.
            </p>
          </div>
        </Modal>
      )}
    </div>
  );
}
