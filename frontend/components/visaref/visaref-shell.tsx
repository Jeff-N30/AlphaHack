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
  PassportIcon,
  RefreshIcon,
  SentIcon,
  Tick02Icon,
  UnfoldMoreIcon,
} from "@hugeicons/core-free-icons";
import { toast } from "sonner";
import {
  fetchApplication,
  fetchApplications,
  postEmailInboxRead,
  postGloriaAction,
  postSeedCase,
  type ApplicationRow,
} from "@/lib/api";

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
const text1 = "text-neutral-900 dark:text-neutral-100";
const text2 = "text-neutral-900/80 dark:text-neutral-100/80";
const text3 = "text-neutral-900/66 dark:text-neutral-100/66";
const rowsRuled = "divide-y divide-neutral-900/8 dark:divide-neutral-100/8";
const overlayShadow =
  "shadow-[0_12px_24px_-12px_rgb(0_0_0/0.2)] dark:shadow-[0_12px_24px_-12px_rgb(0_0_0/0.6)]";
const typeHeadingSm = "text-[20px]/[24px] font-[450] tracking-[-0.015em]";
const typeHeadingXs = "text-[16px]/[20px] font-[450] tracking-[-0.015em]";
const typeLabel = "text-[14px]/[16px] font-[450]";
const typeBodySm = "text-[13px]/[18px] font-normal";
const typeCaption = "text-[12px]/[16px] font-normal tabular-nums";
const typeCodeSm = "font-mono text-[12px]/[16px] tabular-nums";
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
  "h-7 gap-1.5 rounded-[var(--rb-r-sm,6px)] px-3 text-[14px]/[16px] font-[450]";
const buttonMd =
  "h-8 gap-2 rounded-[var(--rb-r-sm,6px)] px-4 text-[14px]/[16px] font-[450]";
const buttonLg =
  "h-11 gap-2 rounded-[var(--rb-r-sm,6px)] px-5 text-[16px]/[20px] font-[450] tracking-[-0.01em]";
const iconButtonMd = "size-8 rounded-[var(--rb-r-sm,6px)]";
const selectCaret = "shrink-0 text-neutral-900/80 dark:text-neutral-100/80";
const statusWordSm =
  "inline-flex items-start gap-1 text-[13px]/[18px] font-[450] tabular-nums";
const statusOk = "text-neutral-900/80 dark:text-neutral-100/80";
const statusWarn = "text-[oklch(49%_0.1_68)] dark:text-[oklch(80%_0.13_68)]";
const statusFail = "text-[oklch(51%_0.18_26)] dark:text-[oklch(76%_0.14_26)]";
const avatar =
  "relative inline-flex size-8 shrink-0 overflow-hidden rounded-full select-none";
const avatarSquare =
  "relative inline-flex size-8 shrink-0 overflow-hidden rounded-[var(--rb-r-sm,6px)] select-none";
const avatarFallback =
  "flex size-full items-center justify-center rounded-[inherit] border border-neutral-900/12 dark:border-neutral-100/14 bg-white dark:bg-neutral-900 text-[12px]/[16px] font-[450] tabular-nums text-neutral-900 dark:text-neutral-100";
const frameTitle =
  "min-w-0 truncate text-[14px]/[16px] font-[450] text-neutral-900 dark:text-neutral-100";
const frameMeta =
  "shrink-0 text-[14px]/[16px] font-[450] tabular-nums text-neutral-900/66 dark:text-neutral-100/66";
const panel =
  "relative flex min-w-0 flex-col overflow-hidden rounded-[var(--rb-r-lg,10px)] border border-neutral-900/10 dark:border-neutral-100/14 bg-neutral-50 text-neutral-900 dark:text-neutral-100 dark:bg-neutral-900";
const panelHead =
  "flex min-h-10 min-w-0 shrink-0 items-center gap-2 px-4 has-[button]:pe-2";
const panelBody =
  "mx-1 mb-1 flex min-w-0 flex-col overflow-hidden rounded-[var(--rb-r-sm,6px)] border border-neutral-900/8 bg-white [&:has(+*)]:mb-0 dark:border-neutral-100/8 dark:bg-neutral-950";
const panelFoot =
  "flex min-h-11 min-w-0 items-center gap-2 px-4 py-2 text-[13px]/[18px] text-neutral-900/66 dark:text-neutral-100/66 has-[button]:justify-end has-[button]:pe-2";
