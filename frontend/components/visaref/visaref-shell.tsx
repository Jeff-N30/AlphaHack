"use client";

/**
 * VisaRef Gloria desk — app shell + approval gate UI (owned source in-repo).
 */
import Image from "next/image";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { HugeiconsIcon, type IconSvgElement } from "@hugeicons/react";
import {
  Alert02Icon,
  ArrowRight02Icon,
  Cancel01Icon,
  CheckmarkCircle02Icon,
  File01Icon,
  InboxIcon,
  Loading03Icon,
  Mail01Icon,
  Menu01Icon,
  NeuralNetworkIcon,
  PassportIcon,
  RefreshIcon,
  SentIcon,
  Tick02Icon,
} from "@hugeicons/core-free-icons";
import { toast } from "sonner";
import {
  fetchApplication,
  fetchApplications,
  filePagePreviewUrl,
  filePreviewUrl,
  postEmailInboxRead,
  postGloriaAction,
  postSeedCase,
  redactApplication,
  uploadAndAudit,
  type ApplicationRow,
} from "@/lib/api";
import AgentExecutionGraph from "@/components/visaref/agent-execution-graph";

const cx = (...c: (string | false | null | undefined)[]) =>
  c.filter(Boolean).join(" ");

function useScrollFade<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [edges, setEdges] = useState({ start: false, end: false });

  const update = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    const { scrollTop, scrollHeight, clientHeight } = el;
    setEdges({
      start: scrollTop > 1,
      end: Math.ceil(scrollTop + clientHeight) < scrollHeight - 1,
    });
  }, []);

  useEffect(() => {
    update();
    const el = ref.current;
    const view = el?.ownerDocument.defaultView;
    if (!el || !view?.ResizeObserver) return;
    const observer = new view.ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, [update]);

  return { ref, edges, onScroll: update };
}

const canvas = "bg-white dark:bg-neutral-950";
const pageFog = "bg-neutral-50 dark:bg-neutral-950";
const frame =
  "relative flex min-w-0 flex-col overflow-hidden rounded-[var(--rb-r-lg,10px)] border border-neutral-900/10 dark:border-neutral-100/14 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100";
const paper = "bg-white dark:bg-neutral-900";
const backdrop = "bg-neutral-900/25 dark:bg-neutral-950/60";
const text1 = "text-[#192123] dark:text-neutral-100";
const text2 = "text-[#41494c] dark:text-neutral-100/80";
const text3 = "text-[#5c6568] dark:text-neutral-100/66";
const rowsRuled = "divide-y divide-[rgb(25_33_35/0.06)] dark:divide-neutral-100/8";
const overlayShadow =
  "shadow-[0_12px_24px_-12px_rgb(0_0_0/0.2)] dark:shadow-[0_12px_24px_-12px_rgb(0_0_0/0.6)]";
const typeHeadingSm = "text-[20px]/[28px] font-semibold tracking-[-0.02em]";
const typeHeadingXs = "text-[16px]/[24px] font-semibold tracking-[-0.01em]";
const typeLabel = "text-[14px]/[20px] font-medium";
const typeBodySm = "text-[13px]/[18px] font-normal";
const typeCaption = "text-[12px]/[16px] font-normal tabular-nums";
const typeRowTitle = "text-[13px]/[18px] font-medium";
const focusRing =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--rb-accent,oklch(20.5%_0_0))] dark:focus-visible:outline-[var(--rb-accent,oklch(100%_0_0))]";
const focusRingInset =
  "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--rb-accent,oklch(20.5%_0_0))] dark:focus-visible:outline-[var(--rb-accent,oklch(100%_0_0))]";
const primaryButton =
  "relative inline-flex shrink-0 cursor-pointer items-center justify-center whitespace-nowrap select-none transition-[color,background-color,border-color,box-shadow,outline-color,scale,filter] duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)] active:scale-[0.98] active:duration-[60ms] motion-reduce:active:scale-100 disabled:cursor-not-allowed aria-busy:cursor-progress focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--rb-accent,oklch(20.5%_0_0))] dark:focus-visible:outline-[var(--rb-accent,oklch(100%_0_0))] bg-[linear-gradient(180deg,color-mix(in_oklab,var(--rb-accent,oklch(20.5%_0_0))_84%,white),color-mix(in_oklab,var(--rb-accent,oklch(20.5%_0_0))_94%,black))] text-[var(--rb-accent-fg,oklch(100%_0_0))] shadow-[inset_0_2px_0_-1px_rgb(255_255_255/0.2),inset_0_-2px_0_-1px_rgb(0_0_0/0.3),inset_0_0_0_1px_color-mix(in_oklab,var(--rb-accent,oklch(20.5%_0_0))_88%,black),0_1px_1px_rgb(0_0_0/0.22),0_2px_5px_-2px_rgb(0_0_0/0.3)] hover:not-disabled:brightness-110 active:shadow-[inset_0_0_0_1px_color-mix(in_oklab,var(--rb-accent,oklch(20.5%_0_0))_88%,black),inset_0_1px_2px_rgb(0_0_0/0.42)] disabled:opacity-40 disabled:shadow-none dark:bg-[linear-gradient(180deg,color-mix(in_oklab,var(--rb-accent,oklch(100%_0_0))_84%,white),color-mix(in_oklab,var(--rb-accent,oklch(100%_0_0))_94%,black))] dark:text-[var(--rb-accent-fg,oklch(20.5%_0_0))] dark:shadow-[inset_0_2px_0_-1px_rgb(255_255_255/0.2),inset_0_-2px_0_-1px_rgb(0_0_0/0.3),inset_0_0_0_1px_color-mix(in_oklab,var(--rb-accent,oklch(100%_0_0))_88%,black),0_1px_1px_rgb(0_0_0/0.66),0_2px_5px_-2px_rgb(0_0_0/0.9)] dark:active:shadow-[inset_0_0_0_1px_color-mix(in_oklab,var(--rb-accent,oklch(100%_0_0))_88%,black),inset_0_1px_2px_rgb(0_0_0/0.42)] dark:disabled:shadow-none";
const secondaryButton =
  "relative inline-flex shrink-0 cursor-pointer items-center justify-center whitespace-nowrap select-none transition-[color,background-color,border-color,box-shadow,outline-color,scale,filter] duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)] active:scale-[0.98] active:duration-[60ms] motion-reduce:active:scale-100 disabled:cursor-not-allowed aria-busy:cursor-progress focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--rb-accent,oklch(20.5%_0_0))] dark:focus-visible:outline-[var(--rb-accent,oklch(100%_0_0))] border border-neutral-900/12 bg-white text-neutral-900 shadow-[0_1px_2px_-1px_rgb(0_0_0/0.12)] hover:not-disabled:border-neutral-900/32 hover:not-disabled:bg-linear-to-b hover:not-disabled:from-neutral-900/3 hover:not-disabled:to-neutral-900/3 active:shadow-[inset_0_1px_2px_rgb(0_0_0/0.12)] disabled:border-neutral-900/8 disabled:text-neutral-900/40 disabled:shadow-none dark:border-neutral-100/14 dark:bg-neutral-900 dark:text-neutral-100 dark:shadow-[0_1px_2px_-1px_rgb(0_0_0/0.36)] dark:hover:not-disabled:border-neutral-100/32 dark:hover:not-disabled:from-neutral-100/3 dark:hover:not-disabled:to-neutral-100/3 dark:active:shadow-[inset_0_1px_2px_rgb(0_0_0/0.4)] dark:disabled:border-neutral-100/8 dark:disabled:text-neutral-100/40";
const ghostButton =
  "relative inline-flex shrink-0 cursor-pointer items-center justify-center whitespace-nowrap select-none transition-[color,background-color,border-color,box-shadow,outline-color,scale,filter] duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)] active:scale-[0.98] active:duration-[60ms] motion-reduce:active:scale-100 disabled:cursor-not-allowed aria-busy:cursor-progress focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--rb-accent,oklch(20.5%_0_0))] dark:focus-visible:outline-[var(--rb-accent,oklch(100%_0_0))] bg-transparent text-neutral-900 hover:not-disabled:bg-neutral-900/5 active:bg-neutral-900/8 aria-pressed:bg-neutral-900/9 disabled:text-neutral-900/40 dark:text-neutral-100 dark:hover:not-disabled:bg-neutral-100/5 dark:active:bg-neutral-100/8 dark:aria-pressed:bg-neutral-100/9 dark:disabled:text-neutral-100/40";
const ghostButtonMuted =
  "relative inline-flex shrink-0 cursor-pointer items-center justify-center whitespace-nowrap select-none transition-[color,background-color,border-color,box-shadow,outline-color,scale,filter] duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)] active:scale-[0.98] active:duration-[60ms] motion-reduce:active:scale-100 disabled:cursor-not-allowed aria-busy:cursor-progress focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--rb-accent,oklch(20.5%_0_0))] dark:focus-visible:outline-[var(--rb-accent,oklch(100%_0_0))] bg-transparent text-neutral-900/80 hover:not-disabled:bg-neutral-900/5 hover:not-disabled:text-neutral-900 active:bg-neutral-900/8 aria-expanded:bg-neutral-900/5 aria-expanded:text-neutral-900 disabled:text-neutral-900/40 dark:text-neutral-100/80 dark:hover:not-disabled:bg-neutral-100/5 dark:hover:not-disabled:text-neutral-100 dark:active:bg-neutral-100/8 dark:aria-expanded:bg-neutral-100/5 dark:aria-expanded:text-neutral-100 dark:disabled:text-neutral-100/40";
const buttonSm =
  "h-8 gap-1.5 rounded-[var(--rb-r-sm,6px)] px-3 text-[13px]/[16px] font-medium";
const buttonMd =
  "h-9 gap-2 rounded-[var(--rb-r-sm,6px)] px-3.5 text-[14px]/[16px] font-medium";
const buttonLg =
  "h-10 gap-2 rounded-[var(--rb-r-sm,6px)] px-4 text-[14px]/[20px] font-medium";
const iconButtonMd = "size-8 rounded-[var(--rb-r-sm,6px)]";
const statusOk = "text-neutral-900/80 dark:text-neutral-100/80";
const statusWarn = "text-[oklch(52%_0.11_62)] dark:text-[oklch(80%_0.13_68)]";
const statusFail = "text-[oklch(51%_0.18_26)] dark:text-[oklch(76%_0.14_26)]";
const avatar =
  "relative inline-flex size-8 shrink-0 overflow-hidden rounded-full select-none";
const avatarSquare =
  "relative inline-flex size-8 shrink-0 overflow-hidden rounded-[var(--rb-r-sm,6px)] select-none";
const avatarFallback =
  "flex size-full items-center justify-center rounded-[inherit] border border-[rgb(25_33_35/0.1)] dark:border-neutral-100/14 bg-white dark:bg-neutral-900 text-[12px]/[16px] font-medium tabular-nums text-[#41494c] dark:text-neutral-100";
const frameTitle =
  "min-w-0 truncate text-[14px]/[20px] font-medium text-[#192123] dark:text-neutral-100";
const panelShell =
  "relative flex min-w-0 flex-col rounded-[var(--rb-r-lg,10px)] border border-[rgb(25_33_35/0.08)] dark:border-neutral-100/14 bg-[#f7f8f8] text-[#192123] dark:text-neutral-100 dark:bg-neutral-900";
const panel = `${panelShell} overflow-hidden`;
const panelHead =
  "flex min-h-11 min-w-0 shrink-0 items-center gap-2.5 px-4 has-[button]:pe-2";
const panelBody =
  "mx-1 mb-1 flex min-w-0 flex-col overflow-hidden rounded-[8px] border border-[rgb(25_33_35/0.08)] bg-white [&:has(+*)]:mb-0 dark:border-neutral-100/8 dark:bg-neutral-950";
const panelFoot =
  "flex min-h-12 min-w-0 items-center gap-2 px-4 py-3 text-[13px]/[18px] text-[#5c6568] dark:text-neutral-100/66 has-[button]:justify-end";
const groupHead =
  "flex h-7 items-center gap-1.5 px-6 text-[12px]/[16px] font-medium text-[#5c6568] dark:text-neutral-100/70";
const groupCount =
  "font-normal tabular-nums text-[#737c7f] dark:text-neutral-100/50";
const checkRow =
  "mx-3 flex w-[calc(100%-24px)] items-start gap-3 rounded-[8px] px-3 py-2 text-left";
const checkHint =
  "line-clamp-2 block text-[12px]/[18px] font-normal text-pretty text-[#737c7f] dark:text-neutral-100/55";
const countPill =
  "inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-[5px] bg-[rgb(25_33_35/0.05)] px-1.5 text-[12px]/[16px] font-medium tabular-nums text-[#5c6568] dark:bg-neutral-100/10 dark:text-neutral-100/70";
const tag =
  "inline-flex h-5 shrink-0 items-center rounded-[5px] px-1.5 text-[12px]/[16px] font-medium";
