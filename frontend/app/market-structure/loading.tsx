export default function MarketStructureLoading() {
  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="space-y-3">
          <div className="h-3 w-40 animate-pulse rounded-full bg-blue-400/10" />
          <div className="h-9 w-80 max-w-full animate-pulse rounded-xl bg-blue-400/10" />
          <div className="h-4 w-full max-w-2xl animate-pulse rounded-full bg-blue-400/[0.07]" />
          <div className="h-4 w-4/5 max-w-xl animate-pulse rounded-full bg-blue-400/[0.07]" />
        </div>

        <div className="h-16 w-full animate-pulse rounded-2xl border border-blue-400/10 bg-blue-500/[0.04] xl:w-72" />
      </section>

      <section className="midnight-panel rounded-3xl p-5">
        <div className="grid gap-4 lg:grid-cols-[1fr_1fr_auto] lg:items-end">
          <div className="space-y-2">
            <div className="h-3 w-20 animate-pulse rounded-full bg-blue-400/10" />
            <div className="h-12 animate-pulse rounded-xl border border-blue-400/10 bg-blue-500/[0.035]" />
          </div>

          <div className="space-y-2">
            <div className="h-3 w-24 animate-pulse rounded-full bg-blue-400/10" />
            <div className="h-12 animate-pulse rounded-xl border border-blue-400/10 bg-blue-500/[0.035]" />
          </div>

          <div className="h-12 w-full animate-pulse rounded-xl bg-blue-400/10 lg:w-44" />
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <article
            key={index}
            className="midnight-panel rounded-2xl p-5"
          >
            <div className="h-3 w-28 animate-pulse rounded-full bg-blue-400/10" />
            <div className="mt-4 h-8 w-24 animate-pulse rounded-lg bg-blue-400/10" />
            <div className="mt-3 h-3 w-40 animate-pulse rounded-full bg-blue-400/[0.07]" />
          </article>
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="midnight-panel overflow-hidden rounded-3xl">
          <div className="border-b border-blue-400/10 p-5">
            <div className="h-3 w-32 animate-pulse rounded-full bg-blue-400/10" />
            <div className="mt-3 h-6 w-40 animate-pulse rounded-lg bg-blue-400/10" />
          </div>

          <div className="flex min-h-[430px] items-center justify-center p-6">
            <div className="w-full max-w-md space-y-4 text-center">
              <div className="midnight-pulse mx-auto h-16 w-16 rounded-2xl border border-cyan-300/20 bg-blue-500/[0.06]" />
              <div className="mx-auto h-6 w-64 animate-pulse rounded-lg bg-blue-400/10" />
              <div className="mx-auto h-4 w-full animate-pulse rounded-full bg-blue-400/[0.07]" />
              <div className="mx-auto h-4 w-4/5 animate-pulse rounded-full bg-blue-400/[0.07]" />
            </div>
          </div>
        </div>

        <aside className="midnight-panel rounded-3xl p-5">
          <div className="h-3 w-36 animate-pulse rounded-full bg-blue-400/10" />
          <div className="mt-3 h-6 w-44 animate-pulse rounded-lg bg-blue-400/10" />

          <div className="mt-5 space-y-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <div
                key={index}
                className="h-16 animate-pulse rounded-2xl border border-blue-400/10 bg-blue-500/[0.035]"
              />
            ))}
          </div>
        </aside>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <article
            key={index}
            className="midnight-panel rounded-2xl p-5"
          >
            <div className="flex items-center justify-between gap-3">
              <div className="h-5 w-32 animate-pulse rounded-lg bg-blue-400/10" />
              <div className="h-6 w-16 animate-pulse rounded-full bg-blue-400/[0.07]" />
            </div>

            <div className="mt-4 h-3 w-full animate-pulse rounded-full bg-blue-400/[0.07]" />
            <div className="mt-2 h-3 w-4/5 animate-pulse rounded-full bg-blue-400/[0.07]" />
          </article>
        ))}
      </section>
    </div>
  );
}