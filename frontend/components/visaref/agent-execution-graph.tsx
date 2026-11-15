"use client";

/**
 * Agent execution graph: Obsidian-style 2D force-directed network.
 *
 * - Environment (nodes/edges) comes from GET /applications/{id}/execution-graph, which builds it
 *   from the checklist, the check registry, the extractors, the application files and config.
 * - Layout (d3-force, computed once per graph) is separate from playback (event cursor).
 * - Status (what happened) is separate from category/cluster (what the component is).
 * - Replay is driven by the recorded, timestamped execution events.
 */

import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type Simulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import { useQuery } from "@tanstack/react-query";
import { HugeiconsIcon } from "@hugeicons/react";
import {
  ArrowLeft01Icon,
  ArrowRight01Icon,
  Cancel01Icon,
  CenterFocusIcon,
  FullScreenIcon,
  Navigation03Icon,
  PauseIcon,
  PlayIcon,
  RepeatIcon,
} from "@hugeicons/core-free-icons";
import { motion, useReducedMotion } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchExecutionGraph,
  type ExecutionEvent,
  type ExecutionGraph,
  type ExecutionGraphNode,
  type GraphNodeStatus,
} from "@/lib/api";

type Props = {
  applicationId: string;
  applicantName?: string | null;
  onClose: () => void;
};

type DisplayStatus = GraphNodeStatus | "executing" | "queued";

type SimNode = SimulationNodeDatum & {
  id: string;
  r: number;
  cluster: string;
  node: ExecutionGraphNode;
};
type SimLink = SimulationLinkDatum<SimNode> & { kind: string; key: string };

type Layout = {
  nodes: SimNode[];
  byId: Map<string, SimNode>;
  links: SimLink[];
  sim: Simulation<SimNode, SimLink>;
  anchors: Map<string, { x: number; y: number }>;
};

type View = { x: number; y: number; k: number };

type Display = {
  status: Map<string, DisplayStatus>;
  lit: Map<string, "green" | "red" | "blue">;
  path: Set<string>;
  current: string | null;
};

/* ---------- palette (dark charcoal + app green, restrained accents) ---------- */
const BG = "#0c0f11";
const RGB: Record<DisplayStatus, [number, number, number]> = {
  completed: [74, 201, 140],
  attention: [240, 92, 92],
  awaiting: [244, 80, 80],
  error: [255, 120, 72],
  executing: [245, 196, 81],
  pending: [110, 146, 214],
  queued: [96, 122, 168],
  available: [120, 130, 134],
  disabled: [90, 98, 102],
  skipped: [150, 158, 161],
};
const STATUS_LABEL: Record<DisplayStatus, string> = {
  completed: "Executed",
  attention: "Needs attention",
  awaiting: "Awaiting human",
  error: "Error",
  executing: "Executing",
  pending: "Pending (after approval)",
  queued: "Not reached yet",
  available: "Available, unused",
  disabled: "Not configured",
  skipped: "Skipped",
};
const rgba = (c: [number, number, number], a: number) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;

const CLUSTER_ORDER = [
  "intake",
  "storage",
  "documents",
  "model",
  "extraction",
  "facts",
  "checks",
  "rules",
  "decision",
  "human",
  "delivery",
];

function hash01(s: string) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return ((h >>> 0) % 100000) / 100000;
}

const edgeKey = (a: string, b: string) => `${a}→${b}`;

/* ---------- layout: deterministic force simulation, run once ---------- */
function buildLayout(graph: ExecutionGraph): Layout {
  const anchors = new Map<string, { x: number; y: number }>();
  const present = CLUSTER_ORDER.filter((c) => graph.nodes.some((n) => n.cluster === c));
  present.forEach((c, i) => {
    const a = (i / present.length) * Math.PI * 2 - Math.PI * 0.62;
    const wobble = 0.82 + hash01(c) * 0.36;
    anchors.set(c, { x: Math.cos(a) * 560 * wobble, y: Math.sin(a) * 235 * wobble });
  });
  const nodes: SimNode[] = graph.nodes.map((n) => {
    const an = anchors.get(n.cluster) ?? { x: 0, y: 0 };
    const h = hash01(n.id);
    const h2 = hash01(n.id + "y");
    return {
      id: n.id,
      r: 1.6 + n.size * 2.3,
      cluster: n.cluster,
      node: n,
      x: an.x + (h - 0.5) * 120,
      y: an.y + (h2 - 0.5) * 120,
    };
  });
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const links: SimLink[] = graph.edges
    .filter((e) => byId.has(e.source) && byId.has(e.target))
    .map((e) => ({ source: e.source, target: e.target, kind: e.kind, key: edgeKey(e.source, e.target) }));
  const sim = forceSimulation<SimNode, SimLink>(nodes)
    .force(
      "link",
      forceLink<SimNode, SimLink>(links)
        .id((d) => d.id)
        .distance((l) => {
          const s = l.source as SimNode;
          const t = l.target as SimNode;
          const same = s.cluster === t.cluster;
          return (same ? 26 : 70) + s.r + t.r + (l.kind === "uses" ? 18 : 0);
        })
        .strength((l) => ((l.source as SimNode).cluster === (l.target as SimNode).cluster ? 0.55 : 0.08)),
    )
    .force("charge", forceManyBody<SimNode>().strength((d) => -26 - d.r * 7).distanceMax(420))
    .force("collide", forceCollide<SimNode>().radius((d) => d.r + 5).iterations(2))
    .force("x", forceX<SimNode>((d) => anchors.get(d.cluster)?.x ?? 0).strength(0.06))
    .force("y", forceY<SimNode>((d) => anchors.get(d.cluster)?.y ?? 0).strength(0.06))
    .stop();
  for (let i = 0; i < 420; i++) sim.tick();
  sim.alpha(0).alphaTarget(0);
  return { nodes, byId, links, sim, anchors };
}

/* ---------- playback → display statuses ---------- */
function eventStatus(ev: ExecutionEvent, humanDone: boolean): DisplayStatus {
  switch (ev.status) {
    case "error":
      return "error";
    case "skipped":
      return "skipped";
    case "awaiting":
      return "awaiting";
    case "failed":
    case "needs_human":
      return humanDone ? "completed" : "attention";
    default:
      return "completed";
  }
}

function computeDisplay(graph: ExecutionGraph, applied: number, inflight: number | null): Display {
  const events = graph.events;
  const n = events.length;
  const status = new Map<string, DisplayStatus>();
  const lit = new Map<string, "green" | "red" | "blue">();
  const path = new Set<string>();
  const finalState = applied >= n && inflight === null;
  const willRun = new Set(events.map((e) => e.node));
  let humanDone = false;
  for (let i = 0; i < Math.min(applied, n); i++) {
    if (events[i].node === "gate:human" && events[i].status === "resolved") humanDone = true;
  }
  for (const node of graph.nodes) {
    if (finalState) status.set(node.id, node.status);
    else if (willRun.has(node.id) || (node.status === "completed" && node.event_count === 0)) status.set(node.id, "queued");
    else status.set(node.id, node.status === "awaiting" ? "queued" : node.status);
  }
  for (let i = 0; i < Math.min(applied, n); i++) {
    const ev = events[i];
    if (!finalState) {
      status.set(ev.node, ev.status === "resolved" ? "completed" : eventStatus(ev, humanDone));
      for (const v of ev.via ?? []) if (status.get(v) === "queued") status.set(v, "completed");
    }
    path.add(ev.node);
    const red = ev.status === "awaiting" && !humanDone;
    if (ev.from) lit.set(edgeKey(ev.from, ev.node), red ? "red" : "green");
    for (const v of ev.via ?? []) lit.set(edgeKey(ev.node, v), "green");
  }
  if (finalState) {
    // completed-by-use capability nodes (via) are already completed server-side
    for (const node of graph.nodes) if (node.status === "pending") path.add(node.id);
  }
  // pending path after the human gate (blue, dim)
  if (finalState) {
    for (const e of graph.edges) {
      const s = status.get(e.source);
      const t = status.get(e.target);
      if ((s === "pending" || s === "awaiting") && t === "pending") lit.set(edgeKey(e.source, e.target), "blue");
    }
  }
  let current: string | null = null;
  if (inflight !== null && events[inflight]) {
    current = events[inflight].node;
    status.set(current, "executing");
  } else if (applied > 0) {
    current = events[Math.min(applied, n) - 1]?.node ?? null;
  }
  return { status, lit, path, current };
}