const tagOk =
  "bg-[rgb(25_33_35/0.06)] text-[#41494c] dark:bg-neutral-100/10 dark:text-neutral-100/80";
const issueGlyph =
  "flex h-[18px] w-4 shrink-0 items-center justify-center before:size-1.5 before:rounded-full before:bg-[oklch(58%_0.19_26)] before:content-['']";
const paneHead =
  "flex h-12 min-w-0 shrink-0 items-center gap-2 border-b border-[rgb(25_33_35/0.08)] bg-white px-6 dark:border-neutral-100/8 dark:bg-neutral-950";
const paneTitle =
  "min-w-0 truncate text-[14px]/[20px] font-semibold tracking-[-0.005em] text-[#192123] dark:text-neutral-100";
const hairT = "border-t border-[rgb(25_33_35/0.08)] dark:border-neutral-100/8";
const docChip =
  "inline-flex h-7 shrink-0 items-center whitespace-nowrap rounded-[6px] border border-[rgb(25_33_35/0.08)] bg-white px-2.5 text-[12px]/[16px] font-medium text-[#41494c] dark:border-neutral-100/14 dark:bg-neutral-900 dark:text-neutral-100/80";
const overlayEnter =
  "transition-opacity duration-[160ms] ease-[cubic-bezier(0.2,0,0,1)] starting:opacity-0 motion-reduce:transition-none";
const sidebarSurface =
  "border-r border-neutral-900/8 bg-white dark:border-neutral-100/8 dark:bg-neutral-900";
const navItem =
  "flex h-8 w-full min-w-0 cursor-pointer items-center gap-2 rounded-[var(--rb-r-sm,6px)] px-2 text-left text-[13px]/[16px] font-medium text-[#41494c] transition-[background-color,color] duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)] [&_svg]:shrink-0 hover:bg-neutral-900/5 hover:text-neutral-900 aria-[current=page]:bg-neutral-900/9 aria-[current=page]:text-neutral-900 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--rb-accent,oklch(20.5%_0_0))] dark:focus-visible:outline-[var(--rb-accent,oklch(100%_0_0))] dark:text-neutral-100/80 dark:hover:bg-neutral-100/5 dark:hover:text-neutral-100 dark:aria-[current=page]:bg-neutral-100/9 dark:aria-[current=page]:text-neutral-100";
const navCount =
  "ms-auto text-[12px]/[16px] font-medium tabular-nums text-neutral-900/66 dark:text-neutral-100/66";
const navGroupLabel =
  "px-2 pt-4 pb-1 text-[12px]/[16px] font-normal tabular-nums text-neutral-900/66 dark:text-neutral-100/66";
const topBar =
  "border-b border-neutral-900/8 bg-white dark:border-neutral-100/8 dark:bg-neutral-900";
const fadeTopOnPaper =
  "bg-linear-to-b from-white to-transparent transition-opacity duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)] dark:from-neutral-900";
const fadeTopOnTray =
  "bg-linear-to-b from-white to-transparent transition-opacity duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)] dark:from-neutral-900";
const fadeBottomOnPaper =
  "bg-linear-to-t from-white to-transparent transition-opacity duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)] dark:from-neutral-900";
const fadeBottomOnTray =
  "bg-linear-to-t from-white to-transparent transition-opacity duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)] dark:from-neutral-900";
const fadeBottom =
  "bg-linear-to-t from-white to-transparent transition-opacity duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)] dark:from-neutral-950";
const skeleton =
  "rounded-[var(--rb-r-sm,6px)] bg-neutral-900/8 dark:bg-neutral-100/8";
const emptyTitle =
  "text-[16px]/[20px] font-semibold tracking-[-0.01em] text-[#192123] dark:text-neutral-100";
const emptyDescription =
  "max-w-[48ch] text-[13px]/[20px] text-[#5c6568] dark:text-neutral-100/80";
const cornerSm = "rounded-[var(--rb-r-sm,6px)]";
const hoverFill = "hover:bg-neutral-900/5 dark:hover:bg-neutral-100/5";
const pressedFill = "active:bg-neutral-900/8 dark:active:bg-neutral-100/8";
const transition =
  "transition-[color,background-color,border-color,box-shadow,outline-color,opacity,scale] duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)] active:duration-[60ms]";
const insetBody = "bg-white dark:bg-neutral-950";
const inkSlot =
  "inline-flex h-6 shrink-0 items-center whitespace-nowrap rounded-[6px] bg-[rgb(25_33_35/0.05)] dark:bg-neutral-100/10 px-2 text-[12px]/[16px] font-medium tabular-nums text-[#5c6568] dark:text-neutral-100/70";
const disclosureRow =
  "group -mx-2 flex min-h-8 max-w-[calc(100%+16px)] min-w-0 cursor-pointer items-center gap-2 self-start rounded-[var(--rb-r-sm,6px)] px-2 text-left text-[13px]/[18px] text-neutral-900/80 dark:text-neutral-100/80 transition-[background-color] duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)] hover:bg-neutral-900/5 active:bg-neutral-900/8 dark:hover:bg-neutral-100/5 dark:active:bg-neutral-100/8 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--rb-accent,oklch(20.5%_0_0))] dark:focus-visible:outline-[var(--rb-accent,oklch(100%_0_0))]";
const toolWell =
  "flex min-w-0 flex-col gap-3 rounded-[var(--rb-r-sm,6px)] bg-neutral-900/5 px-3 py-2 dark:bg-neutral-100/5";
const toolOutput =
  "min-w-0 overflow-x-auto font-mono text-[12px]/[16px] whitespace-pre-wrap text-neutral-900/80 dark:text-neutral-100/80 [overflow-wrap:anywhere]";

const EASE_OUT: [number, number, number, number] = [0.2, 0, 0, 1];

type Tone = "neutral" | "attention" | "critical";
const TONE: Record<Tone, string> = {
  neutral: statusOk,
  attention: statusWarn,
  critical: statusFail,
};

type NavView = "queue" | "approved" | "sent_back" | "inbox" | "upload";

function bucket(row: ApplicationRow): "queue" | "approved" | "sent_back" | "other" {
  if (row.status?.startsWith("approved")) return "approved";
  if (row.status?.startsWith("sent_back")) return "sent_back";
  // Only files waiting on Gloria — not raw ingest without an audit
  if (row.human_required || row.status?.startsWith("awaiting_gloria")) {
    return "queue";
  }
  return "other";
}

function toneFor(row: ApplicationRow): Tone {
  if (row.outcome === "SEND_BACK" || row.status?.includes("send_back")) {
    return "critical";
  }
  if (row.outcome === "NEEDS_GLORIA" || row.status?.includes("review")) {
    return "attention";
  }
  return "neutral";
}

function statusCopy(row: ApplicationRow) {
  if (row.status?.startsWith("awaiting_gloria_approval")) return "Approve";
  if (row.status?.startsWith("awaiting_gloria_send_back")) return "Send back";
  if (row.status?.startsWith("awaiting_gloria")) return "Flag";
  if (row.status?.startsWith("approved")) return "Approved";
  if (row.status?.startsWith("sent_back")) return "Sent back";
  return "Review";
}

function outcomeCopy(row: ApplicationRow) {
  switch (row.outcome) {
    case "READY_FOR_APPROVAL":
      return "Ready for approval";
    case "NEEDS_GLORIA":
      return "Needs Gloria";
    case "SEND_BACK":
      return "Send back";
    default:
      return row.outcome ?? null;
  }
}

function shortId(id: string) {
  return id.length > 10 ? `${id.slice(0, 8)}…` : id;
}

/** Gloria-facing labels — never show raw rule ids as the primary text. */
const RULE_LABEL: Record<string, { title: string; hint: string }> = {
  "DOC.PRESENT": {
    title: "Missing documents",
    hint: "Required pack is incomplete",
  },
  "PP.MRZ_CHECKSUM": {
    title: "Passport MRZ",
    hint: "Machine zone checksum — re-scan if unclear",
  },
  "PP.MRZ_MATCHES_VIZ": {
    title: "MRZ vs printed name",
    hint: "Compare machine zone to the visual passport page",
  },
  "PP.NOT_EXPIRED": {
    title: "Passport expired",
    hint: "Passport must be valid for travel",
  },
  "PP.VALID_AFTER_DEPARTURE": {
    title: "Passport validity after trip",
    hint: "Must stay valid ≥ 3 months after leaving Schengen",
  },
  "PHOTO.ISO": {
    title: "Photo standard",
    hint: "Open the ID photo (not the passport) and confirm Schengen / ISO rules",
  },
  "BANK.SUFFICIENT_FUNDS": {
    title: "Bank balance too low",
    hint: "Statement balance below required trip funds",
  },
  "BANK.WINDOW": {
    title: "Bank statement too old",
    hint: "Statement date outside the allowed window",
  },
  "BANK.STAMPED": {
    title: "Bank stamp",
    hint: "Confirm the statement is stamped by the bank",
  },
  "ID.NAME_MATCH": {
    title: "Names don’t match",
    hint: "Compare the passport name to the other document — confirm it’s the same person",
  },
  "ID.DOB_MATCH": {
    title: "Birth date",
    hint: "Birth dates differ across documents — confirm which is correct",
  },
  "ID.FORM_MATCHES_PASSPORT": {
    title: "Form vs passport",
    hint: "France-Visas form must match the passport exactly",
  },
  "ID.PASSPORT_NO_MATCH": {
    title: "Passport number",
    hint: "Confirm the passport number matches on each document",
  },
  "EMP.LETTER_FIELDS": {
    title: "Employer letter incomplete",
    hint: "Something required is missing on the employer letter",
  },
  "EMP.LEAVE_COVERS_TRIP": {
    title: "Leave dates",
    hint: "Approved leave must cover the trip dates",
  },
  "EMP.PAYSLIPS_RECENT": {
    title: "Payslips",
    hint: "Need the last 3 recent payslips",
  },
  "SUS.LOW_CONFIDENCE": {
    title: "Unclear field",
    hint: "Open the document and confirm the printed value looks right",
  },
  "SUS.DOC_ANOMALY": {
    title: "Odd-looking document",
    hint: "Something looks unusual — open the page and confirm",
  },
};

const DOC_PLAIN: Record<string, string> = {
  passport: "passport",
  travel_insurance: "insurance certificate",
  application_form: "visa application form",
  employment_letter: "employer letter",
  bank_statement: "bank statement",
  flight_booking: "flight booking",
  hotel_booking: "hotel booking",
  payslip: "payslip",
  photo: "photo",
  family_register: "family register",
  cnss_certificate: "CNSS certificate",
  travel_plan: "travel plan",
};

const FIELD_PLAIN: Record<string, string> = {
  date_of_birth: "birth date",
  issue_date: "issue date",
  passport_number: "passport number",
  position: "job title",
  employee_name: "employee name",
  employer_name: "employer name",
  expiry_date: "expiry date",
  surname: "surname",
  given_names: "given names",
};

type AuditRow = {
  id?: string;
  rule_id?: string;
  status?: string;
  message?: string;
  mode?: string;
  evidence?: Array<{ doc?: string; field?: string; value?: string; page?: number }>;
};

/** Map checklist doc types / missing labels → filename patterns in the pack. */
const DOC_FILE_PATTERNS: Record<string, RegExp> = {
  passport: /passport/i,
  photo: /photo/i,
  employment_letter: /employ/i,
  payslip: /payslip|salary/i,
  bank_statement: /bank/i,
  flight_booking: /flight|ticket|amadeus/i,
  hotel_booking: /hotel|booking|accommodation/i,
  travel_insurance: /insurance|euromed|assurance/i,
  application_form: /application|form|france.?visa/i,
  family_register: /family|ekhraj|kaid/i,
  travel_plan: /travel.?plan|itinerary/i,
  cnss_certificate: /cnss/i,
};

const RULE_DOC_HINT: Record<string, string> = {
  "DOC.PRESENT": "application_form",
  "PP.MRZ_CHECKSUM": "passport",
  "PP.MRZ_MATCHES_VIZ": "passport",
  "PP.NOT_EXPIRED": "passport",
  "PP.VALID_AFTER_DEPARTURE": "passport",
  "PP.ISSUED_WITHIN_10Y": "passport",
  "PHOTO.ISO": "photo",
  "BANK.SUFFICIENT_FUNDS": "bank_statement",
  "BANK.WINDOW": "bank_statement",
  "BANK.STAMPED": "bank_statement",
  "BANK.LARGE_RECENT_DEPOSIT": "bank_statement",
  "ID.NAME_MATCH": "passport",
  "ID.DOB_MATCH": "passport",
  "ID.FORM_MATCHES_PASSPORT": "application_form",
  "ID.PASSPORT_NO_MATCH": "passport",
  "EMP.LETTER_FIELDS": "employment_letter",
  "EMP.LEAVE_COVERS_TRIP": "employment_letter",
  "EMP.PAYSLIPS_RECENT": "payslip",
  "SUS.LOW_CONFIDENCE": "passport",
  "SUS.DOC_ANOMALY": "passport",
};

