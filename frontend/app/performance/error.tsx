"use client";

import { useEffect } from "react";

type PerformanceErrorProps = {
  error: Error & {
    digest?: string;
  };
  reset: () => void;
};

export default function PerformanceError({
  error,
  reset,
}: PerformanceErrorProps) {
  useEffect(() => {
    console.error(
      "Performance page error:",
      error,
    );
  }, [error]);

  return (
    <section className="midnight-panel flex min-h-[520px] items-center justify-center rounded-3xl p-6">
      <div className="w-full max-w-lg text-center">
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-3xl border border-rose-400/20 bg-rose-400/[0.06] text-3xl font-black text-rose-300 shadow-[0_0_30px_rgba(251,113,133,0.14)]">
          !
        </div>

        <p className="mt-6 text-[10px] font-black uppercase tracking-[0.22em] text-rose-300">
          Performance Data Error
        </p>

        <h1 className="mt-2 text-3xl font-black tracking-tight text-white">
          Unable to load performance statistics
        </h1>

        <p className="mx-auto mt-4 max-w-md text-sm leading-6 text-slate-500">
          Blue-Trading-AI could not load win rate,
          signal outcomes, risk–reward, drawdown, or
          market performance. This may be caused by a
          temporary backend, database, network, or
          authentication issue.
        </p>

        <div className="mt-6 rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4 text-left">
          <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-600">
            Data integrity behaviour
          </p>

          <p className="mt-2 text-xs leading-5 text-slate-500">
            Blue-Trading-AI will not display estimated,
            incomplete, or unverified performance results
            while the official statistics source is unavailable.
          </p>
        </div>

        {error.digest ? (
          <p className="mt-4 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-700">
            Error reference: {error.digest}
          </p>
        ) : null}

        <button
          type="button"
          onClick={reset}
          className="midnight-button mt-7 rounded-xl px-7 py-3 text-sm font-black"
        >
          Retry Performance Data
        </button>
      </div>
    </section>
  );
}