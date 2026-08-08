import Link from "next/link";

export default function NotFoundPage() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#030712] px-6 py-12">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-[-180px] h-[420px] w-[420px] -translate-x-1/2 rounded-full bg-blue-600/10 blur-[120px]" />
        <div className="absolute bottom-[-180px] right-[-120px] h-[360px] w-[360px] rounded-full bg-cyan-400/[0.07] blur-[110px]" />
      </div>

      <section className="midnight-panel relative w-full max-w-2xl rounded-3xl p-8 text-center sm:p-12">
        <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-3xl border border-cyan-300/20 bg-blue-500/[0.06] text-3xl font-black text-cyan-200 shadow-[0_0_35px_rgba(34,211,238,0.12)]">
          404
        </div>

        <p className="mt-7 text-[10px] font-black uppercase tracking-[0.24em] text-cyan-300">
          Route Not Found
        </p>

        <h1 className="mt-3 text-3xl font-black tracking-tight text-white sm:text-4xl">
          This Blue-Trading-AI page does not exist
        </h1>

        <p className="mx-auto mt-4 max-w-lg text-sm leading-6 text-slate-500">
          The address may be incorrect, the page may have
          moved, or your account may not have access to the
          requested section.
        </p>

        <div className="mt-7 rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-5 text-left">
          <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-600">
            Safe recovery
          </p>

          <p className="mt-2 text-xs leading-5 text-slate-500">
            Return to the dashboard to continue using verified
            analysis, approved signals, market structure,
            performance, news, and monitoring tools.
          </p>
        </div>

        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
          <Link
            href="/dashboard"
            className="midnight-button rounded-xl px-7 py-3 text-sm font-black"
          >
            Return to Dashboard
          </Link>

          <Link
            href="/login"
            className="rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-7 py-3 text-sm font-black text-cyan-200 transition hover:border-cyan-300/20 hover:bg-blue-500/[0.08]"
          >
            Go to Login
          </Link>
        </div>

        <p className="mt-7 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-700">
          Blue-Trading-AI · Protected Analysis Platform
        </p>
      </section>
    </main>
  );
}