function findFileForDoc(files: string[], docType: string | undefined): string | null {
  if (!docType || !files.length) return null;
  const key = docType.toLowerCase().replace(/\s+/g, "_");
  // ISO / visa photos — never open the passport biodata page
  if (key === "photo") {
    const idPhoto =
      files.find((f) => /^photo(_\d+)?\./i.test(f)) ??
      files.find((f) => /national[_-]?id|id[_-]?card|id_photo/i.test(f));
    if (idPhoto) return idPhoto;
  }
  // Prefer exact stem (passport.png over passport_phone.jpg)
  const exact = files.find((f) => {
    const stem = f.replace(/\.[^.]+$/, "").toLowerCase();
    return stem === key || stem === key.replaceAll("_", "-");
  });
  if (exact) return exact;
  const re = DOC_FILE_PATTERNS[key];
  if (re) {
    const ranked = files
      .filter((f) => re.test(f) && !(key === "photo" && /passport/i.test(f)))
      .sort((a, b) => a.length - b.length);
    if (ranked[0]) return ranked[0];
  }
  const loose = files.find((f) =>
    f.toLowerCase().includes(key.replaceAll("_", "")),
  );
  return loose ?? null;
}

function fileForMissingLabel(files: string[], label: string): string | null {
  const l = label.toLowerCase();
  if (/photo|iso/.test(l)) return findFileForDoc(files, "photo");
  if (/payslip|salary/.test(l)) return findFileForDoc(files, "payslip");
  if (/passport/.test(l)) return findFileForDoc(files, "passport");
  if (/employ|letter/.test(l)) return findFileForDoc(files, "employment_letter");
  if (/bank/.test(l)) return findFileForDoc(files, "bank_statement");
  if (/flight|ticket/.test(l)) return findFileForDoc(files, "flight_booking");
  if (/hotel|accommodation/.test(l)) return findFileForDoc(files, "hotel_booking");
  if (/insurance/.test(l)) return findFileForDoc(files, "travel_insurance");
  if (/form|france-visas|receipt/.test(l)) return findFileForDoc(files, "application_form");
  if (/family|ekhraj|kaid/.test(l)) return findFileForDoc(files, "family_register");
  if (/travel plan|itinerary/.test(l)) return findFileForDoc(files, "travel_plan");
  if (/cnss/.test(l)) return findFileForDoc(files, "cnss_certificate");
  return null;
}

/** Docs to open for a row — compare rules return passport + conflicting file. */
function filesForIssue(files: string[], row: AuditRow): string[] {
  const ruleId = row.rule_id ?? row.id ?? "";
  if (ruleId === "PHOTO.ISO") {
    const photo = findFileForDoc(files, "photo");
    return photo ? [photo] : [];
  }

  if (ruleId === "ID.NAME_MATCH" || ruleId === "ID.DOB_MATCH") {
    const evidence = row.evidence ?? [];
    const passport = findFileForDoc(files, "passport");
    const out: string[] = [];
    if (passport) out.push(passport);
    const seen = new Set<string>();
    // NAME: every mismatched doc (score < 100); DOB: every non-passport evidence doc
    const scored: { doc: string; score: number }[] = [];
    for (const e of evidence) {
      if (!e.doc || e.doc === "passport" || seen.has(e.doc)) continue;
      const m = String(e.value ?? "").match(/\((\d+(?:\.\d+)?)\)\s*$/);
      const score = m ? Number(m[1]) : ruleId === "ID.NAME_MATCH" ? 100 : 0;
      if (ruleId === "ID.NAME_MATCH" && score >= 100) continue;
      seen.add(e.doc);
      scored.push({ doc: e.doc, score });
    }
    scored.sort((a, b) => a.score - b.score);
    for (const { doc } of scored) {
      const hit = findFileForDoc(files, doc);
      if (hit && !out.includes(hit)) out.push(hit);
    }
    if (out.length) return out;
  }

  const fromEvidence = (row.evidence ?? [])
    .map((e) => e.doc)
    .find((d): d is string => Boolean(d) && d !== "application");
  if (fromEvidence) {
    const hit = findFileForDoc(files, fromEvidence);
    if (hit) return [hit];
  }
  const hint = RULE_DOC_HINT[ruleId];
  if (hint) {
    const hit = findFileForDoc(files, hint);
    if (hit) return [hit];
  }
  return [];
}

function fileForIssue(files: string[], row: AuditRow): string | null {
  return filesForIssue(files, row)[0] ?? null;
}

function ruleCopy(ruleId: string | undefined) {
  if (!ruleId) return { title: "Item to check", hint: "Open the document and confirm" };
  return (
    RULE_LABEL[ruleId] ?? {
      title: "Item to check",
      hint: "Open the document and confirm",
    }
  );
}

function plainDoc(name: string) {
  return DOC_PLAIN[name] ?? name.replaceAll("_", " ");
}

function plainField(name: string) {
  return FIELD_PLAIN[name] ?? name.replaceAll("_", " ");
}

function nameFromEvidenceValue(raw: string | undefined): string {
  if (!raw) return "";
  // Strip trailing match scores like "JEFF GERGES NADER (74.1)"
  return raw.replace(/\s*\(\d+(?:\.\d+)?\)\s*$/, "").trim();
}

/** Gloria-facing body text — no rule ids, field paths, or confidence scores. */
function issuePlain(row: AuditRow): string {
  const ruleId = row.rule_id ?? row.id ?? "";
  const copy = ruleCopy(ruleId);
  const msg = (row.message ?? "").trim();

  if (ruleId === "ID.NAME_MATCH") {
    // Prefer backend message — lists every mismatched doc (flight, bank, insurance, …)
    if (/Passport says/i.test(msg) && /match|check /i.test(msg)) {
      return msg;
    }
    const evidence = row.evidence ?? [];
    const passportName = nameFromEvidenceValue(
      evidence.find((e) => e.doc === "passport")?.value,
    );
    const mismatches: { doc: string; name: string; score: number }[] = [];
    const seen = new Set<string>();
    for (const e of evidence) {
      if (!e.doc || e.doc === "passport" || seen.has(e.doc)) continue;
      const m = String(e.value ?? "").match(/^(.*?)\s*\((\d+(?:\.\d+)?)\)\s*$/);
      const name = nameFromEvidenceValue(e.value);
      const score = m ? Number(m[2]) : 100;
      if (!name || score >= 100) continue;
      seen.add(e.doc);
      mismatches.push({ doc: e.doc, name, score });
    }
    mismatches.sort((a, b) => a.score - b.score);
    if (passportName && mismatches.length) {
      const listed = mismatches
        .map((x) => `${plainDoc(x.doc)} (“${x.name}”)`)
        .join(", ");
      const askFix = mismatches.some((x) => x.score < 70);
      return askFix
        ? `Passport says “${passportName}” — doesn’t match ${listed} — ask applicant to fix`
        : `Passport says “${passportName}” — check ${listed} — confirm it’s the same person`;
    }
    if (/MRZ|Gloria review|variant/i.test(msg)) {
      return copy.hint;
    }
  }

  if (ruleId === "SUS.LOW_CONFIDENCE") {
    // Prefer backend Gloria message when it already names doc + value
    if (/^Unsure about /i.test(msg) && !/confidence|field_meta/i.test(msg)) {
      return msg;
    }
    const evidence = row.evidence ?? [];
    const first = evidence.find((e) => e.doc && e.doc !== "application");
    if (first?.doc && first.field) {
      const shown = String(first.value ?? "").trim();
      const looksLikeScoreOnly = /^0?\.\d+$/.test(shown) || /^confidence=/i.test(shown);
      if (shown && !looksLikeScoreOnly) {
        return (
          `Unsure about ${plainDoc(first.doc)} ${plainField(first.field)} ` +
          `(showing ${shown}) — open the ${plainDoc(first.doc)} and confirm`
        );
      }
      return (
        `Unsure about ${plainDoc(first.doc)} ${plainField(first.field)} ` +
        `— open the ${plainDoc(first.doc)} and confirm the printed value`
      );
    }
    const legacy = [...msg.matchAll(/([a-z_]+)\.([a-z_]+)=([0-9.]+)/gi)];
    if (legacy.length === 1) {
      return (
        `Unsure about ${plainDoc(legacy[0][1])} ${plainField(legacy[0][2])} ` +
        `— open the ${plainDoc(legacy[0][1])} and confirm`
      );
    }
    if (legacy.length > 1) {
      return `Unsure about ${legacy.length} fields — open each document and confirm`;
    }
    return copy.hint;
  }

  const missingField = msg.match(/Missing\s+([a-z_]+)\s+on\s+([a-z_]+)/i);
  if (missingField) {
    return `Couldn’t read the ${plainField(missingField[1])} on the ${plainDoc(missingField[2])} — open it and confirm`;
  }

  const missingFields = msg.match(/Missing fields:\s*(.+)$/i);
  if (missingFields) {
    const fields = missingFields[1]
      .split(",")
      .map((s) => plainField(s.trim()))
      .filter(Boolean);
    return `Missing on this letter: ${fields.join(", ")} — ask the applicant to fix or confirm on the page`;
  }

  if (/mismatch/i.test(msg)) {
    return "Details don’t match across documents — open them and compare";
  }

  if (/manual officer confirmation/i.test(msg)) {
    return copy.hint;
  }

  if (!msg || /^confirm on the document$/i.test(msg)) {
    return copy.hint;
  }

  // Strip leftover technical tokens
  if (/^[A-Z][A-Z0-9_.]+$/.test(msg) || /confidence|field_meta|null/i.test(msg)) {
    return copy.hint;
  }

  return msg;
}

