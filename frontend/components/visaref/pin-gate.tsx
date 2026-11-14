"use client";

import Image from "next/image";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { postOfficerAuth } from "@/lib/api";

const SESSION_KEY = "visaref.session";
const SESSION_DURATION_MS = 5 * 60 * 1000;
const EASE_OUT = [0.2, 0, 0, 1] as const;

type Session = {
  token: string;
  expiresAt: number;
};

function readSession(): Session | null {
  try {
    const raw = window.sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as Session;
    if (
      typeof session.token !== "string" ||
      typeof session.expiresAt !== "number" ||
      session.expiresAt <= Date.now()
    ) {
      window.sessionStorage.removeItem(SESSION_KEY);
      return null;
    }
    return session;
  } catch {
    window.sessionStorage.removeItem(SESSION_KEY);
    return null;
  }
}

function writeSession(): Session {
  const session: Session = {
    token: crypto.randomUUID(),
    expiresAt: Date.now() + SESSION_DURATION_MS,
  };
  window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  return session;
}

export default function PinGate({ children }: { children: React.ReactNode }) {
  const reduceMotion = useReducedMotion();
  const [hydrated, setHydrated] = useState(false);
  const [unlocked, setUnlocked] = useState(false);
  const [expiresAt, setExpiresAt] = useState<number | null>(null);
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [shake, setShake] = useState(0);
  const [pending, setPending] = useState(false);

  const lock = useCallback(() => {
    window.sessionStorage.removeItem(SESSION_KEY);
    setUnlocked(false);
    setExpiresAt(null);
    setPin("");
    setError("");
  }, []);

  const submitPin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const entered = pin.trim();
    if (!entered) {
      setError("Enter your officer PIN.");
      setShake((value) => value + 1);
      return;
    }
    setPending(true);
    setError("");
    try {
      await postOfficerAuth(entered);
      const session = writeSession();
      setExpiresAt(session.expiresAt);
      setUnlocked(true);
      setPin("");
    } catch {
      setError("That PIN is not correct.");
      setShake((value) => value + 1);
      setPin("");
    } finally {
      setPending(false);
    }
  };

  useEffect(() => {
    const session = readSession();
    const timer = window.setTimeout(() => {
      if (session) {
        setUnlocked(true);
        setExpiresAt(session.expiresAt);
      }
      setHydrated(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!unlocked || !expiresAt) return;

    const checkExpiry = () => {
      if (Date.now() >= expiresAt) lock();
    };
    const timeout = window.setTimeout(
      checkExpiry,
      Math.max(0, expiresAt - Date.now()),
    );
    const onVisibilityChange = () => {
      if (!document.hidden) checkExpiry();
    };

    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      window.clearTimeout(timeout);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [expiresAt, lock, unlocked]);

  return (
    <AnimatePresence mode="wait" initial={false}>
      {hydrated && unlocked ? (
        <motion.div
          key="app"
          className="h-full"
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.22, ease: EASE_OUT }}
        >
          {children}
        </motion.div>
      ) : (
        <motion.main
          key="lock"
          className="relative isolate flex min-h-dvh items-center justify-center overflow-hidden bg-neutral-950 px-6 text-neutral-900 dark:text-neutral-100"
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={reduceMotion ? undefined : { opacity: 0, scale: 0.98 }}
          transition={{ duration: 0.2, ease: EASE_OUT }}
        >
          <div
            aria-hidden="true"
            className="absolute inset-[-18%] -z-10 scale-110 bg-[radial-gradient(circle_at_22%_28%,oklch(54%_0.08_250/.48),transparent_35%),radial-gradient(circle_at_78%_72%,oklch(62%_0.07_35/.34),transparent_38%),linear-gradient(125deg,oklch(18%_0.03_250),oklch(28%_0.04_290),oklch(15%_0.03_40))] blur-3xl"
          />
          <motion.section
            className="relative w-full max-w-[320px] rounded-[var(--rb-r-lg,10px)] border border-white/18 bg-white/92 p-6 text-neutral-900 shadow-[0_18px_50px_-24px_rgb(0_0_0/0.5)] backdrop-blur-xl dark:border-white/14 dark:bg-neutral-900/92 dark:text-neutral-100 dark:shadow-[0_18px_50px_-24px_rgb(0_0_0/0.9)]"
            initial={reduceMotion ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.28, delay: 0.04, ease: EASE_OUT }}
          >
            <div className="mb-5 flex items-center gap-2.5">
              <Image
                src="/visaref-mark.svg"
                alt=""
                width={28}
                height={28}
                className="size-7 rounded-[6px]"
                priority
              />
              <div>
                <p className="text-[14px]/[16px] font-[450]">VisaRef</p>
                <p className="mt-1 text-[12px]/[16px] text-neutral-900/60 dark:text-neutral-100/60">
                  Gloria desk
                </p>
              </div>
            </div>

            <div className="mb-4">
              <p className="text-[18px]/[22px] font-[450] tracking-[-0.015em]">
                Enter your PIN
              </p>
              <p className="mt-1.5 text-[12px]/[16px] text-neutral-900/70 dark:text-neutral-100/70">
                Unlock with the officer PIN from your server config.
              </p>
            </div>

            <form onSubmit={submitPin}>
              <motion.div
                key={shake}
                className="mb-3.5"
                animate={shake ? { x: [0, -6, 6, -4, 4, 0] } : undefined}
                transition={{ duration: 0.28, ease: EASE_OUT }}
              >
                <input
                  aria-label="Officer PIN"
                  autoComplete="one-time-code"
                  className="h-12 w-full rounded-[var(--rb-r-sm,6px)] border border-neutral-900/14 bg-white px-3 text-center font-mono text-[20px] tracking-[0.35em] text-neutral-900 outline-none transition-[border-color,box-shadow] duration-[120ms] focus:border-neutral-900/45 focus:ring-2 focus:ring-neutral-900/10 dark:border-neutral-100/14 dark:bg-neutral-950 dark:text-neutral-100 dark:focus:border-neutral-100/45 dark:focus:ring-neutral-100/10"
                  disabled={pending}
                  inputMode="numeric"
                  maxLength={32}
                  onChange={(event) => {
                    setPin(event.target.value.replace(/\D/g, "").slice(0, 32));
                    setError("");
                  }}
                  type="password"
                  value={pin}
                />
              </motion.div>

              <button
                type="submit"
                disabled={pending || !pin}
                className="flex h-10 w-full items-center justify-center rounded-[var(--rb-r-sm,6px)] bg-neutral-900 text-[13px] font-[450] text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
              >
                {pending ? "Checking…" : "Unlock"}
              </button>

              <p className="mb-1 mt-2 min-h-[16px] text-[12px]/[16px] text-[oklch(51%_0.18_26)] dark:text-[oklch(76%_0.14_26)]">
                {error}
              </p>
            </form>

            <p className="mt-3 text-center text-[11px]/[15px] text-neutral-900/55 dark:text-neutral-100/55">
              Session expires after 5 minutes. API still requires lock tokens for
              Approve / Send.
            </p>
          </motion.section>
        </motion.main>
      )}
    </AnimatePresence>
  );
}
