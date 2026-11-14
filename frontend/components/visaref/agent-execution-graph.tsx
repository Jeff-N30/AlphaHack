"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { Html, Line, OrbitControls, Stars } from "@react-three/drei";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Group, Mesh } from "three";
import * as THREE from "three";
import { motion, useReducedMotion } from "motion/react";

type NodeStatus = "completed" | "active" | "waiting" | "available";

type TraceNode = {
  id: string;
  label: string;
  category: string;
  detail: string;
  evidence: string;
  tool: string;
  position: [number, number, number];
  radius: number;
  status: NodeStatus;
  sequence?: number;
};

type Props = {
  applicantName?: string | null;
  files: string[];
  outcome?: string;
  resultCount: number;
  escalationCount: number;
  completed: boolean;
  onClose: () => void;
};

const colors = {
  completed: "#63e6a1",
  active: "#f6d365",
  waiting: "#ff5f68",
  available: "#657080",
  filament: "#617080",
};

function NodeMesh({
  node,
  selected,
  onSelect,
}: {
  node: TraceNode;
  selected: boolean;
  onSelect: () => void;
}) {
  const mesh = useRef<Mesh>(null);
  const group = useRef<Group>(null);
  const color = colors[node.status];
  useFrame(({ clock }) => {
    if (!group.current) return;
    const pulse = node.status === "waiting" || node.status === "active";
    group.current.scale.setScalar(
      selected && pulse ? 1 + Math.sin(clock.elapsedTime * 4) * 0.06 : 1,
    );
    if (mesh.current && pulse) {
      mesh.current.rotation.y = clock.elapsedTime * 0.22;
    }
  });

  return (
    <group ref={group} position={node.position}>
      <mesh
        ref={mesh}
        onClick={(event) => {
          event.stopPropagation();
          onSelect();
        }}
      >
        <sphereGeometry args={[node.radius, 24, 24]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={selected ? 2.4 : node.status === "available" ? 0.1 : 0.65}
          roughness={0.45}
          metalness={0.15}
          transparent={node.status === "available"}
          opacity={node.status === "available" ? 0.48 : 1}
        />
      </mesh>
      {selected ? (
        <mesh scale={1.35}>
          <sphereGeometry args={[node.radius, 16, 16]} />
          <meshBasicMaterial color={color} transparent opacity={0.12} />
        </mesh>
      ) : null}
      <Html distanceFactor={10} position={[0, -node.radius - 0.12, 0]} center>
        <button
          type="button"
          onClick={onSelect}
          className={`whitespace-nowrap font-mono text-[10px] transition ${selected ? "text-white" : node.status === "available" ? "text-white/35" : "text-white/65"}`}
        >
          {node.label}
        </button>
      </Html>
    </group>
  );
}

function TraceConnection({
  start,
  end,
  active,
  particle,
}: {
  start: [number, number, number];
  end: [number, number, number];
  active: boolean;
  particle: number;
}) {
  const mesh = useRef<Mesh>(null);
  const from = useMemo(() => new THREE.Vector3(...start), [start]);
  const to = useMemo(() => new THREE.Vector3(...end), [end]);
  useFrame(({ clock }) => {
    if (!mesh.current) return;
    const progress = (clock.elapsedTime * 0.42 + particle) % 1;
    mesh.current.position.copy(from).lerp(to, progress);
  });
  return (
    <>
      <Line
        points={[start, end]}
        color={active ? colors.completed : colors.filament}
        transparent
        opacity={active ? 0.72 : 0.2}
        lineWidth={active ? 1.4 : 0.55}
      />
      {active ? (
        <mesh ref={mesh}>
          <sphereGeometry args={[0.045, 10, 10]} />
          <meshBasicMaterial color={colors.active} />
        </mesh>
      ) : null}
    </>
  );
}

function TraceScene({
  nodes,
  edges,
  selected,
  onSelect,
  step,
  playing,
}: {
  nodes: TraceNode[];
  edges: [string, string][];
  selected: string;
  onSelect: (id: string) => void;
  step: number;
  playing: boolean;
}) {
  const particleRef = useRef(0);
  useFrame((_, delta) => {
    if (playing) particleRef.current = (particleRef.current + delta * 0.8) % 1;
  });
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  return (
    <>
      <ambientLight intensity={0.8} />
      <pointLight position={[0, 5, 6]} intensity={16} distance={20} color="#8ab7ff" />
      <Stars radius={18} depth={12} count={650} factor={1.2} saturation={0} fade speed={0.25} />
      {edges.map(([from, to], index) => {
        const start = nodeById.get(from);
        const end = nodeById.get(to);
        if (!start || !end) return null;
        const active = index < step;
        return (
          <TraceConnection
            key={`${from}-${to}`}
            start={start.position}
            end={end.position}
            active={active}
            particle={particleRef.current}
          />
        );
      })}
      {nodes.map((node) => (
        <NodeMesh
          key={node.id}
          node={node}
          selected={selected === node.id}
          onSelect={() => onSelect(node.id)}
        />
      ))}
      <OrbitControls makeDefault enableDamping dampingFactor={0.08} minDistance={5} maxDistance={22} />
    </>
  );
}

export default function AgentExecutionGraph({
  applicantName,
  files,
  outcome,
  resultCount,
  escalationCount,
  completed,
  onClose,
}: Props) {
  const reduceMotion = useReducedMotion();
  const nodes = useMemo<TraceNode[]>(() => {
    const executed: Omit<TraceNode, "status">[] = [
      {
        id: "ingest",
        label: "Ingest",
        category: "Input",
        detail: "Read the local application record and established the processing boundary.",
        evidence: "Source: local application record · no external upload",
        tool: "app.ingest.pipeline.process_application",
        position: [-4.6, 0.1, 0.4],
        radius: 0.36,
        sequence: 1,
      },
      {
        id: "inventory",
        label: "File inventory",
        category: "Documents",
        detail: "Enumerated supported PDF/image attachments and ignored control files.",
        evidence: `${files.length} file${files.length === 1 ? "" : "s"} available · filenames preserved`,
        tool: "ingest.email_pipeline._attachment_paths",
        position: [-3.1, 1.8, -0.5],
        radius: 0.3,
        sequence: 2,
      },
      {
        id: "render",
        label: "Render pages",
        category: "Documents",
        detail: "Rendered source pages for OCR and page-addressable evidence.",
        evidence: "PDF/image renderer · page references retained",
        tool: "ingest.render.render_page_png",
        position: [-2.2, -1.6, 1.1],
        radius: 0.48,
        sequence: 3,
      },
      {
        id: "ocr",
        label: "OCR + text",
        category: "Extraction",
        detail: "Collected machine-readable text before structured field extraction.",
        evidence: "OCR text is attached to the document extraction context",
        tool: "extract.pipeline_extract",
        position: [-0.5, 1.25, -1.8],
        radius: 0.43,
        sequence: 4,
      },
      {
        id: "llama",
        label: "Llama extract",
        category: "Extraction",
        detail: "Requested typed facts only. The model does not decide PASS or FAIL.",
        evidence: "Extraction JSON · provider/model details stored in report",
        tool: "extract.llm / extract_application_docs",
        position: [0.8, -0.7, -0.7],
        radius: 0.68,
        sequence: 5,
      },
      {
        id: "mrz",
        label: "MRZ verify",
        category: "Validation",
        detail: "Checked identity fields, MRZ checksums, and passport date consistency.",
        evidence: "Passport identity guard · checksum validation",
        tool: "extract.mrz.verify_mrz",
        position: [2.4, 1.8, 0.6],
        radius: 0.4,
        sequence: 6,
      },
      {
        id: "rules",
        label: "Rules engine",
        category: "Decision",
        detail: "Compared facts with the France Schengen checklist, rule by rule.",
        evidence: `${resultCount} rule result${resultCount === 1 ? "" : "s"} · ${outcome || "outcome unavailable"}`,
        tool: "rules.engine.run",
        position: [3.4, -1.25, -1.4],
        radius: 0.58,
        sequence: 7,
      },
      {
        id: "evidence",
        label: "Evidence report",
        category: "Audit",
        detail: "Attached document, field, page, and escalation references for Gloria.",
        evidence: `${escalationCount} escalation${escalationCount === 1 ? "" : "s"} · report persisted`,
        tool: "audit_pipeline.audit_application",
        position: [4.6, 1.2, 1],
        radius: 0.5,
        sequence: 8,
      },
      {
        id: "human",
        label: completed ? "Approved" : "Gloria review",
        category: "Human gate",
        detail: completed
          ? "The human decision was recorded and the case left the review queue."
          : "The pipeline stopped safely. Gloria must inspect the evidence and decide.",
        evidence: completed ? "Terminal: approved" : "Terminal: human_required = true",
        tool: completed ? "lock.actions.approve" : "lock.actions",
        position: [5.4, -0.25, 0.1],
        radius: 0.7,
        sequence: 9,
      },
    ];
    const executedCount = completed ? executed.length : executed.length - 1;
    return [
      ...executed.map((node, index) => ({
        ...node,
        status: index < executedCount ? "completed" : "waiting",
      })),
      {
        id: "db",
        label: "Metadata DB",
        category: "Available",
        detail: "Available storage component; no separate execution event is recorded for this graph.",
        evidence: "Status: available, execution timing unavailable",
        tool: "storage.db / SQLModel",
        position: [-4.3, -2.6, -1.4],
        radius: 0.25,
        status: "available",
      },
      {
        id: "draft",
        label: "Draft writer",
        category: "Available",
        detail: "Available outbound draft component; shown only when the stored report uses it.",
        evidence: "Status: available, execution timing unavailable",
        tool: "drafts.drafter.attach_drafts",
        position: [0.6, 2.9, 1.4],
        radius: 0.28,
        status: "available",
      },
      {
        id: "smtp",
        label: "SMTP delivery",
        category: "Available",
        detail: "Available delivery component; not presented as executed without a delivery event.",
        evidence: "Status: available, execution timing unavailable",
        tool: "outbound.email_smtp",
        position: [4.7, 2.7, -1.3],
        radius: 0.22,
        status: "available",
      },
    ] as TraceNode[];
  }, [completed, escalationCount, files.length, outcome, resultCount]);

  const edges = useMemo<[string, string][]>(() => [
    ["ingest", "inventory"],
    ["inventory", "render"],
    ["inventory", "ocr"],
    ["render", "ocr"],
    ["ocr", "llama"],
    ["llama", "mrz"],
    ["llama", "rules"],
    ["mrz", "rules"],
    ["rules", "evidence"],
    ["evidence", "human"],
    ["inventory", "db"],
    ["llama", "draft"],
    ["human", "smtp"],
  ], []);
  const [playing, setPlaying] = useState(!reduceMotion);
  const [step, setStep] = useState(completed ? 8 : 0);
  const [selected, setSelected] = useState(completed ? "human" : "ingest");
  const active = nodes.find((node) => node.id === selected) ?? nodes[0];
  const executedPath = nodes.filter((node) => node.sequence);
  const maxStep = completed ? executedPath.length : executedPath.length - 1;

  useEffect(() => {
    if (!playing || step >= maxStep) return undefined;
    const timer = window.setTimeout(
      () => {
        setStep((current) => current + 1);
        setSelected(executedPath[Math.min(step + 1, executedPath.length - 1)].id);
      },
      reduceMotion ? 0 : 900,
    );
    return () => window.clearTimeout(timer);
  }, [executedPath, maxStep, playing, reduceMotion, step]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-3 backdrop-blur-md sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="agent-execution-graph-title"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <motion.section
        initial={reduceMotion ? false : { opacity: 0, scale: 0.97, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        className="flex h-[min(900px,calc(100dvh-24px))] w-full max-w-7xl flex-col overflow-hidden rounded-[14px] border border-white/12 bg-[#090b10] text-white shadow-[0_30px_100px_-30px_rgb(0_0_0/0.95)]"
      >
        <header className="flex shrink-0 items-start gap-4 border-b border-white/10 px-4 py-4 sm:px-6">
          <div className="min-w-0 flex-1">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/42">
              Agent trace / 3D graph view
            </p>
            <h2 id="agent-execution-graph-title" className="mt-1 text-[20px]/[24px] font-[450] tracking-[-0.02em]">
              {applicantName || "Application"} · execution environment
            </h2>
            <p className="mt-1 text-[12px]/[17px] text-white/55">
              Drag to rotate · scroll to zoom · right-drag to pan · click a node for details
            </p>
          </div>
          <button type="button" onClick={onClose} className="rounded-md border border-white/12 px-2.5 py-1.5 text-[12px] text-white/65 hover:border-white/25 hover:text-white">
            Close
          </button>
        </header>

        <div className="relative min-h-0 flex-1">
          <Canvas camera={{ position: [0, 0, 12], fov: 48 }} dpr={[1, 2]}>
            <color attach="background" args={["#090b10"]} />
            <TraceScene
              nodes={nodes}
              edges={edges}
              selected={selected}
              onSelect={(id) => {
                setSelected(id);
                setPlaying(false);
              }}
              step={step}
              playing={playing}
            />
          </Canvas>

          <div className="pointer-events-none absolute left-4 top-4 rounded-md border border-white/10 bg-black/35 px-3 py-2 font-mono text-[10px]/[16px] text-white/50 backdrop-blur-sm">
            <div className="text-white/75">OBSIDIAN TRACE SPACE</div>
            <div>green executed · yellow active · red human gate · grey available</div>
            <div>timings: unavailable — backend has no event timestamps yet</div>
          </div>

          <aside className="absolute bottom-4 right-4 hidden w-[min(330px,calc(100%-32px))] rounded-lg border border-white/12 bg-[#0d1017]/90 p-3.5 backdrop-blur-xl sm:block">
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-white/40">
                Selected node
              </span>
              <span className={`font-mono text-[10px] uppercase ${active.status === "waiting" ? "text-red-300" : active.status === "available" ? "text-white/35" : "text-emerald-300"}`}>
                {active.status}
              </span>
            </div>
            <h3 className="mt-1 text-[16px]/[20px] font-[450]">{active.label}</h3>
            <p className="mt-1 text-[12px]/[17px] text-white/65">{active.detail}</p>
            <dl className="mt-3 space-y-1.5 border-t border-white/10 pt-2.5 font-mono text-[10px]/[15px]">
              <div className="flex gap-2"><dt className="text-white/35">component</dt><dd className="min-w-0 truncate text-cyan-200/70">{active.tool}</dd></div>
              <div className="flex gap-2"><dt className="text-white/35">evidence</dt><dd className="text-white/55">{active.evidence}</dd></div>
              <div className="flex gap-2"><dt className="text-white/35">timing</dt><dd className="text-white/45">Unavailable (not recorded)</dd></div>
            </dl>
          </aside>
        </div>

        <footer className="flex shrink-0 flex-wrap items-center gap-2 border-t border-white/10 bg-[#0d1017] px-4 py-3 sm:px-6">
          <button
            type="button"
            onClick={() => setPlaying((current) => !current)}
            className="rounded-md border border-white/15 bg-white/8 px-3 py-1.5 text-[12px] hover:bg-white/14"
          >
            {playing ? "Pause" : "Play"}
          </button>
          <button
            type="button"
            onClick={() => {
              setStep(0);
              setSelected(executedPath[0].id);
              setPlaying(true);
            }}
            className="rounded-md border border-white/12 px-3 py-1.5 text-[12px] text-white/70 hover:border-white/25 hover:text-white"
          >
            Replay
          </button>
          <span className="ml-1 font-mono text-[10px] text-white/42">
            event {Math.min(step + 1, executedPath.length)} / {executedPath.length} · total elapsed unavailable
          </span>
          <span className="ml-auto font-mono text-[10px] text-white/42">
            {completed ? "completed with human decision" : "paused safely for human review"}
          </span>
        </footer>
      </motion.section>
    </div>
  );
}