function parseMissingDocs(message: string | undefined): string[] {
  if (!message) return [];
  const m = message.match(/Missing:\s*(.+)$/i);
  if (!m?.[1]) return [];
  return m[1]
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function partitionIssues(results: AuditRow[]) {
  const fails = results.filter((r) => (r.status ?? "").toUpperCase() === "FAIL");
  const youCheck = results.filter((r) => {
    const s = (r.status ?? "").toUpperCase();
    return s === "NEEDS_HUMAN" || r.mode === "manual";
  });
  const present = fails.find(
    (r) => (r.rule_id ?? r.id ?? "") === "DOC.PRESENT",
  );
  const missingDocs = parseMissingDocs(present?.message);
  const mustFix = fails.filter(
    (r) => (r.rule_id ?? r.id ?? "") !== "DOC.PRESENT",
  );
  return { missingDocs, mustFix, youCheck, failCount: fails.length };
}

function outcomePlain(
  outcome: string | null | undefined,
  issues?: ReturnType<typeof partitionIssues>,
) {
  const missingN = issues?.missingDocs.length ?? 0;
  const fixN = issues?.mustFix.length ?? 0;
  const youN = issues?.youCheck.length ?? 0;

  switch (outcome) {
    case "READY_FOR_APPROVAL":
      return {
        title: "Approve",
        auto: "passed" as const,
        body:
          youN > 0
            ? `${youN} look-item${youN === 1 ? "" : "s"} for your eye — then mark ready for TLS.`
            : "Code checks are clear. Confirm look-items, then mark ready for TLS.",
        tone: "neutral" as Tone,
      };
    case "NEEDS_GLORIA":
      return {
        title: "Flag",
        auto: "attention" as const,
        body: `${youN || "Some"} item${youN === 1 ? "" : "s"} need your judgment before this file is ready.`,
        tone: "attention" as Tone,
      };
    case "SEND_BACK": {
      const parts: string[] = [];
      if (missingN) parts.push(`${missingN} missing document${missingN === 1 ? "" : "s"}`);
      if (fixN) parts.push(`${fixN} failed check${fixN === 1 ? "" : "s"}`);
      if (youN) parts.push(`${youN} for your eye`);
      return {
        title: "Send back",
        auto: "failed" as const,
        body: parts.length
          ? `${parts.join(" · ")}. Confirm send-back (draft below).`
          : "Code checks found issues. Confirm send-back to the applicant.",
        tone: "critical" as Tone,
      };
    }
    default:
      return {
        title: "Review",
        auto: "unknown" as const,
        body: "Decide if this file is ready for you to take to TLS.",
        tone: "neutral" as Tone,
      };
  }
}

const AREA_META: {
  id: NavView;
  label: string;
  icon: IconSvgElement;
  title: string;
  action: string;
  listTitle: string;
}[] = [
  {
    id: "queue",
    label: "Queue",
    icon: InboxIcon,
    title: "Review queue",
    action: "Seed case",
    listTitle: "Needs Gloria",
  },
  {
    id: "approved",
    label: "Approved",
    icon: Tick02Icon,
    title: "Approved files",
    action: "Seed case",
    listTitle: "Approved",
  },
  {
    id: "sent_back",
    label: "Sent back",
    icon: SentIcon,
    title: "Sent back",
    action: "Seed case",
    listTitle: "Sent back",
  },
  {
    id: "inbox",
    label: "Inbox",
    icon: Mail01Icon,
    title: "Email inbox",
    action: "Read inbox",
    listTitle: "Pipeline",
  },
  {
    id: "upload",
    label: "Upload",
    icon: File01Icon,
    title: "Upload file pack",
    action: "Audit files",
    listTitle: "Upload",
  },
];

function WorkspaceBlock() {
  return (
    <div
      className={cx(
        ghostButtonMuted,
        "pointer-events-none flex h-9 w-full items-center gap-2 rounded-[var(--rb-r-sm,6px)] px-1.5 text-left",
      )}
    >
      <span className={cx(avatarSquare, "size-6 overflow-hidden")}>
        <Image
          src="/visaref-mark.svg"
          alt=""
          width={24}
          height={24}
          className="size-full"
        />
      </span>
      <span className="min-w-0 flex-1">
        <span className={cx(typeLabel, text1, "block truncate text-[13px]")}>
          VisaRef
        </span>
      </span>
    </div>
  );
}

function NavigationFrame({
  areaId,
  onSelectArea,
  counts,
  onClose,
  collapsed = false,
  onToggleCollapsed,
}: {
  areaId: NavView;
  onSelectArea: (id: NavView) => void;
  counts: Record<NavView, number>;
  onClose?: () => void;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
}) {
  const {
    ref: navRef,
    edges: navEdges,
    onScroll: onNavScroll,
  } = useScrollFade<HTMLElement>();

  return (
    <div
      className={cx(
        sidebarSurface,
        "flex shrink-0 flex-col transition-[width] duration-[160ms] ease-[cubic-bezier(0.2,0,0,1)]",
        collapsed ? "w-14" : "w-[11.5rem]",
      )}
    >
      <div
        className={cx(
          "flex shrink-0 items-center gap-1 py-1.5",
          collapsed ? "flex-col px-1.5" : "px-1.5",
        )}
      >
        {collapsed ? (
          <button
            type="button"
            title="VisaRef"
            aria-label="VisaRef"
            onClick={onToggleCollapsed}
            className={cx(ghostButton, "size-9 justify-center p-0")}
          >
            <span className={cx(avatarSquare, "size-6 overflow-hidden")}>
              <Image
                src="/visaref-mark.svg"
                alt=""
                width={24}
                height={24}
                className="size-full"
              />
            </span>
          </button>
        ) : (
          <div className="min-w-0 flex-1">
            <WorkspaceBlock />
          </div>
        )}
        {onToggleCollapsed ? (
          <button
            type="button"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
            title={collapsed ? "Expand" : "Collapse"}
            onClick={onToggleCollapsed}
            className={cx(ghostButton, iconButtonMd, "size-7 shrink-0")}
          >
            <HugeiconsIcon
              icon={ArrowRight02Icon}
              size={14}
              strokeWidth={1.8}
              className={cx(
                "transition-transform duration-[160ms] ease-[cubic-bezier(0.2,0,0,1)]",
                collapsed ? "" : "rotate-180",
              )}
            />
          </button>
        ) : null}
        {onClose ? (
          <button
            type="button"
            aria-label="Close navigation"
            onClick={onClose}
            className={cx(ghostButton, iconButtonMd, "size-7 shrink-0")}
          >
            <HugeiconsIcon icon={Cancel01Icon} size={14} strokeWidth={1.8} />
          </button>
        ) : null}
      </div>

      <div className="relative min-h-0 flex-1">
        <nav
          ref={navRef}
          onScroll={onNavScroll}
          aria-label="Desk"
          className={cx(
            "h-full overflow-y-auto pb-2",
            collapsed ? "px-1.5" : "px-1.5",
          )}
        >
          {!collapsed ? (
            <p className={cx(navGroupLabel, "pt-1")}>Desk</p>
          ) : (
            <div className="h-1" />
          )}
          <ul className={cx("space-y-0.5", collapsed && "flex flex-col items-center")}>
            {AREA_META.map((item) => (
              <li key={item.id} className={collapsed ? "w-full" : undefined}>
                <button
                  type="button"
                  title={collapsed ? item.label : undefined}
                  aria-label={item.label}
                  aria-current={item.id === areaId ? "page" : undefined}
                  onClick={() => onSelectArea(item.id)}
                  className={cx(
                    navItem,
                    collapsed && "justify-center px-0",
                  )}
                >
                  <HugeiconsIcon
                    icon={item.icon}
                    size={15}
                    strokeWidth={1.8}
                    aria-hidden="true"
                    className="shrink-0 opacity-80"
                  />
                  {!collapsed ? (
                    <>
                      <span className="min-w-0 flex-1 truncate">
                        {item.label}
                      </span>
                      {item.id !== "inbox" && item.id !== "upload" ? (
                        <span className={cx(navCount, "shrink-0")}>
                          {counts[item.id]}
                        </span>
                      ) : null}
                    </>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>

          {!collapsed ? (
            <>
              <p className={navGroupLabel}>Destination</p>
              <ul className="space-y-0.5">
                <li>
                  <span
                    className={cx(
                      navItem,
                      "cursor-default hover:bg-transparent",
                    )}
                  >
                    <HugeiconsIcon
                      icon={PassportIcon}
                      size={15}
                      strokeWidth={1.8}
                      className="shrink-0 opacity-80"
                    />
                    <span className="min-w-0 flex-1 truncate">FR Schengen</span>
                  </span>
                </li>
              </ul>
            </>
          ) : (
            <ul className="mt-1 flex flex-col items-center space-y-0.5">
              <li className="w-full">
                <span
                  title="FR Schengen"
                  className={cx(
                    navItem,
                    "cursor-default justify-center px-0 hover:bg-transparent",
                  )}
                >
                  <HugeiconsIcon
                    icon={PassportIcon}
                    size={15}
                    strokeWidth={1.8}
                    className="shrink-0 opacity-80"
                  />
                </span>
              </li>
            </ul>
          )}
        </nav>
        {!collapsed ? (
          <>
            <div
              aria-hidden="true"
              className={cx(
                fadeTopOnTray,
                "pointer-events-none absolute inset-x-0 top-0 h-8",
                navEdges.start ? "opacity-100" : "opacity-0",
              )}
            />
            <div
              aria-hidden="true"
              className={cx(
                fadeBottomOnTray,
                "pointer-events-none absolute inset-x-0 bottom-0 h-8",
                navEdges.end ? "opacity-100" : "opacity-0",
              )}
            />
          </>
        ) : null}
      </div>

      <div
        className={cx(
          "flex shrink-0 items-center border-t border-neutral-900/8 py-2 dark:border-neutral-100/8",
          collapsed ? "justify-center px-1" : "gap-2 px-2",
        )}
      >
        <span
          title="Gloria"
          className={cx(avatar, "size-7 shrink-0 cursor-default")}
        >
          <span className={cx(avatarFallback, "text-[11px]")}>GL</span>
        </span>
        {!collapsed ? (
          <span className={cx(typeCaption, text3, "min-w-0 truncate")}>
            Gloria
          </span>
        ) : null}
      </div>
    </div>
  );
}

function DocPagePreview({
  applicationId,
  filename,
  compact = false,
}: {
  applicationId: string;
  filename: string;
  compact?: boolean;
}) {
  const [status, setStatus] = useState<"loading" | "ok" | "err">("loading");
  const src = filePagePreviewUrl(applicationId, filename, 1);
  const isPdf = filename.toLowerCase().endsWith(".pdf");

  return (
    <div
      className={cx(
        "flex min-h-0 flex-1 flex-col bg-[var(--rb-bg,white)] dark:bg-neutral-950",
        !compact && "",
      )}
    >
      <div className="flex h-11 shrink-0 items-center gap-2 bg-[#f7f8f8] px-6 dark:bg-neutral-950">
        <span className={cx("text-[12px]/[16px] font-medium", text2, "min-w-0 flex-1 truncate")}>
          {filename}
          {isPdf ? " · page 1" : ""}
        </span>
        <a
          href={filePreviewUrl(applicationId, filename)}
          target="_blank"
          rel="noreferrer"
          className={cx(ghostButtonMuted, buttonSm)}
        >
          Original
        </a>
      </div>
      <div className="relative min-h-0 flex-1 bg-[#f7f8f8] px-6 pb-6 dark:bg-neutral-950">
        {status === "loading" ? (
          <div
            aria-hidden
            className="pointer-events-none absolute inset-2 z-10 flex flex-col gap-2 rounded-[var(--rb-r-sm,6px)] p-3"
          >
            <span className={cx(skeleton, "block h-2.5 w-[40%]")} />
            <span className={cx(skeleton, "mt-1 block h-full min-h-[8rem] w-full")} />
          </div>
        ) : null}
        {status === "err" ? (
          <p className={cx(typeCaption, text3, "px-2 py-6 text-center")}>
            Preview unavailable — open Original
          </p>
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={src}
            alt={filename}
            onLoad={() => setStatus("ok")}
            onError={() => setStatus("err")}
            ref={(el) => {
              if (el?.complete && el.naturalWidth > 0) setStatus("ok");
            }}
            className={cx(
              "relative z-0 mx-auto h-full max-h-full w-full object-contain object-center drop-shadow-[0_0_0.5px_rgb(25_33_35/0.35)] transition-opacity duration-150",
              status === "ok" ? "opacity-100" : "opacity-0",
            )}
          />
        )}
      </div>
    </div>
  );
}

function ApprovalPanel({
  applicationId,
  onDone,
}: {
  applicationId: string;
  onDone: () => void;
}) {
  const qc = useQueryClient();
  const reduceMotion = useReducedMotion();
  const [showTech, setShowTech] = useState(false);
  const [showExecutionGraph, setShowExecutionGraph] = useState(false);
  const detailQuery = useQuery({
    queryKey: ["application", applicationId],
    queryFn: () => fetchApplication(applicationId),
  });

  const meta = detailQuery.data?.meta;
  const audit = detailQuery.data?.report?.audit;
  const outcome = (audit?.outcome ?? meta?.outcome) as string | undefined;
  const results = (audit?.results ?? []) as AuditRow[];
  const issues = partitionIssues(results);
  const lookItems = [
    ...issues.mustFix,
    ...issues.youCheck,
  ];
  const plain = outcomePlain(outcome, issues);
  const draft = audit?.drafts?.[0];
  const files = detailQuery.data?.files ?? [];
  const fileKey = files.join("\0");
  const [previewFiles, setPreviewFiles] = useState<string[]>([]);
  const [previewTick, setPreviewTick] = useState(0);
  const [docsFlash, setDocsFlash] = useState(false);
  /** Look-item verdict: ok = Gloria accepts, fail = human verification failed → send back */
  const [lookVerdict, setLookVerdict] = useState<
    Record<string, "ok" | "fail" | undefined>
  >({});
  const [toEmail, setToEmail] = useState("");
  const docsRef = useRef<HTMLElement | null>(null);
  const previewFile = previewFiles[0] ?? null;
  const hasErrors =
    outcome === "SEND_BACK" ||
    issues.missingDocs.length > 0 ||
    issues.mustFix.length > 0;
  const alreadyDecided =
    Boolean(meta?.status?.startsWith("approved")) ||
    Boolean(meta?.status?.startsWith("sent_back"));
  const youCheckIds = issues.youCheck.map(
    (r, i) => String(r.rule_id ?? r.id ?? `you-${i}`),
  );
  const rejectedLooks = issues.youCheck.filter((r, i) => {
    const id = String(r.rule_id ?? r.id ?? `you-${i}`);
    return lookVerdict[id] === "fail";
  });
  const humanLookFailed = rejectedLooks.length > 0;
  const allYouConfirmed =
    youCheckIds.length === 0 ||
    youCheckIds.every((id) => lookVerdict[id] === "ok");
  const emailOk = /[\w.+-]+@[\w.-]+\.\w+/.test(toEmail.trim());
  // Code FAILs or Gloria marked a look-item Not OK → send-back path
  const showSendBack = hasErrors || humanLookFailed;
  const lookRejectBody =
    humanLookFailed && !hasErrors
      ? [
          "Hello,",
          "",
          "We reviewed your visa file and need the following before we can continue:",
          "",
          ...rejectedLooks.map((r, i) => {
            const copy = ruleCopy(r.rule_id ?? r.id);
            return `${i + 1}. ${copy.title} — ${issuePlain(r)}`;
          }),
          "",
          "Thank you,",
          "Gloria – VisaRef Agency",
        ].join("\n")
      : null;
  const displayDraftBody = lookRejectBody || draft?.body || "";
  // Approve = no code FAILs + every look-item OK (ack only — not auto validation).
  // Send-back = code FAILs (ticks optional) OR Gloria failed a look-item.
  const canApprove =
    !showSendBack && allYouConfirmed && emailOk && Boolean(draft?.body);
  const canSendEmail = emailOk && Boolean(displayDraftBody.trim());
  const draftIsReady =
    Boolean(draft?.body) &&
    (!draft?.rule_ids || draft.rule_ids.length === 0) &&
    !showSendBack;

  const actionMut = useMutation({
    mutationFn: (action: "approve" | "send_back" | "review") =>
      postGloriaAction(
        applicationId,
        action,
        "Gloria",
        draft?.id,
        action === "review" ? undefined : toEmail.trim(),
        action === "send_back" ? lookRejectBody || undefined : undefined,
      ),
    onSuccess: (data, action) => {
      const delivery = data.delivery;
      if (action === "review") {
        toast.success("Still in your queue");
      } else if (delivery?.to) {
        toast.success(
          action === "approve"
            ? `Ready for TLS — emailed ${delivery.to}`
            : `Emailed send-back to ${delivery.to}`,
        );
      } else {
        toast.success(
          action === "approve" ? "Marked ready" : "Send-back sent",
        );
      }
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["application", applicationId] });
      if (action !== "review") onDone();
    },
    onError: (err: Error) => toast.error(err.message),
  });
  const redactMut = useMutation({
    mutationFn: () => redactApplication(applicationId),
    onSuccess: (data) => {
      toast.success(
        `Deleted ${data.deleted_files} sensitive file${data.deleted_files === 1 ? "" : "s"}`,
      );
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["application", applicationId] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  useEffect(() => {
    setLookVerdict({});
  }, [applicationId]);

  useEffect(() => {
    const raw =
      (typeof meta?.applicant_email === "string" && meta.applicant_email) ||
      (typeof meta?.email_sender === "string" && meta.email_sender) ||
      "";
    const m = raw.match(/[\w.+-]+@[\w.-]+\.\w+/);
    setToEmail(m ? m[0] : "");
  }, [applicationId, meta?.applicant_email, meta?.email_sender]);

  const openDocs = useCallback(
    (names: string[] | string | null) => {
      const list = (Array.isArray(names) ? names : names ? [names] : [])
        .filter((f) => files.includes(f))
        .slice(0, 2);
      if (!list.length) return;
      setPreviewFiles(list);
      setPreviewTick((n) => n + 1);
      setDocsFlash(true);
      window.setTimeout(() => setDocsFlash(false), 700);
      // Do NOT scrollIntoView — on stacked layouts that yanks the Decision
      // panel (and every confirm row) off-screen.
    },
    [files],
  );
  const openDoc = openDocs;

  // Demo: always show a document — prefer passport image, else first file
  useEffect(() => {
    if (!files.length) {
      setPreviewFiles([]);
      return;
    }
    setPreviewFiles((cur) => {
      const kept = cur.filter((f) => files.includes(f));
      if (kept.length) return kept;
      const passport = files.find((f) => /passport/i.test(f));
      return [passport ?? files[0]];
    });
    // fileKey tracks membership; files is derived from the same query data
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applicationId, fileKey]);

  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      exit={reduceMotion ? undefined : { opacity: 0, x: 8 }}
      transition={{ duration: 0.22, ease: EASE_OUT }}
      className="flex h-full min-h-0 flex-col"
    >
      <div className="shrink-0 border-b border-[rgb(25_33_35/0.08)] px-6 pt-5 pb-4 dark:border-neutral-100/8">
        <div className="flex items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-2.5">
            <h2 className={cx(typeHeadingSm, text1, "truncate")}>
              {meta?.applicant_name || "Unknown applicant"}
            </h2>
            <button
              type="button"
              onClick={() => setShowExecutionGraph(true)}
              className={cx(
                secondaryButton,
                "h-7 shrink-0 gap-1.5 rounded-[var(--rb-r-sm,6px)] px-2.5 text-[12px]/[16px] font-medium text-[#41494c]",
              )}
              title="Open the agent execution graph for this file"
            >
              <span className="size-1.5 rounded-full bg-[oklch(62%_0.16_145)]" />
              View execution graph
            </button>
          </div>
          <span
            className={cx(
              "inline-flex h-6 shrink-0 items-center gap-1.5 rounded-[6px] border border-[rgb(25_33_35/0.08)] bg-white px-2 text-[12px]/[16px] font-medium dark:border-neutral-100/14 dark:bg-neutral-900",
              TONE[plain.tone],
            )}
          >
            <span aria-hidden className="size-1.5 rounded-full bg-current" />
            {plain.title}
          </span>
        </div>
        <p className={cx("mt-1 text-[13px]/[18px] tabular-nums", text3, "truncate")}>
          {meta?.trip_summary || "Trip pending"}
        </p>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto xl:grid xl:grid-rows-[minmax(0,1fr)] xl:overflow-hidden">
        {detailQuery.isLoading ? (
          <section className={cx(panel, "m-6")} aria-busy="true" aria-label="Loading file">
            <div className={cx(panelHead, "h-10")}>
              <span className={cx(skeleton, "h-5 w-20")} />
              <span className={cx(skeleton, "h-4 w-24")} />
            </div>
            <div className={cx(panelBody, "space-y-3 p-4")}>
              <span className={cx(skeleton, "block h-4 w-[80%] max-w-[280px]")} />
              <span className={cx(skeleton, "block h-3 w-[66%] max-w-[200px]")} />
              <div className="space-y-2 pt-1">
                {[0.9, 0.7, 0.5].map((op, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2"
                    style={{ opacity: op }}
                  >
                    <span className={cx(skeleton, "size-3.5 shrink-0")} />
                    <span className={cx(skeleton, "h-2.5 flex-1")} />
                  </div>
                ))}
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <span className={cx(skeleton, "h-7 w-20")} />
                <span className={cx(skeleton, "h-7 w-24")} />
              </div>
            </div>
          </section>
        ) : (
          <div className="grid min-h-0 grid-cols-[minmax(0,1fr)] xl:grid-cols-[minmax(0,1.12fr)_minmax(0,1fr)] xl:grid-rows-[minmax(0,1fr)] xl:divide-x xl:divide-[rgb(25_33_35/0.08)] dark:divide-neutral-100/8">
            <div className="flex flex-col bg-white [scrollbar-width:thin] dark:bg-neutral-950 xl:min-h-0 xl:overflow-y-auto">
            <section className="relative flex shrink-0 flex-col">
              <div className={cx(paneHead, "sticky top-0 z-20")}>
                <span className={paneTitle}>Decision</span>
                <span className={inkSlot}>Your call</span>
              </div>
              <div className="flex min-w-0 flex-col">
                <div className="flex items-start gap-3 px-6 pt-5 pb-4">
                  <span
                    aria-hidden
                    className={cx(
                      "flex size-6 shrink-0 items-center justify-center rounded-full",
                      plain.auto === "failed"
                        ? "bg-[oklch(58%_0.19_26/0.09)]"
                        : plain.auto === "attention"
                          ? "bg-[oklch(75%_0.14_75/0.16)]"
                          : "bg-[rgb(25_33_35/0.05)]",
                    )}
                  >
                  <HugeiconsIcon
                    icon={
                      plain.auto === "failed"
                        ? Alert02Icon
                        : CheckmarkCircle02Icon
                    }
                    size={14}
                    className={cx(
                      "shrink-0",
                      plain.auto === "failed"
                        ? statusFail
                        : plain.auto === "attention"
                          ? statusWarn
                          : statusOk,
                    )}
                  />
                  </span>
                  <div className="min-w-0">
                    <p className={cx("text-[14px]/[24px] font-semibold tracking-[-0.005em]", text1)}>
                      {plain.auto === "passed"
                        ? "Automated checks passed"
                        : plain.auto === "failed"
                          ? "Automated checks failed"
                          : plain.auto === "attention"
                            ? "Needs your judgment"
                            : "Review required"}
                    </p>
                    <p className={cx("text-[13px]/[20px]", text3, "text-pretty")}>
                      {plain.body}
                    </p>
                  </div>
                </div>

                {issues.missingDocs.length > 0 ||
                issues.mustFix.length > 0 ||
                issues.youCheck.length > 0 ? (
                  <div className={cx(hairT, "flex flex-col gap-3 pt-3 pb-3")}>
                    {issues.missingDocs.length > 0 ? (
                      <div>
                        <p className={groupHead}>
                          Missing from pack
                          <span className={groupCount}>{issues.missingDocs.length}</span>
                        </p>
                        <ul>
                          {issues.missingDocs.map((label) => {
                            const linked = fileForMissingLabel(files, label);
                            return (
                              <li key={label}>
                                <button
                                  type="button"
                                  disabled={!linked}
                                  onClick={() => openDoc(linked)}
                                  className={cx(
                                    checkRow,
                                    linked
                                      ? cx(
                                          hoverFill,
                                          pressedFill,
                                          transition,
                                          focusRingInset,
                                          "cursor-pointer",
                                        )
                                      : "cursor-default opacity-90",
                                  )}
                                >
                                  <span className={issueGlyph} aria-hidden />
                                  <span className="min-w-0 flex-1">
                                    <span className={cx(typeRowTitle, text1, "block")}>
                                      {label}
                                    </span>
                                    <span
                                      className={cx(
                                        checkHint,
                                      )}
                                    >
                                      {linked
                                        ? "Open related file in Docs"
                                        : "Ask applicant to upload this document"}
                                    </span>
                                  </span>
                                  <span className="sr-only">
                                    Missing
                                  </span>
                                </button>
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    ) : null}

                    {issues.mustFix.length > 0 ? (
                      <div>
                        <p className={groupHead}>
                          Ask applicant to fix
                          <span className={groupCount}>{issues.mustFix.length}</span>
                        </p>
                        <ul>
                          {issues.mustFix.map((r, i) => {
                            const id = String(r.rule_id ?? r.id ?? i);
                            const copy = ruleCopy(r.rule_id ?? r.id);
                            const linked = filesForIssue(files, r);
                            return (
                              <li key={id}>
                                <button
                                  type="button"
                                  disabled={!linked.length}
                                  onClick={() => openDocs(linked)}
                                  className={cx(
                                    checkRow,
                                    linked.length
                                      ? cx(
                                          hoverFill,
                                          pressedFill,
                                          transition,
                                          focusRingInset,
                                          "cursor-pointer",
                                        )
                                      : "cursor-default",
                                  )}
                                >
                                  <span className={issueGlyph} aria-hidden />
                                  <span className="min-w-0 flex-1">
                                    <span className={cx(typeRowTitle, text1, "block")}>
                                      {copy.title}
                                    </span>
                                    <span
                                      className={cx(
                                        checkHint,
                                      )}
                                    >
                                    {issuePlain(r)}
                                      {linked.length ? " · tap to open" : ""}
                                    </span>
                                </span>
                                <span className="sr-only">
                                    Fix
                                  </span>
                                </button>
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    ) : null}

                    {issues.youCheck.length > 0 ? (
                      <div>
                        <p className={groupHead}>
                          {hasErrors ? "Also look" : "Look with your eye"}
                          <span className={groupCount}>
                            {
                              youCheckIds.filter((id) => Boolean(lookVerdict[id]))
                                .length
                            }
                            /{issues.youCheck.length}
                          </span>
                        </p>
                        <ul>
                          {issues.youCheck.map((r, i) => {
                            const id = String(r.rule_id ?? r.id ?? `you-${i}`);
                            const copy = ruleCopy(r.rule_id ?? r.id);
                            const linked = filesForIssue(files, r);
                            const verdict = lookVerdict[id];
                            const setVerdict = (v: "ok" | "fail") => {
                              // Toggle only — do not open docs (that felt like the row vanished)
                              setLookVerdict((prev) => ({
                                ...prev,
                                [id]: prev[id] === v ? undefined : v,
                              }));
                            };
                            return (
                              <li key={id}>
                                <div
                                  className={cx(
                                    checkRow,
                                    "items-center transition-[opacity,background-color] duration-[120ms]",
                                    verdict === "ok" &&
                                      "bg-[rgb(47_107_74/0.06)] opacity-75 dark:bg-[rgb(47_107_74/0.12)]",
                                    verdict === "fail" &&
                                      "bg-[rgb(155_61_61/0.06)] dark:bg-[rgb(155_61_61/0.12)]",
                                    !verdict &&
                                      "hover:bg-[rgb(25_33_35/0.025)] dark:hover:bg-neutral-100/[0.03]",
                                  )}
                                >
                                  <button
                                    type="button"
                                    disabled={!linked.length}
                                    onClick={() => openDocs(linked)}
                                    className={cx(
                                      "min-w-0 flex-1 text-left",
                                      linked.length
                                        ? cx(transition, "cursor-pointer")
                                        : "cursor-default",
                                    )}
                                  >
                                    <span
                                      className={cx(
                                        typeRowTitle,
                                        text1,
                                        "block",
                                        verdict === "ok" &&
                                          "text-[#2f6b4a] dark:text-[oklch(72%_0.08_150)]",
                                        verdict === "fail" && "text-[#9b3d3d]",
                                      )}
                                    >
                                      {copy.title}
                                      {verdict === "ok" ? (
                                        <span className="ms-2 text-[12px] font-medium opacity-80">
                                          · checked
                                        </span>
                                      ) : null}
                                      {verdict === "fail" ? (
                                        <span className="ms-2 text-[12px] font-medium opacity-80">
                                          · send back
                                        </span>
                                      ) : null}
                                    </span>
                                    <span
                                      className={cx(
                                        checkHint,
                                        verdict === "ok" && "line-through opacity-70",
                                      )}
                                    >
                                      {issuePlain(r)}
                                    </span>
                                  </button>
                                  <div
                                    role="group"
                                    aria-label={`${copy.title} verdict`}
                                    className="inline-flex h-7 shrink-0 overflow-hidden rounded-[5px] border border-[rgb(25_33_35/0.12)] dark:border-neutral-100/16"
                                  >
                                    <button
                                      type="button"
                                      aria-pressed={verdict === "ok"}
                                      aria-label={
                                        verdict === "ok"
                                          ? `Checked — ${copy.title}. Click to clear`
                                          : `Accept ${copy.title}`
                                      }
                                      title={
                                        verdict === "ok"
                                          ? "Checked — click to clear"
                                          : "Looks fine"
                                      }
                                      onClick={() => setVerdict("ok")}
                                      className={cx(
                                        "flex w-7 cursor-pointer items-center justify-center border-r border-[rgb(25_33_35/0.12)] transition-colors duration-[120ms] dark:border-neutral-100/16",
                                        focusRingInset,
                                        verdict === "ok"
                                          ? "bg-[#2f6b4a] text-white"
                                          : "bg-white text-[#2f6b4a]/55 hover:bg-[rgb(47_107_74/0.08)] hover:text-[#2f6b4a] dark:bg-neutral-950 dark:hover:bg-[rgb(47_107_74/0.18)]",
                                      )}
                                    >
                                      <HugeiconsIcon
                                        icon={Tick02Icon}
                                        size={12}
                                        strokeWidth={2.5}
                                      />
                                    </button>
                                    <button
                                      type="button"
                                      aria-pressed={verdict === "fail"}
                                      aria-label={`Reject ${copy.title} — send back`}
                                      title="Not fine — send back"
                                      onClick={() => setVerdict("fail")}
                                      className={cx(
                                        "flex w-7 cursor-pointer items-center justify-center transition-colors duration-[120ms]",
                                        focusRingInset,
                                        verdict === "fail"
                                          ? "bg-[#9b3d3d] text-white"
                                          : "bg-white text-[#9b3d3d]/55 hover:bg-[rgb(155_61_61/0.08)] hover:text-[#9b3d3d] dark:bg-neutral-950 dark:hover:bg-[rgb(155_61_61/0.18)]",
                                      )}
                                    >
                                      <HugeiconsIcon
                                        icon={Cancel01Icon}
                                        size={11}
                                        strokeWidth={2}
                                      />
                                    </button>
                                  </div>
                                </div>
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <p className={cx(typeBodySm, text2, hairT, "px-6 py-4")}>
                    No issues — approve if the file looks complete.
                  </p>
                )}

                <div className={cx(hairT, "px-6 py-1.5")}>
                  <button
                    type="button"
                    aria-expanded={showTech}
                    onClick={() => setShowTech((v) => !v)}
                    className={disclosureRow}
                  >
                    <span
                      className={cx(
                        "text-[10px] text-[#5c6568] transition-transform duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)]",
                        showTech && "rotate-90",
                      )}
                    >
                      ▸
                    </span>
                    {showTech ? "Hide audit" : "Show audit"}
                  </button>
                  {showTech ? (
                    <pre
                      tabIndex={0}
                      className={cx(
                        toolWell,
                        toolOutput,
                        "mt-1 mb-2 max-h-36 overflow-auto",
                      )}
                    >
                      {JSON.stringify(
                        {
                          outcome,
                          look_items: lookItems.map((r) => ({
                            rule: r.rule_id ?? r.id,
                            status: r.status,
                          })),
                        },
                        null,
                        2,
                      )}
                    </pre>
                  ) : null}
                </div>
              </div>
              {!alreadyDecided ? (
                <div className="sticky bottom-0 z-10 flex flex-col gap-2 border-t border-[rgb(25_33_35/0.08)] bg-white px-6 pt-3 pb-4 shadow-[0_-8px_16px_-12px_rgb(25_33_35/0.12)] dark:border-neutral-100/8 dark:bg-neutral-950">
                  <div className="flex min-w-0 items-end gap-2">
                  <label className="flex min-w-0 flex-1 flex-col gap-1.5">
                    <span className={cx("text-[12px]/[16px] font-medium", text3)}>
                      Send to (applicant email)
                    </span>
                    <input
                      type="email"
                      value={toEmail}
                      onChange={(e) => setToEmail(e.target.value)}
                      placeholder="applicant@email.com"
                      className={cx(
                        "h-9 w-full rounded-[var(--rb-r-sm,6px)] border border-[rgb(25_33_35/0.14)] bg-white px-3 text-[13px] text-[#192123] outline-none transition-[border-color,box-shadow] duration-[120ms] placeholder:text-[#5c6568]/70 focus-visible:border-[rgb(25_33_35/0.4)] focus-visible:shadow-[0_0_0_3px_rgb(25_33_35/0.06)] dark:border-neutral-100/20 dark:bg-neutral-950 dark:text-neutral-100",
                      )}
                    />
                  </label>
                  <div className="flex shrink-0 items-center justify-end gap-2">
                    <button
                      type="button"
                      className={cx(secondaryButton, buttonSm, "h-9")}
                      disabled={actionMut.isPending}
                      onClick={() => actionMut.mutate("review")}
                    >
                      Flag
                    </button>
                    {showSendBack ? (
                      <button
                        type="button"
                        className={cx(primaryButton, buttonSm, "h-9 px-3.5")}
                        disabled={actionMut.isPending || !canSendEmail}
                        onClick={() => actionMut.mutate("send_back")}
                        title="SMTP the draft below to this address"
                      >
                        {actionMut.isPending ? (
                          <HugeiconsIcon
                            icon={Loading03Icon}
                            size={12}
                            className="animate-spin"
                          />
                        ) : (
                          <HugeiconsIcon icon={Mail01Icon} size={12} />
                        )}
                        Send email
                      </button>
                    ) : (
                      <button
                        type="button"
                        className={cx(primaryButton, buttonSm, "h-9 px-3.5")}
                        disabled={actionMut.isPending || !canApprove}
                        onClick={() => actionMut.mutate("approve")}
                        title="Mark ready + SMTP the ready draft"
                      >
                        {actionMut.isPending ? (
                          <HugeiconsIcon
                            icon={Loading03Icon}
                            size={12}
                            className="animate-spin"
                          />
                        ) : (
                          <HugeiconsIcon icon={Mail01Icon} size={12} />
                        )}
                        Approve & email
                      </button>
                    )}
                  </div>
                  </div>
                  {!emailOk ? (
                    <p className={cx(typeCaption, "flex items-start gap-2 text-[#737c7f] dark:text-neutral-100/55")}>
                      <span aria-hidden className="mt-[5px] size-1.5 shrink-0 rounded-full bg-[oklch(72%_0.15_70)]" />
                      Enter the correspondent email — the button sends SMTP from your Gmail
                    </p>
                  ) : null}
                  {humanLookFailed ? (
                    <p className={cx(typeCaption, "flex items-start gap-2 text-[#737c7f] dark:text-neutral-100/55")}>
                      <span aria-hidden className="mt-[5px] size-1.5 shrink-0 rounded-full bg-[oklch(51%_0.18_26)]" />
                      You marked look-item(s) Not OK — Send email asks the applicant to fix
                    </p>
                  ) : null}
                  {!showSendBack && !allYouConfirmed ? (
                    <p className={cx(typeCaption, "flex items-start gap-2 text-[#737c7f] dark:text-neutral-100/55")}>
                      <span aria-hidden className="mt-[5px] size-1.5 shrink-0 rounded-full bg-[oklch(72%_0.15_70)]" />
                      Check each look-item to Approve, or ✕ to send back
                    </p>
                  ) : null}
                </div>
              ) : (
                <div className={cx(panelFoot, hairT, "flex-wrap px-6")}>
                  <p className={cx(typeBodySm, text2)}>
                    {meta?.human_action || meta?.status}
                  </p>
                  {meta?.status === "approved_by_gloria" &&
                  !meta?.sensitive_data_redacted ? (
                    <button
                      type="button"
                      className={cx(secondaryButton, buttonSm, "text-red-700 dark:text-red-300")}
                      disabled={redactMut.isPending}
                      onClick={() => {
                        if (
                          window.confirm(
                            "Delete the applicant documents, reports, contact details, and extracted personal data? The approved record will remain.",
                          )
                        ) {
                          redactMut.mutate();
                        }
                      }}
                    >
                      {redactMut.isPending ? "Deleting…" : "Delete sensitive data"}
                    </button>
                  ) : null}
                </div>
              )}
            </section>

            {displayDraftBody ? (
              <section
                id="applicant-draft"
                className={cx(hairT, "flex shrink-0 flex-col bg-white dark:bg-neutral-950")}
              >
                <div className="flex h-12 min-w-0 items-center gap-2 px-6">
                  <span className={cx("text-[13px]/[20px]", text3)}>Draft</span>
                  <span aria-hidden className={cx("text-[13px]/[20px]", text3)}>/</span>
                  <span className={cx(paneTitle, "flex-1")}>
                    {draftIsReady
                      ? "Ready-for-TLS message"
                      : humanLookFailed && !hasErrors
                        ? "Send-back (your look rejects)"
                        : "Send-back message"}
                  </span>
                  <span className={cx(tag, tagOk, "uppercase tracking-[0.04em]")}>
                    {draft?.status || "DRAFT"}
                  </span>
                </div>
                <div className="mx-6 mb-6 flex min-w-0 flex-col rounded-[8px] border border-[rgb(25_33_35/0.08)] px-5 pt-5 pb-4 dark:border-neutral-100/8">
                  <pre
                    className={cx(
                      "text-[13px]/[1.6]",
                      text1,
                      "whitespace-pre-wrap font-sans",
                    )}
                  >
                    {displayDraftBody}
                  </pre>
                  <p className={cx(typeCaption, text3, hairT, "mt-4 pt-3")}>
                    {emailOk
                      ? `Confirm above emails this to ${toEmail.trim()} via Gmail SMTP.`
                      : "Enter the applicant email above — confirm sends it directly."}
                  </p>
                </div>
              </section>
            ) : null}
            </div>
            <div className="flex min-h-[32rem] flex-col bg-white dark:bg-neutral-950 xl:min-h-0">
            {files.length > 0 ? (
              <section
                ref={docsRef}
                className={cx(
                  "flex h-full min-h-0 flex-1 flex-col transition-[box-shadow] duration-300",
                  docsFlash &&
                    "shadow-[inset_0_0_0_2px_rgb(25_33_35/0.14)] dark:shadow-[inset_0_0_0_2px_rgb(255_255_255/0.14)]",
                )}
              >
                <div className={paneHead}>
                  <span className={paneTitle}>
                    Images &amp; PDFs
                  </span>
                  <span className={cx(inkSlot, "me-auto")}>Docs</span>
                  <span className={countPill}>
                    {files.length}
                  </span>
                </div>
                <div className="flex min-h-0 flex-1 flex-col">
                  <ul className="flex shrink-0 gap-1.5 overflow-x-auto border-b border-[rgb(25_33_35/0.08)] px-6 py-3 dark:border-neutral-100/8 [scrollbar-width:none] [mask-image:linear-gradient(to_right,black_calc(100%-32px),transparent)]">
                    {files.map((f) => (
                      <li key={f} className="shrink-0">
                        <button
                          type="button"
                          onClick={() => openDocs(f)}
                          className={cx(
                            docChip,
                            hoverFill,
                            pressedFill,
                            transition,
                            focusRing,
                            "max-w-[11rem] cursor-pointer truncate",
                            previewFiles.includes(f) &&
                              "border-[#192123] text-[#192123] dark:border-neutral-100/70 dark:text-neutral-100",
                          )}
                        >
                          {f}
                        </button>
                      </li>
                    ))}
                  </ul>
                  {previewFiles.length > 1 ? (
                    <div
                      key={`compare:${previewFiles.join("|")}:${previewTick}`}
                      className="flex min-h-0 flex-1 flex-col border-t border-neutral-900/8 dark:border-neutral-100/8"
                    >
                      <p
                        className={cx(
                          typeCaption,
                          text3,
                          "shrink-0 px-3 py-1.5",
                        )}
                      >
                        Compare
                      </p>
                      <div className="flex min-h-0 flex-1 flex-col gap-px overflow-y-auto bg-neutral-900/8 dark:bg-neutral-100/8">
                        {previewFiles.map((f) => (
                          <div
                            key={`${f}:${previewTick}`}
                            className="flex min-h-[12rem] flex-1 flex-col"
                          >
                            <DocPagePreview
                              applicationId={applicationId}
                              filename={f}
                              compact
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : previewFile ? (
                    <DocPagePreview
                      key={`${previewFile}:${previewTick}`}
                      applicationId={applicationId}
                      filename={previewFile}
                    />
                  ) : null}
                </div>
              </section>
            ) : null}

            </div>
          </div>
        )}
      </div>
      {showExecutionGraph ? (
        <AgentExecutionGraph
          applicationId={applicationId}
          applicantName={meta?.applicant_name}
          onClose={() => setShowExecutionGraph(false)}
        />
      ) : null}
    </motion.div>
  );
}

export default function VisaRefShell() {
  const qc = useQueryClient();
  const reduceMotion = useReducedMotion();
  const [areaId, setAreaId] = useState<NavView>("queue");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [graphFor, setGraphFor] = useState<{ id: string; name: string | null } | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerShown, setDrawerShown] = useState(false);
  const [navCollapsed, setNavCollapsed] = useState(false);
  const {
    ref: contentRef,
    edges: contentEdges,
    onScroll: onContentScroll,
  } = useScrollFade<HTMLElement>();
  const shouldFocusRef = useRef(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLDivElement>(null);

  const listQuery = useQuery({
    queryKey: ["applications"],
    queryFn: fetchApplications,
    refetchInterval: 8_000,
  });

  const rows = listQuery.data ?? [];
  const counts = useMemo(
    () => ({
      queue: rows.filter((r) => bucket(r) === "queue").length,
      approved: rows.filter((r) => bucket(r) === "approved").length,
      sent_back: rows.filter((r) => bucket(r) === "sent_back").length,
      inbox: 0,
      upload: 0,
    }),
    [rows],
  );

  const filtered = useMemo(() => {
    if (areaId === "inbox" || areaId === "upload") return [];
    const list = rows.filter((r) => bucket(r) === areaId);
    // Ready-to-approve first, then review, then the rest
    const rank = (r: ApplicationRow) => {
      if (r.status?.includes("approval")) return 0;
      if (r.status?.includes("review")) return 1;
      if (r.status?.includes("send_back")) return 2;
      return 3;
    };
    return [...list].sort((a, b) => rank(a) - rank(b));
  }, [rows, areaId]);

  const area = AREA_META.find((a) => a.id === areaId) ?? AREA_META[0];

  const seedMut = useMutation({
    mutationFn: (caseId: string) => postSeedCase(caseId),
    onSuccess: (data, caseId) => {
      const id = String(data.id ?? "");
      const label =
        caseId === "case11_insufficient_funds"
          ? "Bank failure"
          : caseId === "case04_name_mismatch"
            ? "Name mismatch"
            : "Complete case";
      toast.success(id ? `${label} · ${shortId(id)}` : `${label} seeded`);
      qc.invalidateQueries({ queryKey: ["applications"] });
      setAreaId("queue");
      if (id) setSelectedId(id);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const inboxMut = useMutation({
    mutationFn: postEmailInboxRead,
    onSuccess: () => {
      toast.success("Inbox processed");
      qc.invalidateQueries({ queryKey: ["applications"] });
      setAreaId("queue");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const uploadInputRef = useRef<HTMLInputElement>(null);

  const uploadMut = useMutation({
    mutationFn: (files: File[]) => uploadAndAudit(files),
    onSuccess: (data) => {
      toast.success(`Audited · ${shortId(data.id)}`);
      setUploadFiles([]);
      if (uploadInputRef.current) uploadInputRef.current.value = "";
      qc.invalidateQueries({ queryKey: ["applications"] });
      setAreaId("queue");
      setSelectedId(data.id);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const primaryAction = () => {
    if (areaId === "inbox") inboxMut.mutate();
    else if (areaId === "upload") {
      if (uploadFiles.length) uploadMut.mutate(uploadFiles);
      else uploadInputRef.current?.click();
    } else seedMut.mutate("case01_complete");
  };
  const primaryBusy =
    seedMut.isPending || inboxMut.isPending || uploadMut.isPending;

  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      const view = rootRef.current?.ownerDocument.defaultView ?? window;
      if (view.matchMedia("(max-width: 1023px)").matches) setDrawerOpen(true);
    });
    return () => cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (!drawerOpen) return;
    const drawer = drawerRef.current;
    const doc = drawer?.ownerDocument ?? document;
    const frame = requestAnimationFrame(() => setDrawerShown(true));
    const getFocusable = () =>
      Array.from(
        drawer?.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      ).filter((el) => !el.hasAttribute("disabled"));

    if (shouldFocusRef.current) {
      getFocusable()[0]?.focus({ preventScroll: true });
      shouldFocusRef.current = false;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setDrawerOpen(false);
        setDrawerShown(false);
        triggerRef.current?.focus({ preventScroll: true });
      }
    };
    doc.addEventListener("keydown", onKeyDown);
    return () => {
      cancelAnimationFrame(frame);
      doc.removeEventListener("keydown", onKeyDown);
    };
  }, [drawerOpen]);

  const closeDrawer = () => {
    setDrawerOpen(false);
    setDrawerShown(false);
    triggerRef.current?.focus({ preventScroll: true });
  };

  return (
    <div
      ref={rootRef}
      className={cx(
        canvas,
        text1,
        "relative flex h-full min-h-[720px] w-full overflow-hidden",
      )}
    >
      <aside className="hidden shrink-0 lg:flex">
        <NavigationFrame
          areaId={areaId}
          onSelectArea={(id) => {
            setAreaId(id);
            setSelectedId(null);
          }}
          counts={counts}
          collapsed={navCollapsed}
          onToggleCollapsed={() => setNavCollapsed((v) => !v)}
        />
      </aside>

      <div className={cx(pageFog, "flex min-w-0 flex-1 flex-col")}>
        <header
          className={cx(topBar, "flex h-14 shrink-0 items-center gap-2 px-4 sm:px-6")}
        >
          <button
            ref={triggerRef}
            type="button"
            aria-label="Open navigation"
            aria-expanded={drawerOpen}
            onClick={() => {
              shouldFocusRef.current = true;
              setDrawerOpen(true);
            }}
            className={cx(ghostButton, iconButtonMd, "lg:hidden")}
          >
            <HugeiconsIcon icon={Menu01Icon} size={16} strokeWidth={1.8} />
          </button>

          <div className="min-w-0 flex-1">
            <h1 className={cx(typeHeadingXs, text1, "truncate")}>{area.title}</h1>
          </div>

          <button
            type="button"
            className={cx(ghostButton, iconButtonMd)}
            aria-label="Refresh"
            onClick={() => listQuery.refetch()}
          >
            <HugeiconsIcon
              icon={RefreshIcon}
              size={16}
              strokeWidth={1.8}
              className={listQuery.isFetching ? "animate-spin" : undefined}
            />
          </button>

          <button
            type="button"
            className={cx(primaryButton, buttonMd)}
            disabled={primaryBusy}
            onClick={primaryAction}
          >
            {primaryBusy ? (
              <HugeiconsIcon icon={Loading03Icon} size={14} className="animate-spin" />
            ) : areaId === "inbox" ? (
              <HugeiconsIcon icon={Mail01Icon} size={14} />
            ) : areaId === "upload" ? (
              <HugeiconsIcon icon={File01Icon} size={14} />
            ) : (
              <HugeiconsIcon icon={File01Icon} size={14} />
            )}
            {area.action}
          </button>
        </header>

        <div className="flex min-h-0 flex-1 flex-col p-2">
          <div className={cx(frame, "min-h-0 flex-1")}>
            {areaId === "inbox" ? (
              <main className="flex h-full flex-col items-start justify-center gap-4 p-6 sm:p-10">
                <motion.div
                  initial={reduceMotion ? false : { opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.28, ease: EASE_OUT }}
                  className="max-w-lg"
                >
                  <p className={cx(typeCaption, text3)}>Email pipeline</p>
                  <h2 className={cx(typeHeadingSm, "mt-2")}>
                    Pull Jeff&apos;s inbox
                  </h2>
                  <p className={cx(typeBodySm, text2, "mt-3")}>
                    Subject filter → attachments → OCR/MRZ → Llama extract → TLS rules.
                    Approval stays on Gloria&apos;s click.
                  </p>
                  <div className="mt-6 flex flex-wrap gap-2">
                    <button
                      type="button"
                      className={cx(primaryButton, buttonLg)}
                      disabled={inboxMut.isPending}
                      onClick={() => inboxMut.mutate()}
                    >
                      {inboxMut.isPending ? (
                        <HugeiconsIcon
                          icon={Loading03Icon}
                          size={16}
                          className="animate-spin"
                        />
                      ) : (
                        <HugeiconsIcon icon={Mail01Icon} size={16} />
                      )}
                      Read inbox now
                    </button>
                    <button
                      type="button"
                      className={cx(secondaryButton, buttonLg)}
                      onClick={() => setAreaId("queue")}
                    >
                      Back to queue
                    </button>
                  </div>
                </motion.div>
              </main>
            ) : areaId === "upload" ? (
              <main className="flex h-full flex-col items-start justify-center gap-4 p-6 sm:p-10">
                <motion.div
                  initial={reduceMotion ? false : { opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.28, ease: EASE_OUT }}
                  className="max-w-lg"
                >
                  <p className={cx(typeCaption, text3)}>File pack</p>
                  <h2 className={cx(typeHeadingSm, "mt-2")}>
                    Upload &amp; audit
                  </h2>
                  <p className={cx(typeBodySm, text2, "mt-3")}>
                    Drop PDFs or passport images. VisaRef extracts fields, runs
                    the checklist, then waits for your Approve / Send back.
                  </p>
                  <input
                    ref={uploadInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
                    className="sr-only"
                    onChange={(e) =>
                      setUploadFiles(Array.from(e.target.files ?? []))
                    }
                  />
                  <button
                    type="button"
                    className={cx(
                      panel,
                      hoverFill,
                      pressedFill,
                      transition,
                      focusRing,
                      "mt-5 w-full cursor-pointer p-4 text-left",
                    )}
                    onClick={() => uploadInputRef.current?.click()}
                  >
                    <span className={cx(typeLabel, text1)}>
                      {uploadFiles.length
                        ? `${uploadFiles.length} file${uploadFiles.length === 1 ? "" : "s"} selected`
                        : "Choose PDF / PNG / JPG"}
                    </span>
                    {uploadFiles.length > 0 ? (
                      <ul className={cx(typeCaption, text3, "mt-2 space-y-0.5")}>
                        {uploadFiles.slice(0, 8).map((f) => (
                          <li key={f.name + f.size} className="truncate">
                            {f.name}
                          </li>
                        ))}
                        {uploadFiles.length > 8 ? (
                          <li>+{uploadFiles.length - 8} more</li>
                        ) : null}
                      </ul>
                    ) : (
                      <span className={cx(typeCaption, text3, "mt-1 block")}>
                        Multi-select the full visa pack
                      </span>
                    )}
                  </button>
                  <div className="mt-6 flex flex-wrap gap-2">
                    <button
                      type="button"
                      className={cx(primaryButton, buttonLg)}
                      disabled={uploadMut.isPending || uploadFiles.length === 0}
                      onClick={() => uploadMut.mutate(uploadFiles)}
                    >
                      {uploadMut.isPending ? (
                        <HugeiconsIcon
                          icon={Loading03Icon}
                          size={16}
                          className="animate-spin"
                        />
                      ) : (
                        <HugeiconsIcon icon={File01Icon} size={16} />
                      )}
                      Run audit
                    </button>
                    <button
                      type="button"
                      className={cx(secondaryButton, buttonLg)}
                      onClick={() => setAreaId("queue")}
                    >
                      Back to queue
                    </button>
                  </div>
                </motion.div>
              </main>
            ) : (
              <div className="flex h-full min-h-0 flex-col">
                {/* One surface: queue | gate — the page title lives once, in the top bar */}
                <div className="grid min-h-0 flex-1 lg:grid-cols-[minmax(0,332px)_minmax(0,1fr)] xl:grid-cols-[minmax(0,376px)_minmax(0,1fr)]">
                  <div className="flex min-h-0 flex-col border-b border-[rgb(25_33_35/0.08)] lg:border-r lg:border-b-0 dark:border-neutral-100/8">
                    <div className={cx(paneHead, "px-5")}>
                      <span className={paneTitle}>Files</span>
                      <span className={cx(typeCaption, text3, "me-auto")}>
                        {listQuery.isLoading ? "…" : `${filtered.length} in view`}
                      </span>
                      <span className={inkSlot}>{area.listTitle}</span>
                    </div>
                    <div className="relative min-h-0 flex-1">
                    <main
                      ref={contentRef}
                      onScroll={onContentScroll}
                      className="h-full min-h-0 overflow-y-auto"
                    >
                      {listQuery.isError ? (
                        <p className={cx(typeBodySm, statusFail, "px-5 py-4")}>
                          {(listQuery.error as Error).message}
                        </p>
                      ) : listQuery.isLoading ? (
                        <div
                          className={cx(panel, "m-4")}
                          aria-busy="true"
                          aria-label="Loading queue"
                        >
                          <div className={cx(panelHead, "h-10")}>
                            <span className={cx(skeleton, "h-4 w-16")} />
                            <span className={cx(skeleton, "ms-auto h-3.5 w-8")} />
                          </div>
                          <ul className={cx(panelBody, "mb-1", rowsRuled)}>
                            {[0.95, 0.75, 0.55, 0.4].map((op, i) => (
                              <li
                                key={i}
                                className="flex items-center gap-3 px-3.5 py-2.5"
                                style={{ opacity: op }}
                              >
                                <span className={cx(skeleton, "size-8 shrink-0")} />
                                <span className="min-w-0 flex-1 space-y-1.5">
                                  <span className={cx(skeleton, "block h-3.5 w-[55%]")} />
                                  <span className={cx(skeleton, "block h-2.5 w-[70%]")} />
                                </span>
                                <span className={cx(skeleton, "h-2.5 w-12 shrink-0")} />
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : filtered.length === 0 ? (
                        <div className={cx(panel, "m-4 min-h-[calc(100%-2rem)]")}>
                          <div className="px-4 pt-4 pb-2">
                            <p className={emptyTitle}>Queue is clear</p>
                            <p className={cx(emptyDescription, "mt-1")}>
                              Seed a case or pull the inbox when you need a file here.
                            </p>
                          </div>
                          <ul className="grid gap-1 p-1">
                            {(
                              [
                                {
                                  icon: File01Icon,
                                  title: "Seed complete case",
                                  body: "Clean file — ready to approve.",
                                  meta: "Pass",
                                  onClick: () =>
                                    seedMut.mutate("case01_complete"),
                                },
                                {
                                  icon: Alert02Icon,
                                  title: "Seed bank failure",
                                  body: "Balance too low → Send back.",
                                  meta: "Fail",
                                  onClick: () =>
                                    seedMut.mutate("case11_insufficient_funds"),
                                },
                                {
                                  icon: Mail01Icon,
                                  title: "Pull Jeff’s inbox",
                                  body: "Email pipeline into this queue.",
                                  meta: "Live",
                                  onClick: () => setAreaId("inbox"),
                                },
                              ] as const
                            ).map((item) => (
                              <li key={item.title} className={cx(insetBody, cornerSm)}>
                                <button
                                  type="button"
                                  onClick={item.onClick}
                                  className={cx(
                                    hoverFill,
                                    pressedFill,
                                    transition,
                                    focusRingInset,
                                    cornerSm,
                                    "group flex w-full cursor-pointer items-start gap-3 p-3.5 text-left",
                                  )}
                                >
                                  <HugeiconsIcon
                                    icon={item.icon}
                                    size={16}
                                    strokeWidth={1.8}
                                    className={cx(text2, "mt-0.5 shrink-0")}
                                  />
                                  <span className="min-w-0 flex-1">
                                    <span className={cx(typeLabel, text1, "flex items-center gap-1")}>
                                      {item.title}
                                      <HugeiconsIcon
                                        icon={ArrowRight02Icon}
                                        size={12}
                                        strokeWidth={1.8}
                                        className={cx(transition, "opacity-0 group-hover:opacity-100")}
                                      />
                                    </span>
                                    <span className={cx(typeBodySm, text2, "mt-0.5 block")}>
                                      {item.body}
                                    </span>
                                  </span>
                                  <span className={cx(typeCaption, text3, "pt-0.5")}>{item.meta}</span>
                                </button>
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : (
                        <div>
                          <ul className={cx(rowsRuled, "border-b border-[rgb(25_33_35/0.08)] dark:border-neutral-100/8")}>
                            {filtered.map((row) => {
                              const selected = selectedId === row.id;
                              return (
                                <li key={row.id} className="group/row relative">
                                  <button
                                    type="button"
                                    aria-pressed={selected}
                                    onClick={() => setSelectedId(row.id)}
                                    className={cx(
                                      hoverFill,
                                      pressedFill,
                                      transition,
                                      focusRingInset,
                                      "group relative flex w-full cursor-pointer items-start gap-3 py-3.5 pr-12 pl-5 text-left",
                                      selected && "bg-[#f7f8f8] before:absolute before:inset-y-0 before:left-0 before:w-[2px] before:bg-[#192123] hover:bg-[#f3f4f4] dark:bg-neutral-100/9 dark:before:bg-neutral-100",
                                    )}
                                  >
                                    <span className="min-w-0 flex-1">
                                      <span className="flex min-w-0 items-baseline gap-2">
                                        <span className={cx(typeRowTitle, text1, "min-w-0 flex-1 truncate")}>
                                          {row.applicant_name || "Unknown applicant"}
                                        </span>
                                        <span className={cx(typeCaption, text3, "shrink-0 tabular-nums")}>
                                          {row.submission_date ?? "—"}
                                        </span>
                                      </span>
                                      <span className="mt-1 flex min-w-0 items-baseline gap-3">
                                      {row.trip_summary ? (
                                        <span className={cx(typeCaption, text3, "min-w-0 flex-1 truncate")}>
                                          {row.trip_summary}
                                        </span>
                                      ) : null}
                                      <span className={cx(typeCaption, TONE[toneFor(row)], "ms-auto inline-flex shrink-0 items-center gap-1.5 font-medium")}>
                                        <span aria-hidden className="size-1.5 -translate-y-px rounded-full bg-current" />
                                        {statusCopy(row)}
                                      </span>
                                      </span>
                                    </span>
                                  </button>
                                  {row.has_report && (bucket(row) === "queue" || bucket(row) === "approved") ? (
                                    <button
                                      type="button"
                                      onClick={() =>
                                        setGraphFor({ id: row.id, name: row.applicant_name ?? null })
                                      }
                                      title="View execution graph"
                                      aria-label={`View execution graph for ${row.applicant_name || "this application"}`}
                                      className={cx(
                                        transition,
                                        focusRingInset,
                                        "absolute top-1/2 right-3 grid size-7 -translate-y-1/2 cursor-pointer place-items-center rounded-[6px] text-[#9aa2a5] hover:bg-[#192123]/6 hover:text-[#192123] dark:text-neutral-500 dark:hover:bg-neutral-100/8 dark:hover:text-neutral-100",
                                        selected && "text-[#41494c]",
                                      )}
                                    >
                                      <HugeiconsIcon icon={NeuralNetworkIcon} size={16} strokeWidth={1.7} />
                                    </button>
                                  ) : null}
                                </li>
                              );
                            })}
                          </ul>
                        </div>
                      )}
                    </main>
                    <div
                      aria-hidden="true"
                      className={cx(
                        fadeTopOnPaper,
                        "pointer-events-none absolute inset-x-0 top-0 h-8",
                        contentEdges.start ? "opacity-100" : "opacity-0",
                      )}
                    />
                    <div
                      aria-hidden="true"
                      className={cx(
                        fadeBottomOnPaper,
                        "pointer-events-none absolute inset-x-0 bottom-0 h-8",
                        contentEdges.end ? "opacity-100" : "opacity-0",
                      )}
                    />
                    </div>
                    <p className={cx(typeCaption, text3, hairT, "shrink-0 px-5 py-3 text-pretty")}>
                      AI extracts and rules score the file. You approve or send back —
                      human lock only.
                    </p>
                  </div>

                  <div className="relative min-h-[380px] lg:min-h-0">
                    <AnimatePresence mode="wait">
                      {selectedId ? (
                        <ApprovalPanel
                          key={selectedId}
                          applicationId={selectedId}
                          onDone={() => setSelectedId(null)}
                        />
                      ) : (
                        <motion.div
                          key="empty"
                          initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={reduceMotion ? undefined : { opacity: 0 }}
                          transition={{ duration: 0.22, ease: EASE_OUT }}
                          className="flex h-full min-h-0 flex-col overflow-y-auto bg-white p-6 dark:bg-neutral-950"
                        >
                          <div className={cx(panel, "flex flex-1 flex-col")}>
                            <div className={cx(panelHead, "h-11")}>
                              <span className={inkSlot}>Human lock</span>
                              <span className={cx(frameTitle, "flex-1")}>
                                Approval
                              </span>
                            </div>
                            <div className={cx(panelBody, "mb-1 flex flex-1 flex-col p-1")}>
                              <div className="relative px-4 pt-4">
                                <div
                                  aria-hidden
                                  className="pointer-events-none select-none space-y-2.5"
                                >
                                  <span className={cx(skeleton, "block h-3.5 w-[75%]")} />
                                  <span className={cx(skeleton, "block h-2.5 w-[50%]")} />
                                  <div className="space-y-1.5 pt-1">
                                    {[0.8, 0.55].map((op, i) => (
                                      <div
                                        key={i}
                                        className="flex items-center gap-2"
                                        style={{ opacity: op }}
                                      >
                                        <span className={cx(skeleton, "size-3 shrink-0")} />
                                        <span className={cx(skeleton, "h-2 flex-1")} />
                                      </div>
                                    ))}
                                  </div>
                                </div>
                                <div
                                  aria-hidden
                                  className={cx(
                                    fadeBottom,
                                    "pointer-events-none absolute inset-x-0 bottom-0 h-10",
                                  )}
                                />
                              </div>
                              <div className="px-4 pt-5 pb-3">
                                <p className={emptyTitle}>Select a file from the left</p>
                                <p className={cx(emptyDescription, "mt-1 text-pretty")}>
                                  The audit and Approve / Send back controls open in this
                                  panel.
                                </p>
                              </div>
                              <ul className="mt-auto grid gap-1">
                                {(
                                  [
                                    {
                                      icon: InboxIcon,
                                      title: filtered[0]
                                        ? `Open ${filtered[0].applicant_name || "next"}`
                                        : "Open first in queue",
                                      body: filtered[0]
                                        ? [
                                            filtered[0].trip_summary,
                                            statusCopy(filtered[0]),
                                          ]
                                            .filter(Boolean)
                                            .join(" · ")
                                        : "Nothing waiting — seed a case",
                                      meta: filtered[0] ? "Ready" : "—",
                                      onClick: () => {
                                        if (filtered[0]) setSelectedId(filtered[0].id);
                                        else seedMut.mutate("case01_complete");
                                      },
                                    },
                                    {
                                      icon: File01Icon,
                                      title: "Seed complete case",
                                      body: "Clean file — ready to approve.",
                                      meta: "Pass",
                                      onClick: () => seedMut.mutate("case01_complete"),
                                    },
                                    {
                                      icon: Alert02Icon,
                                      title: "Seed bank failure",
                                      body: "Balance too low → Send back.",
                                      meta: "Fail",
                                      onClick: () =>
                                        seedMut.mutate("case11_insufficient_funds"),
                                    },
                                  ] as const
                                ).map((item) => (
                                  <li key={item.title} className={cx(insetBody, cornerSm)}>
                                    <button
                                      type="button"
                                      onClick={item.onClick}
                                      className={cx(
                                        hoverFill,
                                        pressedFill,
                                        transition,
                                        focusRingInset,
                                        cornerSm,
                                        "group flex w-full cursor-pointer items-start gap-3 p-3.5 text-left",
                                      )}
                                    >
                                      <HugeiconsIcon
                                        icon={item.icon}
                                        size={16}
                                        strokeWidth={1.8}
                                        className={cx(text2, "mt-0.5 shrink-0")}
                                      />
                                      <span className="min-w-0 flex-1">
                                        <span
                                          className={cx(
                                            typeLabel,
                                            text1,
                                            "flex items-center gap-1",
                                          )}
                                        >
                                          {item.title}
                                          <HugeiconsIcon
                                            icon={ArrowRight02Icon}
                                            size={12}
                                            strokeWidth={1.8}
                                            className={cx(
                                              transition,
                                              "opacity-0 group-hover:opacity-100",
                                            )}
                                          />
                                        </span>
                                        <span
                                          className={cx(typeBodySm, text2, "mt-0.5 block")}
                                        >
                                          {item.body}
                                        </span>
                                      </span>
                                      <span className={cx(typeCaption, text3, "pt-0.5")}>
                                        {item.meta}
                                      </span>
                                    </button>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {drawerOpen && (
        <div className="lg:hidden">
          <button
            type="button"
            aria-label="Close navigation overlay"
            tabIndex={-1}
            onClick={closeDrawer}
            className={cx(
              backdrop,
              overlayEnter,
              "absolute inset-0 z-30 cursor-pointer",
              drawerShown ? "opacity-100" : "opacity-0",
            )}
          />
          <div
            ref={drawerRef}
            role="dialog"
            aria-modal="true"
            aria-label="Navigation"
            className={cx(
              paper,
              overlayShadow,
              overlayEnter,
              "absolute inset-y-0 left-0 z-40 flex w-[13rem] max-w-[calc(100%-3rem)] overflow-hidden",
              drawerShown ? "opacity-100" : "opacity-0",
            )}
          >
            <NavigationFrame
              areaId={areaId}
              onSelectArea={(id) => {
                setAreaId(id);
                setSelectedId(null);
                closeDrawer();
              }}
              counts={counts}
              onClose={closeDrawer}
            />
          </div>
        </div>
      )}
      {graphFor ? (
        <AgentExecutionGraph
          applicationId={graphFor.id}
          applicantName={graphFor.name}
          onClose={() => setGraphFor(null)}
        />
      ) : null}
    </div>
  );
}