/* ---------- pacing: real durations, compressed so the replay reads like a video ---------- */
function displayDuration(ev: ExecutionEvent | undefined, speed: number) {
  if (!ev) return 300;
  const ms = ev.duration_ms ?? null;
  const base = ms === null ? 420 : 240 + Math.min(1100, 260 * Math.log10(1 + ms));
  return base / speed;
}

function fmtMs(ms: number | null | undefined) {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return "Unavailable";
  if (ms === 0) return "instant";
  if (ms < 1) return `${(ms * 1000).toFixed(0)} µs`;
  if (ms < 1000) return `${ms < 10 ? ms.toFixed(2) : ms.toFixed(0)} ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)} s`;
  const m = Math.floor(ms / 60000);
  return `${m} min ${Math.round((ms % 60000) / 1000)} s`;
}

function fmtTime(ts: string | null | undefined) {
  if (!ts) return "Unavailable";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "Unavailable";
  return `${d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })}.${String(d.getMilliseconds()).padStart(3, "0")}`;
}

/* quadratic curve control point (organic, stable per edge) */
function ctrl(ax: number, ay: number, bx: number, by: number, key: string) {
  const mx = (ax + bx) / 2;
  const my = (ay + by) / 2;
  const dx = bx - ax;
  const dy = by - ay;
  const bend = (hash01(key) - 0.5) * 0.36;
  return { cx: mx - dy * bend, cy: my + dx * bend };
}
function qpt(ax: number, ay: number, cx: number, cy: number, bx: number, by: number, t: number) {
  const u = 1 - t;
  return { x: u * u * ax + 2 * u * t * cx + t * t * bx, y: u * u * ay + 2 * u * t * cy + t * t * by };
}

/* ======================================================================= */

export default function AgentExecutionGraph({ applicationId, applicantName, onClose }: Props) {
  const query = useQuery({
    queryKey: ["execution-graph", applicationId],
    queryFn: () => fetchExecutionGraph(applicationId),
    staleTime: 0,
  });
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3 backdrop-blur-[2px] sm:p-5"
      role="dialog"
      aria-modal="true"
      aria-labelledby="agent-execution-graph-title"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <motion.section
        initial={reduceMotion ? false : { opacity: 0, scale: 0.985 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.28, ease: [0.2, 0, 0, 1] }}
        className="relative flex h-full max-h-[940px] w-full max-w-[1680px] flex-col overflow-hidden rounded-[12px] border border-white/[0.08] bg-[#0c0f11] text-[#e6ebec] shadow-[0_40px_120px_-40px_rgb(0_0_0/0.9)]"
      >
        {query.data ? (
          <GraphView
            graph={query.data}
            applicantName={applicantName ?? query.data.applicant_name}
            onClose={onClose}
            reduceMotion={Boolean(reduceMotion)}
          />
        ) : (
          <div className="flex flex-1 flex-col">
            <TopBar title={applicantName} onClose={onClose} />
            <div className="grid flex-1 place-items-center text-[13px] text-white/45">
              {query.isError ? `Could not load the execution graph: ${String(query.error?.message ?? "")}` : "Loading execution graph…"}
            </div>
          </div>
        )}
      </motion.section>
    </div>
  );
}

function TopBar({
  title,
  onClose,
  children,
}: {
  title?: string | null;
  onClose: () => void;
  children?: React.ReactNode;
}) {
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-white/[0.06] pr-2 pl-4">
      <h2 id="agent-execution-graph-title" className="flex min-w-0 items-baseline gap-2 text-[13px]/[18px] font-medium text-white/90">
        <span className="shrink-0">Execution graph</span>
        <span className="truncate font-normal text-white/45">{title || "Application"}</span>
      </h2>
      {children}
      <button
        type="button"
        onClick={onClose}
        aria-label="Close"
        className="ml-1 grid size-8 shrink-0 cursor-pointer place-items-center rounded-[7px] text-white/55 transition-colors hover:bg-white/[0.06] hover:text-white focus-visible:outline-2 focus-visible:outline-white/60"
      >
        <HugeiconsIcon icon={Cancel01Icon} size={16} strokeWidth={1.8} />
      </button>
    </header>
  );
}

const iconBtn =
  "inline-flex h-8 shrink-0 cursor-pointer items-center gap-1.5 rounded-[7px] px-2 text-[12px]/[16px] font-medium text-white/60 transition-colors hover:bg-white/[0.06] hover:text-white disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:bg-transparent focus-visible:outline-2 focus-visible:outline-white/60 aria-pressed:bg-white/[0.08] aria-pressed:text-white";