const itemRow =
  "relative flex min-h-10 w-full min-w-0 flex-wrap items-center gap-x-3 gap-y-1 py-2 text-left text-neutral-900 dark:text-neutral-100 transition-[background-color] duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)] has-[[data-description]]:min-h-14";
const itemRowInteractive =
  "cursor-pointer hover:bg-neutral-900/5 dark:hover:bg-neutral-100/5 active:bg-neutral-900/8 dark:active:bg-neutral-100/8";
const itemContent = "flex min-w-0 flex-1 flex-col gap-0.5";
const itemTitle =
  "flex max-w-full min-w-0 items-baseline gap-2 text-[14px]/[16px] font-[450] text-neutral-900 dark:text-neutral-100";
const menuPopup =
  "min-w-48 max-w-[min(480px,calc(100vw-2rem))] overflow-x-hidden overflow-y-auto overscroll-contain rounded-[var(--rb-r-lg,10px)] border border-neutral-900/10 dark:border-neutral-100/14 bg-white dark:bg-neutral-900 p-1 text-neutral-900 dark:text-neutral-100 outline-none shadow-[0_12px_24px_-12px_rgb(0_0_0/0.2)] dark:shadow-[0_12px_24px_-12px_rgb(0_0_0/0.6)]";
const menuSeparator = "-mx-1 my-1 h-px bg-neutral-900/8 dark:bg-neutral-100/8";
const menuItem =
  "relative flex min-h-8 w-full cursor-default items-center gap-2 rounded-[var(--rb-r-sm,6px)] px-2 py-1.5 text-left text-[14px]/[16px] font-[450] text-neutral-900 outline-none select-none [&_svg]:shrink-0 [&_svg]:text-neutral-900/80 hover:bg-neutral-900/5 focus-visible:bg-neutral-900/5 data-[highlighted]:bg-neutral-900/5 aria-selected:bg-neutral-900/9 aria-disabled:cursor-not-allowed aria-disabled:text-neutral-900/40 dark:text-neutral-100 dark:[&_svg]:text-neutral-100/80 dark:hover:bg-neutral-100/5 dark:focus-visible:bg-neutral-100/5 dark:data-[highlighted]:bg-neutral-100/5 dark:aria-selected:bg-neutral-100/9 dark:aria-disabled:text-neutral-100/40";
const tooltip =
  "pointer-events-none inline-flex min-h-6 w-fit max-w-64 items-center gap-2 rounded-[var(--rb-r-sm,6px)] bg-neutral-900 px-2 py-1 text-[12px]/[16px] font-[450] tabular-nums text-white shadow-[0_12px_24px_-12px_rgb(0_0_0/0.2)] dark:shadow-[0_12px_24px_-12px_rgb(0_0_0/0.6)] dark:bg-neutral-100 dark:text-neutral-900";
const overlayEnter =
  "transition-opacity duration-[160ms] ease-[cubic-bezier(0.2,0,0,1)] starting:opacity-0 motion-reduce:transition-none";
const sidebarSurface =
  "border-r border-neutral-900/8 bg-white dark:border-neutral-100/8 dark:bg-neutral-900";
const navItem =
  "flex h-8 w-full min-w-0 cursor-pointer items-center gap-2 rounded-[var(--rb-r-sm,6px)] px-2 text-left text-[14px]/[16px] font-[450] text-neutral-900/80 transition-[background-color,color] duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)] [&_svg]:shrink-0 hover:bg-neutral-900/5 hover:text-neutral-900 aria-[current=page]:bg-neutral-900/9 aria-[current=page]:text-neutral-900 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--rb-accent,oklch(20.5%_0_0))] dark:focus-visible:outline-[var(--rb-accent,oklch(100%_0_0))] dark:text-neutral-100/80 dark:hover:bg-neutral-100/5 dark:hover:text-neutral-100 dark:aria-[current=page]:bg-neutral-100/9 dark:aria-[current=page]:text-neutral-100";
const navCount =
  "ms-auto text-[12px]/[16px] font-[450] tabular-nums text-neutral-900/66 dark:text-neutral-100/66";
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
  "text-[16px]/[20px] font-[450] tracking-[-0.015em] text-neutral-900 dark:text-neutral-100";
