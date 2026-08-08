export default function DashboardLoading() {
  return (
    <main className="midnight-page min-h-screen p-5 text-white sm:p-8">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="h-3 w-32 animate-pulse rounded-full bg-blue-500/10" />
            <div className="mt-3 h-8 w-56 animate-pulse rounded-xl bg-blue-500/10" />
          </div>

          <div className="h-11 w-32 animate-pulse rounded-xl border border-blue-400/10 bg-blue-500/[0.04]" />
        </div>

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <article
              key={index}
              className="midnight-card rounded-2xl p-5"
            >
              <div className="h-3 w-36 animate-pulse rounded-full bg-blue-500/10" />

              <div className="mt-4 h-9 w-20 animate-pulse rounded-xl bg-gradient-to-r from-blue-500/10 to-cyan-300/10" />

              <div className="mt-3 h-3 w-28 animate-pulse rounded-full bg-blue-500/[0.06]" />

              <div className="mt-5 flex items-center gap-2">
                <span className="midnight-pulse h-2 w-2 rounded-full bg-cyan-300" />

                <div className="h-2.5 w-24 animate-pulse rounded-full bg-blue-500/[0.06]" />
              </div>
            </article>
          ))}
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.38fr_0.62fr]">
          <article className="midnight-panel overflow-hidden rounded-3xl">
            <div className="flex items-center justify-between gap-4 border-b midnight-divider p-6">
              <div>
                <div className="h-3 w-28 animate-pulse rounded-full bg-blue-500/10" />
                <div className="mt-3 h-7 w-52 animate-pulse rounded-xl bg-blue-500/10" />
              </div>

              <div className="flex gap-2">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div
                    key={index}
                    className="h-9 w-12 animate-pulse rounded-xl border border-blue-400/10 bg-blue-500/[0.04]"
                  />
                ))}
              </div>
            </div>

            <div className="relative flex h-[430px] items-center justify-center overflow-hidden bg-[#030817]">
              <div className="absolute inset-0 bg-[linear-gradient(rgba(59,130,246,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(59,130,246,0.04)_1px,transparent_1px)] bg-[size:40px_40px]" />

              <div className="relative z-10 text-center">
                <div className="midnight-pulse mx-auto h-20 w-20 rounded-3xl border border-cyan-300/15 bg-gradient-to-br from-blue-600/15 to-cyan-300/[0.06]" />

                <div className="mx-auto mt-5 h-4 w-36 animate-pulse rounded-full bg-blue-500/10" />

                <div className="mx-auto mt-3 h-3 w-64 animate-pulse rounded-full bg-blue-500/[0.06]" />
              </div>
            </div>
          </article>

          <article className="midnight-panel rounded-3xl p-6">
            <div className="flex items-start justify-between">
              <div>
                <div className="h-3 w-40 animate-pulse rounded-full bg-blue-500/10" />
                <div className="mt-3 h-7 w-28 animate-pulse rounded-xl bg-blue-500/10" />
              </div>

              <div className="h-8 w-16 animate-pulse rounded-full bg-emerald-400/10" />
            </div>

            <div className="mt-5 h-24 animate-pulse rounded-2xl border border-blue-400/10 bg-blue-500/[0.035]" />

            <div className="mt-4 grid grid-cols-2 gap-3">
              {Array.from({ length: 4 }).map((_, index) => (
                <div
                  key={index}
                  className="h-20 animate-pulse rounded-2xl border border-blue-400/10 bg-blue-500/[0.03]"
                />
              ))}
            </div>

            <div className="mt-5 space-y-2">
              {Array.from({ length: 5 }).map((_, index) => (
                <div
                  key={index}
                  className="h-11 animate-pulse rounded-xl border border-blue-400/10 bg-blue-500/[0.025]"
                />
              ))}
            </div>

            <div className="mt-5 h-12 animate-pulse rounded-xl bg-gradient-to-r from-blue-600/20 to-cyan-400/20" />
          </article>
        </section>
      </div>
    </main>
  );
}