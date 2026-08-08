"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function GlobalError({
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
      "Blue-Trading-AI global error:",
      error,
    );
  }, [error]);

  return (
    <html lang="en">
      <body className="bg-[#030712] text-white">
        <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,rgba(37,99,235,0.15),transparent_34%),linear-gradient(180deg,#050b16_0%,#020617_100%)] p-5">
          <section className="w-full max-w-xl rounded-3xl border border-blue-400/10 bg-[#07101f]/95 p-6 text-center shadow-[0_28px_90px_rgba(0,0,0,0.55)] sm:p-8">
            <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-3xl border border-rose-400/20 bg-rose-400/[0.06] text-3xl font-black text-rose-300 shadow-[0_0_30px_rgba(251,113,133,0.16)]">
              !
            </div>

            <p className="mt-6 text-[10px] font-black uppercase tracking-[0.24em] text-slate-600">
              Global Recovery
            </p>

            <h1 className="mt-2 text-2xl font-black tracking-tight text-white sm:text-3xl">
              Blue-Trading-AI could not continue
            </h1>

            <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-slate-500">
              A critical interface error occurred. Your account,
              stored data, and backend services were not changed.
            </p>

            <div className="mt-6 rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4 text-left">
              <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-600">
                Error details
              </p>

              <p className="mt-2 break-words text-xs leading-5 text-slate-400">
                {error.message ||
                  "An unexpected global application error occurred."}
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
                className="rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 px-6 py-3 text-sm font-black text-white shadow-[0_0_24px_rgba(37,99,235,0.2)] transition hover:brightness-110"
              >
                Try Again
              </button>

              <button
                type="button"
                onClick={() => {
                  router.push("/");
                }}
                className="rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-6 py-3 text-sm font-black text-slate-400 transition hover:border-cyan-300/20 hover:bg-blue-500/[0.08] hover:text-cyan-200"
              >
                Return Home
              </button>
            </div>

            <div className="mt-6 flex items-center justify-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]" />

              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-600">
                Backend protection remains active
              </p>
            </div>
          </section>
        </main>
      </body>
    </html>
  );
}