const emptyDescription =
  "max-w-[48ch] text-[13px]/[18px] text-neutral-900/80 dark:text-neutral-100/80";
const cornerSm = "rounded-[var(--rb-r-sm,6px)]";
const hoverFill = "hover:bg-neutral-900/5 dark:hover:bg-neutral-100/5";
const pressedFill = "active:bg-neutral-900/8 dark:active:bg-neutral-100/8";
const transition =
  "transition-[color,background-color,border-color,box-shadow,outline-color,opacity,scale] duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)] active:duration-[60ms]";
const insetBody = "bg-white dark:bg-neutral-950";
const inkSlot =
  "inline-flex h-6 shrink-0 items-center whitespace-nowrap rounded-[var(--rb-r-xs,4px)] border border-neutral-900/12 dark:border-neutral-100/14 bg-white dark:bg-neutral-900 px-2 text-[14px]/[16px] font-[450] tabular-nums text-neutral-900 dark:text-neutral-100";
const disclosureRow =
  "group -mx-2 flex min-h-8 max-w-[calc(100%+16px)] min-w-0 cursor-pointer items-center gap-2 self-start rounded-[var(--rb-r-sm,6px)] px-2 text-left text-[13px]/[18px] text-neutral-900/80 dark:text-neutral-100/80 transition-[background-color] duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)] hover:bg-neutral-900/5 active:bg-neutral-900/8 dark:hover:bg-neutral-100/5 dark:active:bg-neutral-100/8 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--rb-accent,oklch(20.5%_0_0))] dark:focus-visible:outline-[var(--rb-accent,oklch(100%_0_0))]";
const toolWell =
  "flex min-w-0 flex-col gap-3 rounded-[var(--rb-r-sm,6px)] bg-neutral-900/5 px-3 py-2 dark:bg-neutral-100/5";
const toolOutput =
  "min-w-0 overflow-x-auto font-mono text-[12px]/[16px] whitespace-pre-wrap text-neutral-900/80 dark:text-neutral-100/80 [overflow-wrap:anywhere]";

const EASE_OUT: [number, number, number, number] = [0.2, 0, 0, 1];
const TOOLTIP_DELAY_MS = 400;
const TOOLTIP_GRACE_MS = 300;

type Tone = "neutral" | "attention" | "critical";
const TONE: Record<Tone, string> = {
  neutral: statusOk,
  attention: statusWarn,
  critical: statusFail,
};

type NavView = "queue" | "approved" | "sent_back" | "inbox";

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
  "PP.BLANK_PAGES": {
    title: "Blank visa pages",
    hint: "At least 2 empty pages in the passport",
  },
  "PHOTO.ISO": {
    title: "Photo standard",
    hint: "Schengen / ISO photo rules",
  },
  "BANK.SUFFICIENT_FUNDS": {
    title: "Bank balance too low",
    hint: "Statement balance below required trip funds",
  },
  "BANK.WINDOW": {
    title: "Bank statement too old",
    hint: "Statement date outside the allowed window",
  },
  "ID.NAME_MATCH": {
    title: "Name mismatch",
    hint: "Passport name does not match other documents",
  },
};

function ruleCopy(ruleId: string | undefined) {
  if (!ruleId) return { title: "Item to check", hint: "Confirm on the document" };
  return (
    RULE_LABEL[ruleId] ?? {
      title: ruleId.replaceAll(".", " · "),
      hint: "Confirm on the document",
    }
  );
}