function GraphView({
  graph,
  applicantName,
  onClose,
  reduceMotion,
}: {
  graph: ExecutionGraph;
  applicantName?: string | null;
  onClose: () => void;
  reduceMotion: boolean;
}) {
  const events = graph.events;
  const N = events.length;
  const [cursor, setCursor] = useState(N); // events fully applied; N = final state (whole network)
  const [inflight, setInflight] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [follow, setFollow] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusId, setFocusId] = useState<string | null>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const layoutRef = useRef<Layout | null>(null);
  const viewRef = useRef<View>({ x: 0, y: 0, k: 1 });
  const targetViewRef = useRef<View | null>(null);
  const displayRef = useRef<Display | null>(null);
  const animRef = useRef<{ index: number; start: number; dur: number } | null>(null);
  const uiRef = useRef({ selectedId, focusId, hoverId, playing, follow, speed, cursor, reduceMotion });
  const branchRef = useRef<Set<string> | null>(null);
  const userMovedRef = useRef(0);

  const nodeById = useMemo(() => new Map(graph.nodes.map((n) => [n.id, n])), [graph]);
  const adjacency = useMemo(() => {
    const out = new Map<string, Set<string>>();
    const inc = new Map<string, Set<string>>();
    for (const e of graph.edges) {
      if (!out.has(e.source)) out.set(e.source, new Set());
      if (!inc.has(e.target)) inc.set(e.target, new Set());
      out.get(e.source)!.add(e.target);
      inc.get(e.target)!.add(e.source);
    }
    return { out, inc };
  }, [graph]);

  const display = useMemo(() => computeDisplay(graph, cursor, inflight), [graph, cursor, inflight]);

  const branch = useMemo(() => {
    if (!focusId) return null;
    const keep = new Set<string>([focusId]);
    const walk = (start: string, map: Map<string, Set<string>>, depth: number) => {
      let frontier = [start];
      for (let d = 0; d < depth; d++) {
        const next: string[] = [];
        for (const id of frontier) for (const m of map.get(id) ?? []) if (!keep.has(m)) { keep.add(m); next.push(m); }
        frontier = next;
      }
    };
    walk(focusId, adjacency.out, 2);
    walk(focusId, adjacency.inc, 2);
    return keep;
  }, [focusId, adjacency]);

  useEffect(() => {
    displayRef.current = display;
    branchRef.current = branch;
    uiRef.current = { selectedId, focusId, hoverId, playing, follow, speed, cursor, reduceMotion };
  });

  /* fit the camera to a set of nodes */
  const fitTo = useCallback((ids: Set<string> | null, animate = true) => {
    const layout = layoutRef.current;
    const wrap = wrapRef.current;
    if (!layout || !wrap) return;
    const pts = layout.nodes.filter((n) => !ids || ids.has(n.id));
    if (!pts.length) return;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const p of pts) {
      x0 = Math.min(x0, (p.x ?? 0) - p.r);
      y0 = Math.min(y0, (p.y ?? 0) - p.r);
      x1 = Math.max(x1, (p.x ?? 0) + p.r);
      y1 = Math.max(y1, (p.y ?? 0) + p.r);
    }
    const w = wrap.clientWidth;
    const h = wrap.clientHeight;
    const pad = 64;
    const k = Math.max(0.3, Math.min(2.2, Math.min((w - pad * 2) / (x1 - x0 || 1), (h - pad * 2 - 56) / (y1 - y0 || 1))));
    const v = { k, x: w / 2 - ((x0 + x1) / 2) * k, y: (h - 56) / 2 - ((y0 + y1) / 2) * k };
    if (animate) targetViewRef.current = v;
    else viewRef.current = v;
  }, []);

  /* layout once per graph (separate from playback) */
  useEffect(() => {
    const layout = buildLayout(graph);
    layoutRef.current = layout;
    fitTo(null, false);
    return () => {
      layout.sim.stop();
    };
  }, [graph, fitTo]);

  /* ----- playback engine ----- */
  const startEvent = useCallback(
    (index: number) => {
      if (index >= N) {
        setInflight(null);
        setPlaying(false);
        return;
      }
      animRef.current = {
        index,
        start: performance.now(),
        dur: uiRef.current.reduceMotion ? 1 : displayDuration(events[index], uiRef.current.speed),
      };
      setInflight(index);
      const layout = layoutRef.current;
      const target = layout?.byId.get(events[index].node);
      if (target && uiRef.current.follow && wrapRef.current && performance.now() - userMovedRef.current > 1500) {
        const v = viewRef.current;
        const k = Math.max(v.k, 1.25);
        const w = wrapRef.current.clientWidth;
        const h = wrapRef.current.clientHeight - 56;
        targetViewRef.current = { k, x: w / 2 - (target.x ?? 0) * k, y: h / 2 - (target.y ?? 0) * k };
      }
    },
    [N, events],
  );

  const finishEvent = useCallback(() => {
    const a = animRef.current;
    if (!a) return;
    animRef.current = null;
    const next = a.index + 1;
    setCursor(next);
    setInflight(null);
    const ev = events[a.index];
    const stopsHere = ev.node === "gate:human" && ev.status === "awaiting" && !events.slice(next).some((e) => e.node === "gate:human" && e.status === "resolved");
    if (!uiRef.current.playing || stopsHere || next >= N) {
      if (stopsHere || next >= N) setPlaying(false);
      return;
    }
    startEvent(next);
  }, [N, events, startEvent]);

  const play = useCallback(() => {
    const from = cursor >= N ? 0 : cursor;
    if (from === 0) setCursor(0);
    setSelectedId(null);
    setPlaying(true);
    uiRef.current.playing = true;
    startEvent(from);
  }, [N, cursor, startEvent]);

  const pause = useCallback(() => {
    setPlaying(false);
    uiRef.current.playing = false;
    if (animRef.current) {
      const idx = animRef.current.index;
      animRef.current = null;
      setInflight(null);
      setCursor(idx + 1);
    }
  }, []);

  const step = useCallback(
    (delta: number) => {
      pause();
      setCursor((c) => {
        const n = Math.max(0, Math.min(N, (animRef.current ? animRef.current.index + 1 : c) + delta));
        const ev = events[n - 1];
        const target = ev ? layoutRef.current?.byId.get(ev.node) : null;
        if (target && uiRef.current.follow && wrapRef.current) {
          const v = viewRef.current;
          const k = Math.max(v.k, 1.25);
          targetViewRef.current = {
            k,
            x: wrapRef.current.clientWidth / 2 - (target.x ?? 0) * k,
            y: (wrapRef.current.clientHeight - 56) / 2 - (target.y ?? 0) * k,
          };
        }
        return n;
      });
      setSelectedId(null);
    },
    [N, events, pause],
  );

  const replay = useCallback(() => {
    setCursor(0);
    setSelectedId(null);
    setPlaying(true);
    uiRef.current.playing = true;
    fitTo(null);
    window.setTimeout(() => startEvent(0), 450);
  }, [fitTo, startEvent]);

  const scrub = useCallback(
    (n: number) => {
      pause();
      setCursor(n);
    },
    [pause],
  );

  /* keyboard: space play/pause, arrows step */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      if (e.key === " ") {
        e.preventDefault();
        if (uiRef.current.playing) pause();
        else play();
      } else if (e.key === "ArrowRight") step(1);
      else if (e.key === "ArrowLeft") step(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pause, play, step]);

  /* ----- canvas render loop ----- */
  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    let raf = 0;
    let dpr = 1;
    const font = getComputedStyle(document.body).fontFamily || "ui-sans-serif, system-ui";

    const resize = () => {
      dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.round(wrap.clientWidth * dpr);
      canvas.height = Math.round(wrap.clientHeight * dpr);
      canvas.style.width = `${wrap.clientWidth}px`;
      canvas.style.height = `${wrap.clientHeight}px`;
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(wrap);

    const draw = (now: number) => {
      raf = requestAnimationFrame(draw);
      const layout = layoutRef.current;
      const disp = displayRef.current;
      if (!layout || !disp) return;
      const ui = uiRef.current;
      const still = ui.reduceMotion;
      const time = still ? 0 : now / 1000;

      // finish the in-flight event when its (real-duration based) slot elapses
      const a = animRef.current;
      let p = 1;
      if (a) {
        p = Math.min(1, (now - a.start) / a.dur);
        if (p >= 1) finishEvent();
      }
      // camera easing
      const tv = targetViewRef.current;
      if (tv) {
        const v = viewRef.current;
        const e = still ? 1 : 0.085;
        v.x += (tv.x - v.x) * e;
        v.y += (tv.y - v.y) * e;
        v.k += (tv.k - v.k) * e;
        if (Math.abs(tv.x - v.x) < 0.3 && Math.abs(tv.y - v.y) < 0.3 && Math.abs(tv.k - v.k) < 0.001) targetViewRef.current = null;
      }
      const v = viewRef.current;
      const W = canvas.width / dpr;
      const H = canvas.height / dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.fillStyle = BG;
      ctx.fillRect(0, 0, W, H);
      const vg = ctx.createRadialGradient(W * 0.5, H * 0.45, 0, W * 0.5, H * 0.45, Math.max(W, H) * 0.75);
      vg.addColorStop(0, "rgba(30,38,42,0.55)");
      vg.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = vg;
      ctx.fillRect(0, 0, W, H);

      ctx.setTransform(dpr * v.k, 0, 0, dpr * v.k, dpr * v.x, dpr * v.y);
      const branch = branchRef.current;
      const sel = ui.selectedId;
      const hov = ui.hoverId;
      const neigh = new Set<string>();
      const hl = hov ?? sel;
      if (hl) {
        neigh.add(hl);
        for (const l of layout.links) {
          const s = (l.source as SimNode).id;
          const t = (l.target as SimNode).id;
          if (s === hl) neigh.add(t);
          if (t === hl) neigh.add(s);
        }
      }
      const dim = (id: string) => (branch && !branch.has(id) ? 0.12 : 1);
      const inflightEv = a ? events[a.index] : null;
      const px = 1 / v.k;
      const approvedRun = graph.summary.state === "approved" && disp.status.get("gate:human") === "completed";

      // cluster captions (very faint)
      ctx.font = `500 ${10 * px}px ${font}`;
      ctx.textAlign = "center";
      const capBoxes: { x: number; y: number; w: number }[] = [];
      for (const c of layout.anchors.keys()) {
        const members = layout.nodes.filter((n) => n.cluster === c);
        if (!members.length) continue;
        let cx = 0, top = Infinity, minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
        for (const m of members) {
          cx += m.x ?? 0;
          top = Math.min(top, (m.y ?? 0) - m.r);
          minX = Math.min(minX, m.x ?? 0); maxX = Math.max(maxX, m.x ?? 0);
          minY = Math.min(minY, m.y ?? 0); maxY = Math.max(maxY, m.y ?? 0);
        }
        if (Math.hypot(maxX - minX, maxY - minY) > 360) continue; // scattered cluster: no caption
        cx /= members.length;
        const cap = graph.clusters[c]?.toUpperCase() ?? c;
        const cw = ctx.measureText(cap).width;
        const cy = top - 14 * px;
        if (capBoxes.some((bx) => Math.abs(bx.x - cx) < (bx.w + cw) / 2 + 8 * px && Math.abs(bx.y - cy) < 14 * px)) continue;
        capBoxes.push({ x: cx, y: cy, w: cw });
        ctx.fillStyle = `rgba(200,210,214,${0.16 * (branch ? 0.4 : 1)})`;
        ctx.fillText(cap, cx, cy);
      }

      // edges
      for (const l of layout.links) {
        const s = l.source as SimNode;
        const t = l.target as SimNode;
        const ax = s.x ?? 0, ay = s.y ?? 0, bx = t.x ?? 0, by = t.y ?? 0;
        const { cx, cy } = ctrl(ax, ay, bx, by, l.key);
        const litC = disp.lit.get(l.key);
        const isInflight = inflightEv && inflightEv.from === s.id && inflightEv.node === t.id;
        const fade = Math.min(dim(s.id), dim(t.id));
        const near = hl && neigh.has(s.id) && neigh.has(t.id) && (s.id === hl || t.id === hl);
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.quadraticCurveTo(cx, cy, bx, by);
        if (litC && !isInflight) {
          const col = litC === "red" ? RGB.awaiting : litC === "blue" ? RGB.pending : RGB.completed;
          const gatePath = approvedRun && (t.node.cluster === "human" || t.node.cluster === "delivery" || s.node.cluster === "human");
          const strong = litC === "red" || gatePath ? 0.8 : litC === "blue" ? 0.35 : l.kind === "uses" ? 0.22 : 0.42;
          ctx.strokeStyle = rgba(col, strong * fade * (near ? 1.4 : 1));
          ctx.lineWidth = (litC === "red" || gatePath ? 1.6 : l.kind === "uses" ? 0.7 : 1.1) * px;
          if (litC === "blue") ctx.setLineDash([3 * px, 4 * px]);
        } else {
          ctx.strokeStyle = `rgba(170,182,186,${(near ? 0.35 : 0.075) * fade})`;
          ctx.lineWidth = (near ? 0.9 : 0.6) * px;
        }
        ctx.stroke();
        ctx.setLineDash([]);

        // progressive illumination + impulse on the in-flight connection
        if (isInflight) {
          const steps = 24;
          ctx.beginPath();
          for (let i = 0; i <= steps; i++) {
            const q = qpt(ax, ay, cx, cy, bx, by, (i / steps) * p);
            if (i === 0) ctx.moveTo(q.x, q.y);
            else ctx.lineTo(q.x, q.y);
          }
          ctx.strokeStyle = rgba(RGB.executing, 0.85);
          ctx.lineWidth = 1.6 * px;
          ctx.stroke();
          const head = qpt(ax, ay, cx, cy, bx, by, p);
          const g = ctx.createRadialGradient(head.x, head.y, 0, head.x, head.y, 9 * px);
          g.addColorStop(0, "rgba(255,240,200,0.95)");
          g.addColorStop(0.35, rgba(RGB.executing, 0.5));
          g.addColorStop(1, rgba(RGB.executing, 0));
          ctx.fillStyle = g;
          ctx.beginPath();
          ctx.arc(head.x, head.y, 9 * px, 0, Math.PI * 2);
          ctx.fill();
        } else if (litC && !still && l.kind !== "uses" && fade > 0.5) {
          // ambient impulses along executed pathways (restrained)
          const speedK = litC === "red" ? 0.55 : 0.22;
          const ph = (time * speedK + hash01(l.key)) % 1;
          const q = qpt(ax, ay, cx, cy, bx, by, ph);
          const col = litC === "red" ? RGB.awaiting : litC === "blue" ? RGB.pending : RGB.completed;
          const rr = (litC === "red" ? 3.2 : 2.2) * px;
          const g = ctx.createRadialGradient(q.x, q.y, 0, q.x, q.y, rr * 2.4);
          g.addColorStop(0, rgba([235, 255, 245], litC === "red" ? 0.9 : 0.55));
          g.addColorStop(0.4, rgba(col, 0.35));
          g.addColorStop(1, rgba(col, 0));
          ctx.fillStyle = g;
          ctx.beginPath();
          ctx.arc(q.x, q.y, rr * 2.4, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      // nodes
      const showAllLabels = v.k > 1.6;
      const labels: { x: number; y: number; text: string; strong: boolean; pri: number; dimText: boolean }[] = [];
      for (const n of layout.nodes) {
        const st = disp.status.get(n.id) ?? "available";
        const col = RGB[st];
        const x = n.x ?? 0;
        const y = n.y ?? 0;
        const fade = dim(n.id);
        const isSel = sel === n.id;
        const isHov = hov === n.id;
        const isCur = disp.current === n.id;
        let r = n.r;
        let glow = 0;
        let alpha = 1;
        switch (st) {
          case "completed":
            glow = n.node.kind === "gate" || n.id === disp.current ? 0.55 : 0.18;
            break;
          case "awaiting": {
            const b = still ? 0.5 : 0.5 + 0.5 * Math.sin(time * 2.6);
            glow = 0.55 + 0.45 * b;
            r = n.r * (1 + 0.06 * b);
            break;
          }
          case "attention":
            glow = 0.28;
            break;
          case "executing":
            glow = 0.75 + (still ? 0 : 0.2 * Math.sin(time * 9));
            break;
          case "error":
            glow = 0.6;
            break;
          case "pending":
            alpha = 0.6;
            break;
          case "queued":
            alpha = 0.42;
            break;
          case "available":
            alpha = 0.32;
            break;
          case "disabled":
            alpha = 0.22;
            break;
          case "skipped":
            alpha = 0.55;
            break;
        }
        if (approvedRun && st === "completed" && n.node.kind === "gate") {
          const b = still ? 0.5 : 0.5 + 0.5 * Math.sin(time * 1.6);
          glow = 0.85 + 0.25 * b;
          r = n.r * 1.3;
        }
        alpha *= fade;
        if (glow > 0 && fade > 0.5) {
          const gr = r * (2.4 + glow * 1.6);
          const g = ctx.createRadialGradient(x, y, r * 0.6, x, y, gr);
          g.addColorStop(0, rgba(col, 0.32 * glow));
          g.addColorStop(1, rgba(col, 0));
          ctx.fillStyle = g;
          ctx.beginPath();
          ctx.arc(x, y, gr, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        if (st === "disabled") {
          ctx.setLineDash([2 * px, 2.5 * px]);
          ctx.strokeStyle = rgba(col, 0.6 * fade);
          ctx.lineWidth = 1 * px;
          ctx.stroke();
          ctx.setLineDash([]);
        } else if (st === "skipped") {
          ctx.fillStyle = BG;
          ctx.fill();
          ctx.strokeStyle = rgba(col, alpha);
          ctx.lineWidth = 1.2 * px;
          ctx.stroke();
          ctx.beginPath();
          ctx.moveTo(x - r * 0.55, y + r * 0.55);
          ctx.lineTo(x + r * 0.55, y - r * 0.55);
          ctx.stroke();
        } else if (st === "pending" || st === "queued") {
          ctx.fillStyle = rgba(col, alpha * 0.35);
          ctx.fill();
          ctx.strokeStyle = rgba(col, alpha);
          ctx.lineWidth = 1 * px;
          ctx.stroke();
        } else {
          ctx.fillStyle = rgba(col, alpha * (st === "available" ? 1 : 0.95));
          ctx.fill();
        }
        if (n.node.warning && st === "completed") {
          ctx.beginPath();
          ctx.arc(x + r * 0.78, y - r * 0.78, Math.max(1.6 * px, r * 0.28), 0, Math.PI * 2);
          ctx.fillStyle = rgba(RGB.executing, 0.9 * fade);
          ctx.fill();
        }
        if (isSel || isHov || isCur) {
          ctx.beginPath();
          ctx.arc(x, y, r + 3.5 * px, 0, Math.PI * 2);
          ctx.strokeStyle = isSel ? "rgba(255,255,255,0.85)" : isCur ? rgba(col, 0.75) : "rgba(255,255,255,0.4)";
          ctx.lineWidth = 1.2 * px;
          ctx.stroke();
        }
        const important = n.node.size >= 2.3 || st === "awaiting" || st === "attention" || st === "executing" || st === "error";
        if (fade > 0.5 && (showAllLabels || important || isSel || isHov || isCur || (hl && neigh.has(n.id)))) {
          const strong = isSel || isHov || isCur || st === "awaiting" || st === "executing";
          labels.push({
            x, y: y + r + 12 * px, text: n.node.label, strong,
            pri: (isSel || isHov ? 100 : 0) + (isCur ? 90 : 0) + (st === "awaiting" ? 80 : 0) + (st === "executing" ? 70 : 0) + n.node.size * 5,
            dimText: st === "available" || st === "disabled" || st === "queued",
          });
        }
      }
      // labels: small, Obsidian-like; greedy collision avoidance in screen space
      labels.sort((p1, p2) => p2.pri - p1.pri);
      const taken: { x0: number; y0: number; x1: number; y1: number }[] = [];
      ctx.textAlign = "center";
      for (const lb of labels) {
        ctx.font = `${lb.strong ? 500 : 400} ${11 * px}px ${font}`;
        const w = ctx.measureText(lb.text).width * v.k;
        const sx = lb.x * v.k + v.x;
        const sy = lb.y * v.k + v.y;
        const rect = { x0: sx - w / 2 - 3, y0: sy - 10, x1: sx + w / 2 + 3, y1: sy + 3 };
        if (!lb.strong && taken.some((t) => rect.x0 < t.x1 && rect.x1 > t.x0 && rect.y0 < t.y1 && rect.y1 > t.y0)) continue;
        taken.push(rect);
        ctx.fillStyle = lb.strong ? "rgba(240,244,245,0.95)" : `rgba(205,214,217,${lb.dimText ? 0.38 : 0.6})`;
        ctx.fillText(lb.text, lb.x, lb.y);
      }
    };
    raf = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [graph, events, finishEvent]);

  /* ----- pointer: pan, zoom, drag nodes, select ----- */
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let mode: "none" | "pan" | "node" = "none";
    let dragNode: SimNode | null = null;
    let sx = 0, sy = 0, moved = 0;
    const toWorld = (ex: number, ey: number) => {
      const rect = canvas.getBoundingClientRect();
      const v = viewRef.current;
      return { x: (ex - rect.left - v.x) / v.k, y: (ey - rect.top - v.y) / v.k };
    };
    const hit = (ex: number, ey: number) => {
      const layout = layoutRef.current;
      if (!layout) return null;
      const w = toWorld(ex, ey);
      let best: SimNode | null = null;
      let bd = Infinity;
      for (const n of layout.nodes) {
        const d = Math.hypot((n.x ?? 0) - w.x, (n.y ?? 0) - w.y);
        if (d < n.r + 5 / viewRef.current.k && d < bd) { best = n; bd = d; }
      }
      return best;
    };
    const down = (e: PointerEvent) => {
      canvas.setPointerCapture(e.pointerId);
      sx = e.clientX; sy = e.clientY; moved = 0;
      const n = hit(e.clientX, e.clientY);
      targetViewRef.current = null;
      if (n) {
        mode = "node";
        dragNode = n;
      } else mode = "pan";
    };
    const move = (e: PointerEvent) => {
      if (mode === "none") {
        const n = hit(e.clientX, e.clientY);
        const id = n?.id ?? null;
        if (id !== uiRef.current.hoverId) setHoverId(id);
        canvas.style.cursor = n ? "pointer" : "grab";
        return;
      }
      const dx = e.clientX - sx, dy = e.clientY - sy;
      moved = Math.max(moved, Math.hypot(dx, dy));
      if (mode === "pan") {
        const v = viewRef.current;
        v.x += e.movementX; v.y += e.movementY;
        canvas.style.cursor = "grabbing";
        userMovedRef.current = performance.now();
      } else if (mode === "node" && dragNode && moved > 3) {
        const layout = layoutRef.current;
        const w = toWorld(e.clientX, e.clientY);
        dragNode.fx = w.x; dragNode.fy = w.y;
        layout?.sim.alphaTarget(0.12).restart();
        userMovedRef.current = performance.now();
      }
    };
    const up = (e: PointerEvent) => {
      if (mode === "node" && dragNode) {
        if (moved <= 3) {
          setSelectedId(dragNode.id);
          if (uiRef.current.playing) {
            setPlaying(false);
            uiRef.current.playing = false;
          }
        }
        dragNode.fx = null; dragNode.fy = null;
        layoutRef.current?.sim.alphaTarget(0);
        window.setTimeout(() => layoutRef.current?.sim.stop(), 1200);
      } else if (mode === "pan" && moved <= 3) {
        setSelectedId(null);
      }
      mode = "none"; dragNode = null;
      canvas.releasePointerCapture(e.pointerId);
      canvas.style.cursor = "grab";
    };
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      targetViewRef.current = null;
      userMovedRef.current = performance.now();
      const rect = canvas.getBoundingClientRect();
      const v = viewRef.current;
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      const k = Math.max(0.25, Math.min(5, v.k * Math.exp(-e.deltaY * 0.0015)));
      v.x = mx - ((mx - v.x) / v.k) * k;
      v.y = my - ((my - v.y) / v.k) * k;
      v.k = k;
    };
    const dbl = (e: MouseEvent) => {
      const n = hit(e.clientX, e.clientY);
      if (n) { setSelectedId(n.id); setFocusId(n.id); }
    };
    const leave = () => setHoverId(null);
    canvas.addEventListener("pointerdown", down);
    canvas.addEventListener("pointermove", move);
    canvas.addEventListener("pointerup", up);
    canvas.addEventListener("pointerleave", leave);
    canvas.addEventListener("wheel", wheel, { passive: false });
    canvas.addEventListener("dblclick", dbl);
    return () => {
      canvas.removeEventListener("pointerdown", down);
      canvas.removeEventListener("pointermove", move);
      canvas.removeEventListener("pointerup", up);
      canvas.removeEventListener("pointerleave", leave);
      canvas.removeEventListener("wheel", wheel);
      canvas.removeEventListener("dblclick", dbl);
    };
  }, []);

  /* re-fit when focus changes */
  useEffect(() => {
    fitTo(branch);
  }, [branch, fitTo]);

  /* ----- derived UI data ----- */
  const activeIndex = inflight ?? (cursor > 0 ? cursor - 1 : null);
  const activeEvent = activeIndex !== null ? events[activeIndex] : null;
  const panelNodeId = selectedId ?? (playing || cursor < N ? activeEvent?.node ?? null : null);
  const panelNode = panelNodeId ? nodeById.get(panelNodeId) ?? null : null;
  const s = graph.summary;
  const tone = s.state === "approved" || s.state === "sent_back" ? "green" : s.state === "not_run" ? "grey" : "red";
  const elapsed = activeEvent && activeEvent.offset_ms != null ? activeEvent.offset_ms + (activeEvent.duration_ms ?? 0) : null;
  const counts = useMemo(() => {
    const c: Partial<Record<GraphNodeStatus, number>> = {};
    for (const n of graph.nodes) c[n.status] = (c[n.status] ?? 0) + 1;
    return c;
  }, [graph]);

  return (
    <>
      <TopBar title={applicantName} onClose={onClose}>
        <span
          className={`inline-flex h-6 shrink-0 items-center gap-1.5 rounded-full px-2 text-[12px]/[16px] font-medium ${
            tone === "green"
              ? "bg-[rgb(74_201_140/0.12)] text-[rgb(120_222_172)]"
              : tone === "red"
                ? "bg-[rgb(240_92_92/0.12)] text-[rgb(255_140_140)]"
                : "bg-white/[0.06] text-white/60"
          }`}
        >
          <span className={`size-1.5 rounded-full ${tone === "green" ? "bg-[rgb(74_201_140)]" : tone === "red" ? "bg-[rgb(244_80_80)]" : "bg-white/50"}`} />
          {s.title}
        </span>
        <span className="hidden truncate text-[12px]/[16px] text-white/35 tabular-nums lg:inline">
          {graph.nodes.length} components · {graph.edges.length} links · {N} events
        </span>
        <div className="ml-auto flex items-center gap-0.5">
          <button
            type="button"
            className={iconBtn}
            disabled={!selectedId && !focusId}
            aria-pressed={Boolean(focusId)}
            onClick={() => setFocusId(focusId ? null : selectedId)}
            title="Show only the selected node's branch (double-click a node)"
          >
            <HugeiconsIcon icon={CenterFocusIcon} size={15} strokeWidth={1.8} />
            {focusId ? "Clear focus" : "Focus branch"}
          </button>
          <button type="button" className={iconBtn} onClick={() => { setFocusId(null); fitTo(null); }} title="Reset view">
            <HugeiconsIcon icon={FullScreenIcon} size={15} strokeWidth={1.8} />
            Reset view
          </button>
          <button
            type="button"
            className={iconBtn}
            aria-pressed={follow}
            onClick={() => setFollow((f) => !f)}
            title="Camera follows the active node during replay"
          >
            <HugeiconsIcon icon={Navigation03Icon} size={15} strokeWidth={1.8} />
            Follow
          </button>
        </div>
      </TopBar>

      <div className="flex min-h-0 flex-1">
        <div ref={wrapRef} className="relative min-w-0 flex-1 overflow-hidden">
          <canvas ref={canvasRef} className="absolute inset-0 block cursor-grab touch-none" aria-label="Agent execution network" />

          <Legend counts={counts} />

          {/* playback */}
          <div className="absolute inset-x-3 bottom-3 flex h-11 items-center gap-1 rounded-[10px] border border-white/[0.07] bg-[#111518]/90 px-1.5 backdrop-blur-md">
            <button type="button" className={iconBtn} onClick={() => step(-1)} disabled={cursor === 0 && inflight === null} aria-label="Previous step" title="Previous step (←)">
              <HugeiconsIcon icon={ArrowLeft01Icon} size={15} strokeWidth={1.8} />
            </button>
            <button
              type="button"
              onClick={() => (playing ? pause() : play())}
              className="inline-flex h-8 w-[84px] shrink-0 cursor-pointer items-center justify-center gap-1.5 rounded-[7px] bg-white/[0.92] text-[12px]/[16px] font-medium text-[#0c0f11] transition-colors hover:bg-white focus-visible:outline-2 focus-visible:outline-white/60"
              aria-label={playing ? "Pause" : "Play"}
            >
              <HugeiconsIcon icon={playing ? PauseIcon : PlayIcon} size={14} strokeWidth={2} />
              {playing ? "Pause" : cursor >= N ? "Play" : "Resume"}
            </button>
            <button type="button" className={iconBtn} onClick={() => step(1)} disabled={cursor >= N} aria-label="Next step" title="Next step (→)">
              <HugeiconsIcon icon={ArrowRight01Icon} size={15} strokeWidth={1.8} />
            </button>
            <button type="button" className={iconBtn} onClick={replay} aria-label="Replay" title="Replay from the first event">
              <HugeiconsIcon icon={RepeatIcon} size={15} strokeWidth={1.8} />
            </button>
            <div className="mx-2 flex min-w-0 flex-1 flex-col justify-center gap-1">
              <div className="flex min-w-0 items-baseline gap-2 text-[12px]/[14px]">
                <span className="shrink-0 text-white/40 tabular-nums">
                  {activeIndex !== null ? activeIndex + 1 : 0}/{N}
                </span>
                <span className="min-w-0 truncate font-medium text-white/85">
                  {activeEvent ? nodeById.get(activeEvent.node)?.label ?? activeEvent.node : "Whole network"}
                </span>
                {activeEvent ? (
                  <span className="shrink-0 text-white/40 tabular-nums">{fmtMs(activeEvent.duration_ms)}</span>
                ) : null}
              </div>
              <Timeline events={events} cursor={cursor} inflight={inflight} onScrub={scrub} resolved={s.state === "approved"} />
            </div>
            <span className="hidden shrink-0 text-right text-[12px]/[14px] text-white/45 tabular-nums md:block">
              {s.timing_available ? (
                <>
                  T+{fmtMs(elapsed ?? s.total_ms)}
                  <span className="text-white/25"> / {fmtMs(s.total_ms)}</span>
                </>
              ) : (
                "Timing not recorded"
              )}
            </span>
            <div className="ml-2 flex shrink-0 items-center rounded-[7px] bg-white/[0.04] p-0.5" role="group" aria-label="Playback speed">
              {[0.5, 1, 2, 4].map((v) => (
                <button
                  key={v}
                  type="button"
                  aria-pressed={speed === v}
                  onClick={() => setSpeed(v)}
                  className="h-7 min-w-[34px] cursor-pointer rounded-[5px] px-1.5 text-[12px]/[16px] text-white/45 tabular-nums transition-colors hover:text-white aria-pressed:bg-white/[0.1] aria-pressed:text-white"
                >
                  {v}×
                </button>
              ))}
            </div>
          </div>
        </div>

        <aside className="hidden w-[360px] shrink-0 flex-col border-l border-white/[0.06] bg-[#0e1214] md:flex">
          {panelNode ? (
            <NodePanel
              key={panelNode.id}
              graph={graph}
              node={panelNode}
              status={display.status.get(panelNode.id) ?? panelNode.status}
              nodeById={nodeById}
              adjacency={adjacency}
              focusEvent={activeEvent && activeEvent.node === panelNode.id ? activeEvent : null}
              onSelect={(id) => setSelectedId(id)}
              onClear={selectedId ? () => setSelectedId(null) : undefined}
            />
          ) : (
            <SummaryPanel graph={graph} onSelect={(id) => setSelectedId(id)} />
          )}
        </aside>
      </div>
    </>
  );
}

/* ---------- small pieces ---------- */

function Timeline({
  events,
  cursor,
  inflight,
  onScrub,
  resolved,
}: {
  events: ExecutionEvent[];
  cursor: number;
  inflight: number | null;
  onScrub: (n: number) => void;
  resolved: boolean;
}) {
  const N = events.length;
  const pos = inflight !== null ? inflight + 0.5 : cursor;
  return (
    <div className="relative h-3">
      <div className="absolute inset-x-0 top-1/2 flex h-[3px] -translate-y-1/2 gap-px overflow-hidden rounded-full">
        {events.map((e, i) => (
          <span
            key={e.id}
            className="h-full flex-1"
            style={{
              background:
                i < cursor
                  ? e.status === "awaiting"
                    ? "rgb(244 80 80)"
                    : e.status === "failed" || e.status === "needs_human"
                      ? resolved
                        ? "rgb(245 196 81 / 0.8)"
                        : "rgb(240 92 92 / 0.75)"
                      : e.status === "skipped"
                        ? "rgb(150 158 161 / 0.6)"
                        : "rgb(74 201 140 / 0.85)"
                  : i === inflight
                    ? "rgb(245 196 81)"
                    : "rgb(255 255 255 / 0.09)",
            }}
          />
        ))}
      </div>
      <input
        type="range"
        min={0}
        max={N}
        step={1}
        value={Math.round(pos)}
        onChange={(e) => onScrub(Number(e.target.value))}
        aria-label="Execution progress"
        className="absolute inset-0 h-3 w-full cursor-pointer appearance-none bg-transparent opacity-0"
      />
    </div>
  );
}

function Legend({ counts }: { counts: Partial<Record<GraphNodeStatus, number>> }) {
  const items: [DisplayStatus, string][] = [
    ["completed", "Executed"],
    ["executing", "Executing"],
    ["awaiting", "Human intervention"],
    ["attention", "Flagged check"],
    ["pending", "Pending"],
    ["skipped", "Skipped"],
    ["available", "Available"],
    ["disabled", "Not configured"],
  ];
  return (
    <div className="pointer-events-none absolute top-3 left-3 flex flex-col gap-1 rounded-[8px] bg-[#0c0f11]/70 px-2.5 py-2 text-[11px]/[14px] text-white/50 backdrop-blur-sm">
      {items.map(([st, label]) => (
        <span key={st} className="inline-flex items-center gap-2">
          <Dot status={st} />
          <span>{label}</span>
          {st !== "executing" && counts[st as GraphNodeStatus] ? (
            <span className="text-white/25 tabular-nums">{counts[st as GraphNodeStatus]}</span>
          ) : null}
        </span>
      ))}
    </div>
  );
}

function Dot({ status }: { status: DisplayStatus }) {
  const c = RGB[status];
  if (status === "disabled")
    return <span className="size-2 rounded-full border border-dashed" style={{ borderColor: rgba(c, 0.7) }} />;
  if (status === "skipped")
    return <span className="size-2 rounded-full border" style={{ borderColor: rgba(c, 0.8) }} />;
  if (status === "pending" || status === "queued")
    return <span className="size-2 rounded-full border" style={{ borderColor: rgba(c, 0.9), background: rgba(c, 0.3) }} />;
  return (
    <span
      className="size-2 rounded-full"
      style={{ background: rgba(c, status === "available" ? 0.45 : 1), boxShadow: status === "awaiting" || status === "executing" ? `0 0 6px ${rgba(c, 0.8)}` : undefined }}
    />
  );
}

/* ---------- side panels ---------- */

const U = "Unavailable";

function fmtVal(v: unknown): string {
  if (v === null || v === undefined || v === "") return U;
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
  if (typeof v === "string") return v;
  if (Array.isArray(v)) {
    if (!v.length) return "none";
    if (v.every((x) => typeof x !== "object" || x === null)) return v.map((x) => String(x)).join(", ");
    return `${v.length} item${v.length === 1 ? "" : "s"}`;
  }
  return Object.entries(v as Record<string, unknown>)
    .map(([k, x]) => `${k}: ${typeof x === "object" && x !== null ? JSON.stringify(x) : String(x)}`)
    .join(" · ");
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-white/[0.06] px-4 py-3">
      <h4 className="mb-2 text-[11px]/[14px] font-medium tracking-[0.04em] text-white/35 uppercase">{title}</h4>
      <div className="space-y-1.5">{children}</div>
    </section>
  );
}

