"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function MonitoringError({
  error,
  reset,
}: {
  error: Error & {
    digest?: string;
  };
  reset: () => void;
}) {
  const router = useRouter();

  useEffect(() => {
    console.error(
      "Blue-Trading-AI monitoring error:",
      error,
    );
  }, [error]);

  return (
    <main className="midnight-page flex min-h-screen items-center justify-center p-5 text-white">
      <section className="midnight-panel w-full max-w-xl rounded-3xl p-6 text-center sm:p-8">
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-3xl border border-rose-400/20 bg-rose-400/[0.06] text-3xl text-rose-300 shadow-[0_0_30px_rgba(251,113,133,0.16)]">
          !
        </div>

        <p className="mt-6 text-[10px] font-black uppercase tracking-[0.24em] text-slate-600">
          Monitoring Recovery
        </p>

        <h1 className="mt-2 text-2xl font-black tracking-tight text-white sm:text-3xl">
          Monitoring could not load
        </h1>

        <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-slate-500">
          Blue-Trading-AI encountered a temporary monitoring error.
          Your account and platform data were not changed.
        </p>

        <div className="mt-6 rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4 text-left">
          <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-600">
            Error details
          </p>

          <p className="mt-2 break-words text-xs leading-5 text-slate-400">
            {error.message ||
              "An unexpected monitoring error occurred."}
          </p>

          {error.digest ? (
            <p className="mt-2 text-[10px] text-slate-700">
              Reference: {error.digest}
            </p>
          ) : null}
        </div>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <button
            type="button"
            onClick={reset}
            className="midnight-button rounded-xl px-6 py-3 text-sm font-black"
          >
            Retry Monitoring
          </button>

          <button
            type="button"
            onClick={() => {
              router.push("/dashboard");
            }}
            className="rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-6 py-3 text-sm font-black text-slate-400 transition hover:border-cyan-300/20 hover:bg-blue-500/[0.08] hover:text-cyan-200"
          >
            Return to Dashboard
          </button>
        </div>

        <div className="mt-6 flex items-center justify-center gap-2">
          <span className="midnight-status-dot h-2 w-2 rounded-full bg-emerald-400" />

          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-600">
            System protection remains active
          </p>
        </div>
      </section>
    </main>
  );
}