export default function GlobalLoading() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#030712] px-6 py-12">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-[-180px] h-[420px] w-[420px] -translate-x-1/2 rounded-full bg-blue-600/10 blur-[120px]" />
        <div className="absolute bottom-[-180px] right-[-120px] h-[360px] w-[360px] rounded-full bg-cyan-400/[0.07] blur-[110px]" />
      </div>

      <section className="midnight-panel relative w-full max-w-xl rounded-3xl p-8 text-center sm:p-12">
        <div className="relative mx-auto h-24 w-24">
          <div className="absolute inset-0 animate-ping rounded-3xl border border-cyan-300/20 bg-cyan-300/[0.04]" />

          <div className="relative flex h-24 w-24 items-center justify-center rounded-3xl border border-cyan-300/20 bg-blue-500/[0.06] shadow-[0_0_35px_rgba(34,211,238,0.14)]">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-blue-400/15 border-t-cyan-300" />
          </div>
        </div>

        <p className="mt-7 text-[10px] font-black uppercase tracking-[0.24em] text-cyan-300">
          Blue-Trading-AI
        </p>

        <h1 className="mt-3 text-2xl font-black tracking-tight text-white sm:text-3xl">
          Loading protected intelligence
        </h1>

        <p className="mx-auto mt-4 max-w-md text-sm leading-6 text-slate-500">
          Preparing verified analysis, approved signals,
          market structure, performance data, news protection,
          and system monitoring.
        </p>

        <div className="mt-7 overflow-hidden rounded-full border border-blue-400/10 bg-slate-950/70 p-1">
          <div className="h-2 w-2/3 animate-pulse rounded-full bg-gradient-to-r from-blue-600 to-cyan-300" />
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          {[
            "Authenticating",
            "Loading Services",
            "Verifying Data",
          ].map((label) => (
            <div
              key={label}
              className="rounded-xl border border-blue-400/10 bg-blue-500/[0.035] px-3 py-3"
            >
              <p className="text-[10px] font-black uppercase tracking-[0.12em] text-slate-600">
                {label}
              </p>
            </div>
          ))}
        </div>

        <p className="mt-7 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-700">
          Protected Analysis Platform
        </p>
      </section>
    </main>
  );
}