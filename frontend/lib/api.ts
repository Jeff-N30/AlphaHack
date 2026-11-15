/** VisaRef backend client (Gloria desk). */

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export type ApplicationRow = {
  id: string;
  applicant_name?: string | null;
  trip_summary?: string | null;
  case_id?: string | null;
  status: string;
  outcome?: string | null;
  human_required?: boolean;
  human_action?: string | null;
  checklist_id?: string | null;
  submission_date?: string | null;
  created_at?: string | null;
  email_uid?: string | null;
  email_source?: string | null;
  escalations?: number | null;
  has_report?: boolean;
  has_draft?: boolean;
};

export type DraftMessage = {
  id?: string;
  body?: string;
  language?: string;
  status?: string;
  channel?: string;
  rule_ids?: string[];
};

export type DeliveryResult = {
  channel?: string;
  delivered?: boolean;
  to?: string;
  intended_to?: string;
  note?: string;
  email_error?: string;
};

export type ApplicationDetail = {
  meta: Record<string, unknown> & {
    id: string;
    applicant_name?: string | null;
    trip_summary?: string | null;
    case_id?: string | null;
    status?: string;
    outcome?: string;
    human_required?: boolean;
    human_action?: string;
    checklist_id?: string;
    submission_date?: string;
    created_at?: string;
    last_officer?: string;
    facts_source?: string;
    applicant_email?: string | null;
    email_sender?: string | null;
    last_delivery?: DeliveryResult | null;
  };
  files: string[];
  report: {
    audit?: {
      outcome?: string;
      escalations?: number;
      results?: Array<{
        id?: string;
        rule_id?: string;
        status?: string;
        message?: string;
        evidence?: Array<{ doc?: string; field?: string; value?: string; page?: number }>;
      }>;
      skipped_rules?: string[];
      drafts?: DraftMessage[];
    };
    [key: string]: unknown;
  } | null;
};

export async function postOfficerAuth(pin: string, officer = "Gloria") {
  return request<{ ok: boolean; officer: string; session: string }>(
    "/auth/officer",
    {
      method: "POST",
      body: JSON.stringify({ pin, officer }),
    },
  );
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function fetchApplications() {
  return request<ApplicationRow[]>("/applications");
}

export function fetchApplication(id: string) {
  return request<ApplicationDetail>(`/applications/${id}`);
}

export type GraphNodeStatus =
  | "completed"
  | "attention"
  | "awaiting"
  | "pending"
  | "available"
  | "disabled"
  | "skipped"
  | "error";

export type ExecutionGraphNode = {
  id: string;
  label: string;
  cluster: string;
  category: string;
  kind: string;
  component?: string | null;
  description?: string | null;
  data: Record<string, unknown>;
  configured: boolean;
  status: GraphNodeStatus;
  warning: boolean;
  event_count: number;
  total_ms: number | null;
  degree: number;
  size: number;
};

export type ExecutionGraphEdge = { source: string; target: string; kind: string };

export type ExecutionEvent = {
  id: string;
  seq: number;
  node: string;
  label?: string | null;
  status: string;
  started_at?: string | null;
  ended_at?: string | null;
  duration_ms?: number | null;
  offset_ms?: number | null;
  inputs?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  via?: string[];
  from?: string | null;
  parent?: string | null;
  run?: string;
  error?: string;
  untimed?: boolean;
};

export type ExecutionGraph = {
  application_id: string;
  applicant_name?: string | null;
  nodes: ExecutionGraphNode[];
  edges: ExecutionGraphEdge[];
  events: ExecutionEvent[];
  clusters: Record<string, string>;
  summary: {
    state: "approved" | "sent_back" | "error" | "not_run" | "pending_approval" | "safe_pause";
    title: string;
    explanation: string;
    outcome?: string | null;
    status?: string;
    human_action?: string | null;
    attention: Array<{ rule_id?: string; status?: string; message?: string }>;
    event_count: number;
    timing_available: boolean;
    pipeline_ms: number | null;
    total_ms: number | null;
    started_at: string | null;
    checklist: { id: string; version: string; rules: number };
    registry: { checks: number; extractors: number };
    facts_source?: string | null;
    demo_offline?: boolean;
  };
};

export function fetchExecutionGraph(id: string) {
  return request<ExecutionGraph>(`/applications/${encodeURIComponent(id)}/execution-graph`);
}

export function filePreviewUrl(applicationId: string, filename: string) {
  return `${API_URL}/applications/${applicationId}/files/${encodeURIComponent(filename)}`;
}

/** Always PNG — PDF page 1 rendered, or the image itself. Best for in-desk demo. */
export function filePagePreviewUrl(
  applicationId: string,
  filename: string,
  page = 1,
) {
  return `${API_URL}/applications/${applicationId}/files/${encodeURIComponent(filename)}/page/${page}`;
}

export async function postConfirmToken(
  applicationId: string,
  action: "approve" | "send_back" | "review",
  officer = "Gloria",
) {
  return request<{ token: string; expires_in_s: number }>("/confirm-tokens", {
    method: "POST",
    body: JSON.stringify({ application_id: applicationId, action, officer }),
  });
}

export async function postGloriaAction(
  id: string,
  action: "approve" | "send_back" | "review",
  officer = "Gloria",
  draftId?: string,
  toEmail?: string,
  bodyOverride?: string,
) {
  const { token } = await postConfirmToken(id, action, officer);
  return request<{
    meta: ApplicationDetail["meta"];
    draft?: DraftMessage;
    delivery?: DeliveryResult;
  }>(`/applications/${id}/gloria-action`, {
    method: "POST",
    body: JSON.stringify({
      action,
      officer,
      confirm_token: token,
      draft_id: draftId,
      to_email: toEmail || undefined,
      body_override: bodyOverride || undefined,
    }),
  });
}

export function postEmailInboxRead() {
  return request<Record<string, unknown>>("/email/inbox/read", { method: "POST" });
}

export function postSeedCase(caseId: string) {
  return request<Record<string, unknown>>(`/demo/seed-case/${caseId}`, {
    method: "POST",
  });
}

export async function uploadAndAudit(
  files: File[],
  opts?: { checklistId?: string; submissionDate?: string },
) {
  if (!files.length) throw new Error("Pick at least one PDF or image");
  const checklistId = opts?.checklistId ?? "fr-schengen-short-stay";
  const submissionDate = opts?.submissionDate ?? "2026-11-16";
  const body = new FormData();
  body.append("checklist_id", checklistId);
  body.append("submission_date", submissionDate);
  for (const f of files) body.append("files", f);

  const created = await fetch(`${API_URL}/applications`, {
    method: "POST",
    headers: { Accept: "application/json" },
    body,
  });
  if (!created.ok) {
    const text = await created.text().catch(() => "");
    throw new Error(text || `${created.status} ${created.statusText}`);
  }
  const meta = (await created.json()) as { id: string; rejected?: unknown[] };
  const audit = await request<Record<string, unknown>>(
    `/applications/${meta.id}/run`,
    { method: "POST" },
  );
  return { id: meta.id, created: meta, audit };
}

export { API_URL };