function Row({ k, v, mono }: { k: string; v: unknown; mono?: boolean }) {
  const text = fmtVal(v);
  const missing = text === U;
  return (
    <div className="grid grid-cols-[112px_1fr] gap-3 text-[12px]/[17px]">
      <span className="text-white/40">{k}</span>
      <span className={`min-w-0 break-words ${missing ? "text-white/25" : "text-white/80"} ${mono && !missing ? "font-mono text-[11.5px]" : ""}`}>
        {text}
      </span>
    </div>
  );
}

function KVs({ obj, skip = [] }: { obj?: Record<string, unknown>; skip?: string[] }) {
  const entries = Object.entries(obj ?? {}).filter(([k]) => !skip.includes(k) && !k.startsWith("_"));
  if (!entries.length) return <Row k="Data" v={null} />;
  return (
    <>
      {entries.map(([k, v]) => (
        <Row key={k} k={k.replace(/_/g, " ")} v={v} mono={typeof v !== "boolean"} />
      ))}
    </>
  );
}

function Chips({ ids, nodeById, onSelect }: { ids: string[]; nodeById: Map<string, ExecutionGraphNode>; onSelect: (id: string) => void }) {
  if (!ids.length) return <span className="text-[12px] text-white/25">None</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {ids.slice(0, 24).map((id) => {
        const n = nodeById.get(id);
        const st = n?.status ?? "available";
        return (
          <button
            key={id}
            type="button"
            onClick={() => onSelect(id)}
            className="inline-flex h-6 cursor-pointer items-center gap-1.5 rounded-[6px] bg-white/[0.04] px-1.5 text-[11.5px]/[16px] text-white/70 transition-colors hover:bg-white/[0.09] hover:text-white"
          >
            <Dot status={st} />
            {n?.label ?? id}
          </button>
        );
      })}
      {ids.length > 24 ? <span className="text-[11px] text-white/30">+{ids.length - 24}</span> : null}
    </div>
  );
}

