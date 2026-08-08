"use client";

import { useEffect } from "react";

type MarketStructureErrorProps = {
  error: Error & {
    digest?: string;
  };
  reset: () => void;
};

export default function MarketStructureError({
  error,
  reset,
}: MarketStructureErrorProps) {
  useEffect(() => {
    console.error(
      "Market Structure page error:",
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
          Structure Engine Error
        </p>

        <h1 className="mt-2 text-3xl font-black tracking-tight text-white">
          Unable to load market structure
        </h1>

        <p className="mx-auto mt-4 max-w-md text-sm leading-6 text-slate-500">
          Blue-Trading-AI could not load swing points,
          BOS, CHoCH, support and resistance, or trend-bias
          information. This may be caused by a temporary
          backend, market-data, network, or authentication issue.
        </p>

        <div className="mt-6 rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4 text-left">
          <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-600">
            Safety behaviour
          </p>

          <p className="mt-2 text-xs leading-5 text-slate-500">
            No signal will be approved while market structure,
            multi-timeframe alignment, and structural confirmation
            are unavailable.
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
          Retry Structure Analysis
        </button>
      </div>
    </section>
  );
}