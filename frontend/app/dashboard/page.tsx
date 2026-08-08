import { LiveLatestSignalCard } from "@/components/dashboard/live-latest-signal-card";
import { SignalQualityMetrics } from "@/components/dashboard/signal-quality-metrics";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <SignalQualityMetrics />

      <section className="grid gap-6 xl:grid-cols-[1.38fr_0.62fr]">
        <article className="midnight-panel overflow-hidden rounded-3xl">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b midnight-divider p-5 sm:p-6">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.22em] text-slate-600">
                Market Intelligence
              </p>

              <div className="mt-2 flex flex-wrap items-center gap-3">
                <h2 className="text-xl font-black text-white">
                  XAUUSD
                </h2>

                <span className="text-sm font-semibold text-slate-600">
                  Gold / US Dollar
                </span>

                <span className="rounded-full border border-emerald-400/15 bg-emerald-400/[0.06] px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.14em] text-emerald-300">
                  Market active
                </span>
              </div>
            </div>

            <div
              className="flex flex-wrap gap-2"
              aria-label="Chart timeframe"
            >
              {[
                "15M",
                "1H",
                "4H",
                "1D",
              ].map((timeframe) => (
                <button
                  key={timeframe}
                  type="button"
                  aria-pressed={
                    timeframe === "1H"
                  }
                  className={`rounded-xl px-3.5 py-2 text-xs font-black transition ${
                    timeframe === "1H"
                      ? "border border-cyan-300/25 bg-gradient-to-r from-blue-600 to-cyan-500 text-white shadow-[0_0_22px_rgba(37,99,235,0.24)]"
                      : "border border-blue-400/10 bg-blue-500/[0.03] text-slate-600 hover:border-cyan-300/20 hover:text-cyan-200"
                  }`}
                >
                  {timeframe}
                </button>
              ))}
            </div>
          </div>

          <div className="relative h-[430px] overflow-hidden bg-[#030817]">
            <div className="absolute inset-0 bg-[linear-gradient(rgba(59,130,246,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(59,130,246,0.04)_1px,transparent_1px)] bg-[size:40px_40px]" />

            <div className="absolute left-6 top-6 z-10 flex flex-wrap gap-2">
              {[
                "BOS",
                "CHoCH",
                "Order Block",
                "Liquidity",
              ].map((label) => (
                <span
                  key={label}
                  className="rounded-full border border-blue-400/10 bg-[#07101f]/80 px-3 py-1.5 text-[10px] font-black uppercase tracking-[0.14em] text-slate-500 backdrop-blur"
                >
                  {label}
                </span>
              ))}
            </div>

            <div className="relative z-10 flex h-full items-center justify-center p-6 text-center">
              <div>
                <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-3xl border border-cyan-300/20 bg-gradient-to-br from-blue-600/20 to-cyan-300/10 text-3xl text-cyan-200 shadow-[0_0_34px_rgba(37,99,235,0.24)]">
                  ◫
                </div>

                <p className="mt-5 text-sm font-black text-slate-200">
                  Live candlestick chart
                </p>

                <p className="mx-auto mt-2 max-w-md text-xs leading-6 text-slate-600">
                  BOS, CHoCH, order blocks, liquidity zones,
                  support, resistance and trade levels will
                  appear here when chart integration is connected.
                </p>
              </div>
            </div>

            <div className="absolute bottom-5 left-5 right-5 z-10 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-blue-400/10 bg-[#07101f]/80 px-4 py-3 backdrop-blur">
              <div className="flex items-center gap-2">
                <span className="midnight-status-dot h-2 w-2 rounded-full bg-emerald-400" />

                <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">
                  Live market feed
                </p>
              </div>

              <p className="text-[10px] font-semibold text-slate-600">
                Multi-timeframe analysis enabled
              </p>
            </div>
          </div>
        </article>

        <LiveLatestSignalCard />
      </section>
    </div>
  );
}