function NodePanel({
  graph,
  node,
  status,
  nodeById,
  adjacency,
  focusEvent,
  onSelect,
  onClear,
}: {
  graph: ExecutionGraph;
  node: ExecutionGraphNode;
  status: DisplayStatus;
  nodeById: Map<string, ExecutionGraphNode>;
  adjacency: { out: Map<string, Set<string>>; inc: Map<string, Set<string>> };
  focusEvent: ExecutionEvent | null;
  onSelect: (id: string) => void;
  onClear?: () => void;
}) {
  const evs = graph.events.filter((e) => e.node === node.id);
  const ev = focusEvent ?? evs[evs.length - 1] ?? null;
  const usedBy = graph.events.filter((e) => (e.via ?? []).includes(node.id));
  const outputs = (ev?.outputs ?? {}) as Record<string, unknown>;
  const timings = outputs.timings_ms as Record<string, unknown> | undefined;
  const data = node.data ?? {};
  const result = data.result as { status?: string; message?: string; evidence?: Array<Record<string, unknown>> } | undefined;
  const ruleChildren = [...(adjacency.out.get(node.id) ?? [])].filter((id) => id.startsWith("rule:"));
  const ruleStats = ruleChildren.reduce(
    (acc, id) => {
      const r = (nodeById.get(id)?.data?.result as { status?: string } | undefined)?.status;
      if (r === "PASS") acc.pass++;
      else if (r === "FAIL") acc.fail++;
      else if (r === "NEEDS_HUMAN") acc.warn++;
      return acc;
    },
    { pass: 0, fail: 0, warn: 0 },
  );
  const endpoint = node.component && /^(GET|POST|PUT|DELETE) /.test(node.component) ? node.component : null;
  const evidence = (result?.evidence ?? (outputs.evidence as Array<Record<string, unknown>> | undefined)) ?? [];
  const c = RGB[status];

  return (
    <motion.div
      initial={{ opacity: 0, x: 6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2, ease: [0.2, 0, 0, 1] }}
      className="flex min-h-0 flex-1 flex-col overflow-y-auto"
    >
      <div className="px-4 pt-4 pb-3">
        <div className="flex items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11.5px]/[16px] font-medium" style={{ background: rgba(c, 0.12), color: rgba(c, 1) }}>
            <Dot status={status} />
            {STATUS_LABEL[status]}
            {node.warning ? " · with warnings" : ""}
          </span>
          {onClear ? (
            <button type="button" onClick={onClear} className="cursor-pointer text-[12px] text-white/40 hover:text-white">
              Back to run
            </button>
          ) : null}
        </div>
        <h3 className="mt-2.5 text-[16px]/[22px] font-semibold tracking-[-0.01em] break-words text-white">{node.label}</h3>
        <p className="mt-0.5 text-[12px]/[17px] text-white/45">
          {node.category}
          {node.description ? ` · ${node.description}` : ""}
        </p>
      </div>

      <Section title="General">
        <Row k="Component" v={node.component} mono />
        <Row k="Category" v={node.category} />
        <Row k="Status" v={STATUS_LABEL[status]} />
        <Row k="Sequence" v={evs.length ? evs.map((e) => `#${e.seq}`).join(", ") : null} />
        <Row k="Timestamp" v={ev?.started_at ? `${fmtTime(ev.started_at)} (${new Date(ev.started_at).toISOString().slice(0, 10)})` : null} />
        <Row k="Size basis" v={`complexity · ${node.degree} links · ${node.event_count} events`} />
      </Section>

      <Section title="Performance">
        <Row k="Start" v={ev?.started_at ? fmtTime(ev.started_at) : null} />
        <Row k="End" v={ev?.ended_at ? fmtTime(ev.ended_at) : null} />
        <Row k="Duration" v={ev?.duration_ms != null ? fmtMs(ev.duration_ms) : null} />
        <Row k="Processing" v={node.total_ms != null ? `${fmtMs(node.total_ms)} across ${node.event_count} event${node.event_count === 1 ? "" : "s"}` : null} />
        <Row k="T+ offset" v={ev?.offset_ms != null ? fmtMs(ev.offset_ms) : null} />
        {timings ? <KVs obj={timings} /> : null}
        {usedBy.length ? <Row k="Called by" v={`${usedBy.length} event${usedBy.length === 1 ? "" : "s"}`} /> : null}
      </Section>

      <Section title="Inputs">
        <Row k="Received from" v={ev?.from ? nodeById.get(ev.from)?.label ?? ev.from : null} />
        <KVs obj={ev?.inputs as Record<string, unknown> | undefined} />
      </Section>

      <Section title="Actions">
        <Row k="Operation" v={ev?.label ?? node.description} />
        <Row k="Tools called" v={ev?.via?.length ? ev.via.map((v) => nodeById.get(v)?.label ?? v) : null} />
        <Row k="API endpoint" v={endpoint} mono />
        <Row k="Model / cache" v={outputs.llm_source ? `${String(outputs.llm_source)} · ${String(outputs.model ?? "")}` : null} />
        <Row k="External service" v={node.id === "outbound:smtp" ? data.host : node.id === "llm:ollama" ? `${String(data.provider)} ${String(data.model)}${data.demo_offline ? " (offline demo: not called)" : ""}` : null} />
      </Section>

      <Section title="Outputs">
        {ev?.error ? <Row k="Error" v={ev.error} /> : null}
        <KVs obj={outputs} skip={["timings_ms", "evidence", "llm_source", "model", "step"]} />
      </Section>

      <Section title="Validation">
        {node.kind === "rule" ? (
          <>
            <Row k="Check" v={data.check} mono />
            <Row k="Mode" v={data.mode} />
            <Row k="On fail" v={data.on_fail} />
            <Row k="Requires docs" v={data.docs} />
            <Row k="Result" v={result?.status ?? (status === "skipped" ? "SKIPPED (documents missing)" : null)} />
            <Row k="Message" v={result?.message} />
          </>
        ) : ruleChildren.length ? (
          <>
            <Row k="Rules fed" v={ruleChildren.length} />
            <Row k="Passed" v={ruleStats.pass} />
            <Row k="Failed" v={ruleStats.fail} />
            <Row k="Warnings" v={ruleStats.warn} />
          </>
        ) : (
          <Row k="Rules" v={null} />
        )}
      </Section>

      <Section title="Dependencies">
        <p className="text-[11px] text-white/35">Previous</p>
        <Chips ids={[...(adjacency.inc.get(node.id) ?? [])]} nodeById={nodeById} onSelect={onSelect} />
        <p className="pt-1 text-[11px] text-white/35">Next</p>
        <Chips ids={[...(adjacency.out.get(node.id) ?? [])]} nodeById={nodeById} onSelect={onSelect} />
      </Section>

      <Section title="Evidence">
        {evidence.length ? (
          evidence.slice(0, 12).map((e, i) => (
            <div key={i} className="rounded-[6px] bg-white/[0.03] px-2 py-1.5 font-mono text-[11.5px]/[16px] text-white/70">
              {String(e.doc ?? "")} · {String(e.field ?? "")}
              {e.page ? ` · p${String(e.page)}` : ""}
              {e.value ? <div className="break-words text-white/45">{String(e.value)}</div> : null}
            </div>
          ))
        ) : node.kind === "file" ? (
          <Row k="Source file" v={node.label} mono />
        ) : (
          <Row k="References" v={null} />
        )}
        {node.id.startsWith("lock:") || node.id === "store:audit_log" ? <Row k="Audit record" v={evs.length ? "audit_log.jsonl" : null} mono /> : null}
      </Section>
      <div className="h-4 shrink-0" />
    </motion.div>
  );
}

