export default function HistoryLoading() {
  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="space-y-3">
          <div className="h-3 w-40 animate-pulse rounded-full bg-blue-400/10" />
          <div className="h-9 w-64 max-w-full animate-pulse rounded-xl bg-blue-400/10" />
          <div className="h-4 w-full max-w-2xl animate-pulse rounded-full bg-blue-400/[0.07]" />
          <div className="h-4 w-4/5 max-w-xl animate-pulse rounded-full bg-blue-400/[0.07]" />
        </div>

        <div className="h-16 w-full animate-pulse rounded-2xl border border-blue-400/10 bg-blue-500/[0.04] xl:w-72" />
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <article
            key={index}
            className="midnight-panel rounded-2xl p-5"
          >
            <div className="h-3 w-28 animate-pulse rounded-full bg-blue-400/10" />
            <div className="mt-4 h-9 w-20 animate-pulse rounded-lg bg-blue-400/10" />
            <div className="mt-3 h-3 w-40 animate-pulse rounded-full bg-blue-400/[0.07]" />
          </article>
        ))}
      </section>

      <section className="midnight-panel rounded-3xl p-5">
        <div className="flex items-center justify-between gap-4">
          <div className="space-y-3">
            <div className="h-3 w-32 animate-pulse rounded-full bg-blue-400/10" />
            <div className="h-6 w-52 animate-pulse rounded-lg bg-blue-400/10" />
          </div>

          <div className="h-4 w-24 animate-pulse rounded-full bg-blue-400/10" />
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={index}
              className="space-y-2"
            >
              <div className="h-3 w-20 animate-pulse rounded-full bg-blue-400/10" />
              <div className="h-12 animate-pulse rounded-xl border border-blue-400/10 bg-blue-500/[0.035]" />
            </div>
          ))}
        </div>
      </section>

      <section className="midnight-panel overflow-hidden rounded-3xl">
        <div className="flex items-center justify-between border-b border-blue-400/10 p-5">
          <div className="space-y-3">
            <div className="h-3 w-32 animate-pulse rounded-full bg-blue-400/10" />
            <div className="h-6 w-56 animate-pulse rounded-lg bg-blue-400/10" />
          </div>

          <div className="h-9 w-56 animate-pulse rounded-xl bg-blue-400/[0.07]" />
        </div>

        <div className="overflow-x-auto border-b border-blue-400/10">
          <div className="min-w-[1100px] px-5 py-4">
            <div className="grid grid-cols-11 gap-4">
              {Array.from({ length: 11 }).map((_, index) => (
                <div
                  key={index}
                  className="h-3 animate-pulse rounded-full bg-blue-400/10"
                />
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-3 p-5">
          {Array.from({ length: 5 }).map((_, rowIndex) => (
            <div
              key={rowIndex}
              className="min-w-[1100px] grid grid-cols-11 gap-4 rounded-2xl border border-blue-400/10 bg-blue-500/[0.025] p-4"
            >
              {Array.from({ length: 11 }).map((_, columnIndex) => (
                <div
                  key={columnIndex}
                  className="h-4 animate-pulse rounded-full bg-blue-400/[0.07]"
                />
              ))}
            </div>
          ))}
        </div>
      </section>

      <section className="midnight-panel rounded-3xl p-5">
        <div className="h-3 w-28 animate-pulse rounded-full bg-blue-400/10" />
        <div className="mt-3 h-6 w-48 animate-pulse rounded-lg bg-blue-400/10" />

        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div
              key={index}
              className="h-16 animate-pulse rounded-2xl border border-blue-400/10 bg-blue-500/[0.035]"
            />
          ))}
        </div>
      </section>
    </div>
  );
}