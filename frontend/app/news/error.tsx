"use client";

import { useEffect } from "react";

type NewsErrorProps = {
  error: Error & {
    digest?: string;
  };
  reset: () => void;
};

export default function NewsError({
  error,
  reset,
}: NewsErrorProps) {
  useEffect(() => {
    console.error(
      "Market News page error:",
      error,
    );
  }, [error]);

  return (
    <section className="midnight-panel flex min-h-[520px] items-center justify-center rounded-3xl p-6">
      <div className="w-full max-w-lg text-center">
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-3xl border border-amber-300/20 bg-amber-400/[0.06] text-3xl font-black text-amber-300 shadow-[0_0_30px_rgba(252,211,77,0.14)]">
          !
        </div>

        <p className="mt-6 text-[10px] font-black uppercase tracking-[0.22em] text-amber-300">
          Market News Error
        </p>

        <h1 className="mt-2 text-3xl font-black tracking-tight text-white">
          Unable to load market news
        </h1>

        <p className="mx-auto mt-4 max-w-md text-sm leading-6 text-slate-500">
          Blue-Trading-AI could not load economic events,
          impact levels, affected markets, or news-conflict
          data. This may be caused by a temporary backend,
          provider, network, or authentication issue.
        </p>

        <div className="mt-6 rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4 text-left">
          <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-600">
            Protection behaviour
          </p>

          <p className="mt-2 text-xs leading-5 text-slate-500">
            Blue-Trading-AI will not mark a market as safe,
            approve a news-sensitive setup, or display
            estimated event data while the verified news
            source is unavailable.
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
          Retry Market News
        </button>
      </div>
    </section>
  );
}