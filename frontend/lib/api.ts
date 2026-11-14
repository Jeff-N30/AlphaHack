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
  rule_ids?: string[];
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

export function filePreviewUrl(applicationId: string, filename: string) {
  return `${API_URL}/applications/${applicationId}/files/${encodeURIComponent(filename)}`;
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
) {
  const { token } = await postConfirmToken(id, action, officer);
  return request<{ meta: ApplicationDetail["meta"]; draft?: DraftMessage }>(
    `/applications/${id}/gloria-action`,
    {
      method: "POST",
      body: JSON.stringify({
        action,
        officer,
        confirm_token: token,
        draft_id: draftId,
      }),
    },
  );
}

export function postEmailInboxRead() {
  return request<Record<string, unknown>>("/email/inbox/read", { method: "POST" });
}

export function postSeedCase(caseId: string) {
  return request<Record<string, unknown>>(`/demo/seed-case/${caseId}`, {
    method: "POST",
  });
}

export { API_URL };