function SummaryPanel({ graph, onSelect }: { graph: ExecutionGraph; onSelect: (id: string) => void }) {
  const s = graph.summary;
  const red = s.state !== "approved" && s.state !== "sent_back" && s.state !== "not_run";
  const kind =
    s.state === "pending_approval"
      ? "Pending approval"
      : s.state === "safe_pause"
        ? "Safely paused"
        : s.state === "error"
          ? "Error"
          : s.state === "approved"
            ? "Completed"
            : s.state === "sent_back"
              ? "Completed (sent back)"
              : "Not run";
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      <div className="px-4 pt-4 pb-3">
        <p className="text-[11px]/[14px] font-medium tracking-[0.04em] text-white/35 uppercase">Run</p>
        <h3 className="mt-1.5 text-[16px]/[22px] font-semibold tracking-[-0.01em] text-white">{s.title}</h3>
        <div
          className={`mt-3 rounded-[8px] border px-3 py-2.5 text-[12.5px]/[18px] ${
            red ? "border-[rgb(244_80_80/0.25)] bg-[rgb(244_80_80/0.07)] text-[rgb(255_200_200)]" : "border-[rgb(74_201_140/0.22)] bg-[rgb(74_201_140/0.07)] text-[rgb(190_240_215)]"
          }`}
        >
          <span className="font-medium">{kind}. </span>
          {s.explanation}
          {red && s.human_action ? <div className="mt-1.5 text-white/50">{s.human_action}</div> : null}
        </div>
        {red ? (
          <button
            type="button"
            onClick={() => onSelect("gate:human")}
            className="mt-2 cursor-pointer text-[12px] text-[rgb(255_150_150)] hover:text-white"
          >
            Inspect the human gate →
          </button>
        ) : null}
      </div>
      {s.attention.length ? (
        <Section title={s.state === "approved" ? "Flags resolved by the officer" : "Needs human attention"}>
          {s.attention.map((a) => (
            <button
              key={a.rule_id}
              type="button"
              onClick={() => a.rule_id && onSelect(`rule:${a.rule_id}`)}
              className="block w-full cursor-pointer rounded-[6px] px-2 py-1.5 text-left transition-colors hover:bg-white/[0.04]"
            >
              <span className="flex items-center gap-2 text-[12px]/[16px] font-medium text-white/85">
                <Dot status={s.state === "approved" ? "completed" : "attention"} />
                {a.rule_id}
                <span className="font-normal text-white/35">{a.status}</span>
              </span>
              <span className="mt-0.5 block pl-4 text-[12px]/[16px] text-white/50">{a.message}</span>
            </button>
          ))}
        </Section>
      ) : null}
      <Section title="Execution">
        <Row k="Events" v={s.event_count} />
        <Row k="Agent time" v={s.timing_available ? fmtMs(s.pipeline_ms) : null} />
        <Row k="Total elapsed" v={s.timing_available ? fmtMs(s.total_ms) : null} />
        <Row k="Started" v={s.started_at ? `${fmtTime(s.started_at)} (${s.started_at.slice(0, 10)})` : null} />
        <Row k="Outcome" v={s.outcome} />
        <Row k="Facts source" v={s.facts_source} />
        {!s.timing_available ? (
          <p className="pt-1 text-[11.5px]/[16px] text-white/40">
            This run was recorded before execution tracing existed: event order comes from the stored report, timings are unavailable.
          </p>
        ) : null}
      </Section>
      <Section title="Environment">
        <Row k="Components" v={graph.nodes.length} />
        <Row k="Links" v={graph.edges.length} />
        <Row k="Checklist" v={`${s.checklist.id} v${s.checklist.version} · ${s.checklist.rules} rules`} />
        <Row k="Registry" v={`${s.registry.checks} checks · ${s.registry.extractors} extractors`} />
        <Row k="Mode" v={s.demo_offline ? "Offline demo (LLM calls served from fixtures)" : "Live"} />
      </Section>
      <p className="px-4 pt-2 pb-5 text-[11.5px]/[16px] text-white/30">
        Click a node to inspect it. Drag to pan, scroll to zoom, drag a node to move it, double-click to focus its branch. Space plays, arrows step.
      </p>
    </div>
  );
}
