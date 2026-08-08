export default function MonitoringLoading() {
  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="space-y-3">
          <div className="h-3 w-44 animate-pulse rounded-full bg-blue-400/10" />
          <div className="h-9 w-72 max-w-full animate-pulse rounded-xl bg-blue-400/10" />
          <div className="h-4 w-full max-w-2xl animate-pulse rounded-full bg-blue-400/[0.07]" />
          <div className="h-4 w-4/5 max-w-xl animate-pulse rounded-full bg-blue-400/[0.07]" />
        </div>

        <div className="h-16 w-full animate-pulse rounded-2xl border border-emerald-400/10 bg-emerald-400/[0.04] xl:w-72" />
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <article
            key={index}
            className="midnight-panel rounded-2xl p-5"
          >
            <div className="h-3 w-28 animate-pulse rounded-full bg-blue-400/10" />
            <div className="mt-4 h-9 w-24 animate-pulse rounded-lg bg-blue-400/10" />
            <div className="mt-3 h-3 w-40 animate-pulse rounded-full bg-blue-400/[0.07]" />
          </article>
        ))}
      </section>

      <section className="midnight-panel rounded-3xl p-5">
        <div className="flex items-center justify-between gap-4">
          <div className="space-y-3">
            <div className="h-3 w-36 animate-pulse rounded-full bg-blue-400/10" />
            <div className="h-6 w-56 animate-pulse rounded-lg bg-blue-400/10" />
          </div>

          <div className="h-4 w-24 animate-pulse rounded-full bg-blue-400/10" />
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          {Array.from({ length: 2 }).map((_, index) => (
            <div
              key={index}
              className="space-y-2"
            >
              <div className="h-3 w-24 animate-pulse rounded-full bg-blue-400/10" />
              <div className="h-12 animate-pulse rounded-xl border border-blue-400/10 bg-blue-500/[0.035]" />
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="midnight-panel overflow-hidden rounded-3xl">
          <div className="flex items-center justify-between border-b border-blue-400/10 p-5">
            <div className="space-y-3">
              <div className="h-3 w-28 animate-pulse rounded-full bg-blue-400/10" />
              <div className="h-6 w-48 animate-pulse rounded-lg bg-blue-400/10" />
            </div>

            <div className="h-9 w-48 animate-pulse rounded-xl bg-blue-400/[0.07]" />
          </div>

          <div className="grid gap-3 p-5 md:grid-cols-2">
            {Array.from({ length: 8 }).map((_, index) => (
              <article
                key={index}
                className="rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4"
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="h-4 w-32 animate-pulse rounded-full bg-blue-400/10" />
                  <div className="h-6 w-16 animate-pulse rounded-lg bg-blue-400/10" />
                </div>

                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <div className="h-3 w-16 animate-pulse rounded-full bg-blue-400/[0.07]" />
                    <div className="h-5 w-20 animate-pulse rounded-full bg-blue-400/10" />
                  </div>

                  <div className="space-y-2">
                    <div className="h-3 w-16 animate-pulse rounded-full bg-blue-400/[0.07]" />
                    <div className="h-5 w-20 animate-pulse rounded-full bg-blue-400/10" />
                  </div>
                </div>
              </article>
            ))}
          </div>
        </div>

        <aside className="space-y-6">
          <section className="midnight-panel rounded-3xl p-5">
            <div className="h-3 w-36 animate-pulse rounded-full bg-blue-400/10" />
            <div className="mt-3 h-6 w-52 animate-pulse rounded-lg bg-blue-400/10" />
            <div className="mt-5 h-64 animate-pulse rounded-2xl border border-amber-300/10 bg-amber-400/[0.035]" />
          </section>

          <section className="midnight-panel rounded-3xl p-5">
            <div className="h-3 w-32 animate-pulse rounded-full bg-blue-400/10" />
            <div className="mt-4 h-28 animate-pulse rounded-2xl border border-blue-400/10 bg-blue-500/[0.035]" />
          </section>
        </aside>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        {Array.from({ length: 2 }).map((_, sectionIndex) => (
          <article
            key={sectionIndex}
            className="midnight-panel rounded-3xl p-5"
          >
            <div className="h-3 w-32 animate-pulse rounded-full bg-blue-400/10" />
            <div className="mt-3 h-6 w-48 animate-pulse rounded-lg bg-blue-400/10" />

            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              {Array.from({ length: 4 }).map((_, index) => (
                <div
                  key={index}
                  className="h-20 animate-pulse rounded-2xl border border-blue-400/10 bg-blue-500/[0.035]"
                />
              ))}
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}