function outcomePlain(outcome: string | null | undefined) {
  switch (outcome) {
    case "READY_FOR_APPROVAL":
      return {
        title: "Approve",
        auto: "passed" as const,
        body: "Code checks are clear. Confirm the look-items below, then mark ready.",
        tone: "neutral" as Tone,
      };
    case "NEEDS_GLORIA":
      return {
        title: "Flag",
        auto: "attention" as const,
        body: "Something needs your judgment before the file is ready.",
        tone: "attention" as Tone,
      };
    case "SEND_BACK":
      return {
        title: "Send back",
        auto: "failed" as const,
        body: "Code checks found issues. Confirm send-back to the applicant.",
        tone: "critical" as Tone,
      };
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
];

function WorkspaceBlock() {
  const [open, setOpen] = useState(false);
  const [shown, setShown] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const close = (restore: boolean) => {
    setOpen(false);
    setShown(false);
    if (restore) triggerRef.current?.focus({ preventScroll: true });
  };

  useEffect(() => {
    if (!open) return;
    const frame = requestAnimationFrame(() => setShown(true));
    const doc = rootRef.current?.ownerDocument ?? document;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) close(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close(true);
    };
    doc.addEventListener("pointerdown", onPointerDown);
    doc.addEventListener("keydown", onKeyDown);
    return () => {
      cancelAnimationFrame(frame);
      doc.removeEventListener("pointerdown", onPointerDown);
      doc.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => (open ? close(false) : setOpen(true))}
        className={cx(ghostButtonMuted, buttonLg, "w-full pr-2 pl-2 text-left")}
      >
        <span className={cx(avatarSquare, "size-[28px] overflow-hidden")}>
          <Image
            src="/visaref-mark.svg"
            alt=""
            width={28}
            height={28}
            className="size-full"
          />
        </span>
        <span className="min-w-0 flex-1">
          <span className={cx(typeLabel, text1, "block truncate")}>VisaRef</span>
          <span className={cx(typeCaption, text3, "block truncate")}>
            TLS Beirut · Gloria
          </span>
        </span>
        <HugeiconsIcon
          icon={UnfoldMoreIcon}
          size={16}
          strokeWidth={1.8}
          aria-hidden="true"
          className={selectCaret}
        />
      </button>

      {open && (
        <div
          ref={menuRef}
          role="menu"
          aria-label="Workspace"
          className={cx(
            menuPopup,
            overlayEnter,
            "absolute left-0 right-0 top-[calc(100%+0.25rem)] z-30",
            shown ? "opacity-100" : "opacity-0",
          )}
        >
          <div className={menuItem}>
            <span className="min-w-0 flex-1">
              <span className="block truncate">VisaRef</span>
              <span className={cx(typeCaption, text3, "block truncate")}>
                FR Schengen short-stay
              </span>
            </span>
            <HugeiconsIcon icon={Tick02Icon} size={16} strokeWidth={1.8} />
          </div>
          <div role="separator" className={menuSeparator} />
          <button type="button" role="menuitem" className={menuItem} onClick={() => close(true)}>
            <HugeiconsIcon icon={PassportIcon} size={16} strokeWidth={1.8} />
            Destination checklist
          </button>
        </div>
      )}
    </div>
  );
}

function NavigationFrame({
  areaId,
  onSelectArea,
  counts,
  onClose,
}: {
  areaId: NavView;
  onSelectArea: (id: NavView) => void;
  counts: Record<NavView, number>;
  onClose?: () => void;
}) {
  const [tipFor, setTipFor] = useState<string | null>(null);
  const [tipShown, setTipShown] = useState(false);
  const {
    ref: navRef,
    edges: navEdges,
    onScroll: onNavScroll,
  } = useScrollFade<HTMLElement>();
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const frameRef = useRef<number | undefined>(undefined);
  const openRef = useRef(false);
  const graceRef = useRef(false);
  const graceTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );
  const reduceMotion = useReducedMotion();

  const showTip = (id: string) => {
    clearTimeout(timerRef.current);
    cancelAnimationFrame(frameRef.current ?? 0);
    const instant = openRef.current || graceRef.current;
    const reveal = () => {
      openRef.current = true;
      setTipFor(id);
      if (instant) setTipShown(true);
      else {
        setTipShown(false);
        frameRef.current = requestAnimationFrame(() => setTipShown(true));
      }
    };
    if (instant) reveal();
    else timerRef.current = setTimeout(reveal, TOOLTIP_DELAY_MS);
  };

  const hideTip = () => {
    clearTimeout(timerRef.current);
    cancelAnimationFrame(frameRef.current ?? 0);
    if (openRef.current) {
      graceRef.current = true;
      clearTimeout(graceTimerRef.current);
      graceTimerRef.current = setTimeout(() => {
        graceRef.current = false;
      }, TOOLTIP_GRACE_MS);
    }
    openRef.current = false;
    setTipFor(null);
    setTipShown(false);
  };

  useEffect(
    () => () => {
      clearTimeout(timerRef.current);
      clearTimeout(graceTimerRef.current);
      cancelAnimationFrame(frameRef.current ?? 0);
    },
    [],
  );

  const tip = (id: string, label: string) =>
    tipFor === id ? (
      <motion.span
        role="tooltip"
        initial={tipShown || reduceMotion ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.16, ease: EASE_OUT }}
        className={cx(
          tooltip,
          "absolute left-full top-1/2 z-[70] ml-2 h-7 -translate-y-1/2 whitespace-nowrap",
        )}
      >
        {label}
      </motion.span>
    ) : null;

  const area = AREA_META.find((a) => a.id === areaId) ?? AREA_META[0];

  return (
    <>
      <div
        className={cx(
          sidebarSurface,
          "flex w-14 shrink-0 flex-col items-center gap-1 px-2 py-3",
        )}
      >
        {onClose && (
          <button
            type="button"
            aria-label="Close navigation"
            onClick={onClose}
            className={cx(ghostButton, iconButtonMd, "mb-1")}
          >
            <HugeiconsIcon icon={Cancel01Icon} size={16} strokeWidth={1.8} />
          </button>
        )}

        <nav
          aria-label="Areas"
          onMouseLeave={hideTip}
          className="flex flex-col items-center gap-1"
        >
          {AREA_META.map((item) => {
            const selected = item.id === areaId;
            return (
              <span key={item.id} className="relative">
                <button
                  type="button"
                  aria-label={item.label}
                  aria-current={selected ? "page" : undefined}
                  onClick={() => {
                    onSelectArea(item.id);
                    hideTip();
                  }}
                  onMouseEnter={() => showTip(item.id)}
                  onFocus={() => showTip(item.id)}
                  onBlur={hideTip}
                  className={cx(navItem, "justify-center")}
                >
                  <HugeiconsIcon
                    icon={item.icon}
                    size={16}
                    strokeWidth={1.8}
                    aria-hidden="true"
                  />
                </button>
                {tip(item.id, item.label)}
              </span>
            );
          })}
        </nav>

        <span className="relative mt-auto" onMouseLeave={hideTip}>
          <button
            type="button"
            aria-label="Gloria, visa officer"
            onMouseEnter={() => showTip("account")}
            onFocus={() => showTip("account")}
            onBlur={hideTip}
            className={cx(avatar, focusRing, "cursor-pointer")}
          >
            <span className={avatarFallback}>GL</span>
          </button>
          {tip("account", "Gloria · visa officer")}
        </span>
      </div>

      <div className={cx(sidebarSurface, "flex w-64 min-w-0 flex-col")}>
        <div className="shrink-0 px-2 py-1.5">
          <WorkspaceBlock />
        </div>

        <div className="relative min-h-0 flex-1">
          <nav
            ref={navRef}
            onScroll={onNavScroll}
            aria-label={area.label}
            className="h-full overflow-y-auto px-2 pb-3"
          >
            <p className={navGroupLabel}>Desk</p>
            <ul className="space-y-0.5">
              {AREA_META.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    aria-current={item.id === areaId ? "page" : undefined}
                    onClick={() => onSelectArea(item.id)}
                    className={navItem}
                  >
                    <span className="min-w-0 flex-1 truncate">{item.label}</span>
                    {item.id !== "inbox" && (
                      <span className={cx(navCount, "shrink-0")}>
                        {counts[item.id]}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>

            <p className={navGroupLabel}>Destination</p>
            <ul className="space-y-0.5">
              <li>
                <span className={cx(navItem, "cursor-default hover:bg-transparent")}>
                  <HugeiconsIcon icon={PassportIcon} size={16} strokeWidth={1.8} />
                  <span className="min-w-0 flex-1 truncate">FR Schengen</span>
                </span>
              </li>
            </ul>
          </nav>
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
        </div>
      </div>
    </>
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
  const detailQuery = useQuery({
    queryKey: ["application", applicationId],
    queryFn: () => fetchApplication(applicationId),
  });

  const actionMut = useMutation({
    mutationFn: (action: "approve" | "send_back" | "review") =>
      postGloriaAction(applicationId, action),
    onSuccess: (_d, action) => {
      toast.success(
        action === "approve"
          ? "Marked ready — you take this to TLS yourself"
          : action === "send_back"
            ? "Marked send-back — moved out of queue"
            : "Still in your queue",
      );
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["application", applicationId] });
      if (action !== "review") onDone();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const meta = detailQuery.data?.meta;
  const audit = detailQuery.data?.report?.audit;
  const outcome = (audit?.outcome ?? meta?.outcome) as string | undefined;
  const plain = outcomePlain(outcome);
  const results = audit?.results ?? [];
  const lookItems = results.filter((r) =>
    ["FAIL", "NEEDS_HUMAN"].includes((r.status ?? "").toUpperCase()),
  );
  const files = detailQuery.data?.files ?? [];
  const alreadyDecided =
    Boolean(meta?.status?.startsWith("approved")) ||
    Boolean(meta?.status?.startsWith("sent_back"));

  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      exit={reduceMotion ? undefined : { opacity: 0, x: 8 }}
      transition={{ duration: 0.22, ease: EASE_OUT }}
      className="flex h-full min-h-0 flex-col"
    >
      <div className="shrink-0 space-y-0.5 border-b border-neutral-900/8 px-4 py-3 dark:border-neutral-100/8 sm:px-5">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className={cx(typeHeadingXs, "truncate")}>
            {meta?.applicant_name || "Unknown applicant"}
          </h2>
          <span className={cx(typeCaption, TONE[plain.tone], "shrink-0")}>
            {plain.title}
          </span>
        </div>
        <p className={cx(typeCaption, text3, "truncate")}>
          {meta?.trip_summary || "Trip pending"}
        </p>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3 sm:p-4">
        {detailQuery.isLoading ? (
          <div className={cx(typeBodySm, text3, "flex items-center gap-2")}>
            <HugeiconsIcon icon={Loading03Icon} size={14} className="animate-spin" />
            Loading file…
          </div>
        ) : (
          <>
            <section className={panel}>
              <div className={cx(panelHead, "h-10")}>
                <span className={inkSlot}>Your call</span>
                <span className={cx(frameTitle, "flex-1")}>Decision</span>
              </div>
              <div className={cx(panelBody, "gap-0 px-0 pt-0 pb-0")}>
                <div className="flex items-start gap-2.5 border-b border-neutral-900/8 px-3 py-2.5 dark:border-neutral-100/8">
                  <HugeiconsIcon
                    icon={
                      plain.auto === "failed"
                        ? Alert02Icon
                        : CheckmarkCircle02Icon
                    }
                    size={15}
                    className={cx(
                      "mt-0.5 shrink-0",
                      plain.auto === "failed"
                        ? statusFail
                        : plain.auto === "attention"
                          ? statusWarn
                          : statusOk,
                    )}
                  />
                  <div className="min-w-0">
                    <p className={cx(typeLabel, text1)}>
                      {plain.auto === "passed"
                        ? "Automated checks passed"
                        : plain.auto === "failed"
                          ? "Automated checks failed"
                          : plain.auto === "attention"
                            ? "Needs your judgment"
                            : "Review required"}
                    </p>
                    <p className={cx(typeCaption, text3, "mt-0.5")}>
                      {plain.body}
                    </p>
                  </div>
                </div>

                {lookItems.length > 0 ? (
                  <div>
                    <p
                      className={cx(
                        typeCaption,
                        text3,
                        "px-3 pt-2.5 pb-1",
                      )}
                    >
                      Look-items · {lookItems.length}
                    </p>
                    <ul className={rowsRuled}>
                      {lookItems.slice(0, 6).map((r, i) => {
                        const id = String(r.rule_id ?? r.id ?? i);
                        const isFail =
                          (r.status ?? "").toUpperCase() === "FAIL";
                        const copy = ruleCopy(r.rule_id ?? r.id);
                        return (
                          <li
                            key={id}
                            className="flex items-start gap-2.5 px-3 py-2.5"
                          >
                            <span
                              className={cx(
                                "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-[3px] border",
                                isFail
                                  ? "border-[oklch(51%_0.18_26/0.45)] text-[oklch(51%_0.18_26)]"
                                  : "border-neutral-900/20 text-neutral-900/40 dark:border-neutral-100/25 dark:text-neutral-100/40",
                              )}
                              aria-hidden
                            >
                              {isFail ? (
                                <HugeiconsIcon icon={Alert02Icon} size={10} />
                              ) : (
                                <span className="size-1.5 rounded-[1px] bg-current opacity-40" />
                              )}
                            </span>
                            <span className="min-w-0 flex-1">
                              <span className={cx(typeLabel, text1, "block")}>
                                {copy.title}
                              </span>
                              <span
                                className={cx(typeCaption, text3, "mt-0.5 block")}
                              >
                                {isFail
                                  ? r.message || "Failed check"
                                  : copy.hint}
                              </span>
                            </span>
                            <span
                              className={cx(
                                typeCaption,
                                "shrink-0",
                                isFail ? statusFail : statusWarn,
                              )}
                            >
                              {isFail ? "Fail" : "You"}
                            </span>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ) : (
                  <p className={cx(typeBodySm, text2, "px-3 py-2.5")}>
                    No look-items — approve if the file looks complete.
                  </p>
                )}

                <div className="border-t border-neutral-900/8 px-3 py-2 dark:border-neutral-100/8">
                  <button
                    type="button"
                    aria-expanded={showTech}
                    onClick={() => setShowTech((v) => !v)}
                    className={disclosureRow}
                  >
                    <span
                      className={cx(
                        "transition-transform duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)]",
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
                        "mt-1.5 max-h-36 overflow-auto",
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
                <div className={panelFoot}>
                  <button
                    type="button"
                    className={cx(secondaryButton, buttonSm)}
                    disabled={actionMut.isPending}
                    onClick={() => actionMut.mutate("review")}
                  >
                    Flag
                  </button>
                  <button
                    type="button"
                    className={cx(secondaryButton, buttonSm)}
                    disabled={actionMut.isPending}
                    onClick={() => actionMut.mutate("send_back")}
                  >
                    Send back
                  </button>
                  <button
                    type="button"
                    className={cx(primaryButton, buttonSm)}
                    disabled={actionMut.isPending}
                    onClick={() => actionMut.mutate("approve")}
                  >
                    {actionMut.isPending ? (
                      <HugeiconsIcon
                        icon={Loading03Icon}
                        size={12}
                        className="animate-spin"
                      />
                    ) : (
                      <HugeiconsIcon icon={Tick02Icon} size={12} />
                    )}
                    Approve
                  </button>
                </div>
              ) : (
                <div className={panelFoot}>
                  <p className={cx(typeBodySm, text2)}>
                    {meta?.human_action || meta?.status}
                  </p>
                </div>
              )}
            </section>

            {files.length > 0 ? (
              <div>
                <p className={cx(typeCaption, text3, "mb-2")}>Documents</p>
                <ul className="flex flex-wrap gap-1.5">
                  {files.map((f) => (
                    <li key={f} className={cx(inkSlot, "max-w-full truncate")}>
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        )}
      </div>
    </motion.div>
  );
}

export default function VisaRefShell() {
  const qc = useQueryClient();
  const reduceMotion = useReducedMotion();
  const [areaId, setAreaId] = useState<NavView>("queue");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerShown, setDrawerShown] = useState(false);
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
    }),
    [rows],
  );

  const filtered = useMemo(() => {
    if (areaId === "inbox") return [];
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

  const primaryAction = () => {
    if (areaId === "inbox") inboxMut.mutate();
    else seedMut.mutate("case01_complete");
  };
  const primaryBusy = seedMut.isPending || inboxMut.isPending;

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
        />
      </aside>

      <div className={cx(pageFog, "flex min-w-0 flex-1 flex-col")}>
        <header
          className={cx(topBar, "flex h-14 shrink-0 items-center gap-3 px-4 sm:px-6")}
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
            <h1 className={cx(typeHeadingSm, "truncate")}>{area.title}</h1>
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
            ) : (
              <div className="flex h-full min-h-0 flex-col">
                {/* One page header — single hierarchy for the whole desk */}
                <div className="shrink-0 border-b border-neutral-900/8 px-5 py-4 dark:border-neutral-100/8 sm:px-6">
                  <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
                    <div className="min-w-0">
                      <p className={cx(typeCaption, text3)}>VisaRef · Gloria</p>
                      <h2 className={cx(typeHeadingSm, "mt-1")}>{area.title}</h2>
                      <p className={cx(typeBodySm, text2, "mt-1 max-w-[52ch]")}>
                        AI extracts and rules score the file. You approve or send back —
                        human lock only.
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={inkSlot}>{area.listTitle}</span>
                      <span className={cx(typeCaption, text3)}>
                        {listQuery.isLoading ? "…" : `${filtered.length} in view`}
                      </span>
                    </div>
                  </div>
                </div>

                {/* One surface: queue | gate */}
                <div className="grid min-h-0 flex-1 lg:grid-cols-2">
                  <div className="relative min-h-0 border-b border-neutral-900/8 lg:border-r lg:border-b-0 dark:border-neutral-100/8">
                    <main
                      ref={contentRef}
                      onScroll={onContentScroll}
                      className="h-full min-h-0 overflow-y-auto p-3 sm:p-4"
                    >
                      {listQuery.isError ? (
                        <p className={cx(typeBodySm, statusFail, "px-2 py-3")}>
                          {(listQuery.error as Error).message}
                        </p>
                      ) : listQuery.isLoading ? (
                        <div className={cx(typeBodySm, text3, "flex items-center gap-2 px-2 py-3")}>
                          <HugeiconsIcon
                            icon={Loading03Icon}
                            size={14}
                            className="animate-spin"
                          />
                          Loading queue…
                        </div>
                      ) : filtered.length === 0 ? (
                        <div className={cx(panel, "h-full")}>
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
                        <div className={cx(panel, "overflow-hidden")}>
                          <div className={cx(panelHead, "h-10")}>
                            <span className={cx(frameTitle, "flex-1")}>Files</span>
                            <span className={frameMeta}>{filtered.length}</span>
                          </div>
                          <ul className={cx(panelBody, "mb-1", rowsRuled)}>
                            {filtered.map((row) => {
                              const selected = selectedId === row.id;
                              return (
                                <li key={row.id}>
                                  <button
                                    type="button"
                                    aria-pressed={selected}
                                    onClick={() => setSelectedId(row.id)}
                                    className={cx(
                                      hoverFill,
                                      pressedFill,
                                      transition,
                                      focusRingInset,
                                      "group flex w-full cursor-pointer items-center gap-3 px-3.5 py-2.5 text-left",
                                      selected && "bg-neutral-900/9 dark:bg-neutral-100/9",
                                    )}
                                  >
                                    <span className={cx(avatarSquare, "size-8 shrink-0")}>
                                      <span className={avatarFallback}>
                                        <HugeiconsIcon
                                          icon={PassportIcon}
                                          size={14}
                                          strokeWidth={1.8}
                                        />
                                      </span>
                                    </span>
                                    <span className="min-w-0 flex-1">
                                      <span className={cx(typeLabel, text1, "block truncate")}>
                                        {row.applicant_name || "Unknown applicant"}
                                      </span>
                                      <span className={cx(typeCaption, text3, "mt-0.5 block truncate")}>
                                        {row.trip_summary ? `${row.trip_summary} · ` : ""}
                                        <span className={TONE[toneFor(row)]}>
                                          {statusCopy(row)}
                                        </span>
                                      </span>
                                    </span>
                                    <span className={cx(typeCaption, text3, "shrink-0 tabular-nums")}>
                                      {row.submission_date ?? "—"}
                                    </span>
                                    <HugeiconsIcon
                                      icon={ArrowRight02Icon}
                                      size={12}
                                      strokeWidth={1.8}
                                      className={cx(
                                        transition,
                                        text3,
                                        "shrink-0 opacity-0 group-hover:opacity-100",
                                        selected && "opacity-100",
                                      )}
                                    />
                                  </button>
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
                          className="flex h-full min-h-0 flex-col overflow-y-auto p-3 sm:p-4"
                        >
                          <div className={cx(panel, "flex flex-1 flex-col")}>
                            <div className={cx(panelHead, "h-10")}>
                              <span className={inkSlot}>Human lock</span>
                              <span className={cx(frameTitle, "flex-1")}>
                                Approval
                              </span>
                            </div>
                            <div className={cx(panelBody, "mb-1 flex flex-1 flex-col p-1")}>
                              <div className="px-3.5 pt-4 pb-2">
                                <p className={emptyTitle}>Select a file</p>
                                <p className={cx(emptyDescription, "mt-1 text-pretty")}>
                                  Approve, send back, or flag — AI never decides alone.
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
              "absolute inset-y-0 left-0 z-40 flex w-[312px] max-w-[calc(100%-3rem)] overflow-hidden",
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
    </div>
  );
}
