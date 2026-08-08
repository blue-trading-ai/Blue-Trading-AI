"use client";

export type TradingSignal = {
  id: string;
  symbol: string;
  timeframe: string;
  direction: "BUY" | "SELL";
  entry: number | string;
  stopLoss: number | string;
  takeProfit1: number | string;
  takeProfit2?: number | string | null;
  confidence: number;
  confirmations: number;
  riskReward: number | string;
  marketStructure?: string | null;
  status?: "ACTIVE" | "PENDING" | "CLOSED";
  createdAt?: string | null;
  reasons?: string[];
};

type SignalCardProps = {
  signal: TradingSignal;
};

function formatValue(
  value: number | string | null | undefined,
): string {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "—";
  }

  const text = String(value).trim();

  return text || "—";
}

function formatRiskReward(
  value: number | string | null | undefined,
): string {
  const formatted = formatValue(value);

  if (formatted === "—") {
    return formatted;
  }

  if (/^1\s*:/i.test(formatted)) {
    return formatted.replace(/\s+/g, "");
  }

  return `1:${formatted}`;
}

function getSafeConfidence(
  value: number,
): number {
  if (!Number.isFinite(value)) {
    return 0;
  }

  return Math.min(
    Math.max(Math.round(value), 0),
    100,
  );
}

function getSafeConfirmations(
  value: number,
): number {
  if (!Number.isFinite(value)) {
    return 0;
  }

  return Math.max(
    Math.trunc(value),
    0,
  );
}

function formatPublishedAt(
  value: string | null | undefined,
): string | null {
  if (!value?.trim()) {
    return null;
  }

  const timestamp = Date.parse(value);

  if (!Number.isFinite(timestamp)) {
    return value.trim();
  }

  return new Intl.DateTimeFormat(
    undefined,
    {
      dateStyle: "medium",
      timeStyle: "short",
    },
  ).format(new Date(timestamp));
}

function getStatusPresentation(
  status: TradingSignal["status"],
): {
  label: string;
  dotClassName: string;
  textClassName: string;
} {
  switch (status) {
    case "PENDING":
      return {
        label: "PENDING",
        dotClassName: "bg-amber-300",
        textClassName: "text-amber-300",
      };

    case "CLOSED":
      return {
        label: "CLOSED",
        dotClassName: "bg-slate-500",
        textClassName: "text-slate-400",
      };

    case "ACTIVE":
    default:
      return {
        label: "ACTIVE",
        dotClassName: "bg-emerald-400",
        textClassName: "text-emerald-300",
      };
  }
}

export function SignalCard({
  signal,
}: SignalCardProps) {
  const isBuy =
    signal.direction === "BUY";

  const directionStyle = isBuy
    ? "border-emerald-400/20 bg-emerald-400/[0.06] text-emerald-300"
    : "border-rose-400/20 bg-rose-400/[0.06] text-rose-300";

  const statusPresentation =
    getStatusPresentation(
      signal.status ?? "ACTIVE",
    );

  const confidence =
    getSafeConfidence(
      signal.confidence,
    );

  const confirmations =
    getSafeConfirmations(
      signal.confirmations,
    );

  const publishedAt =
    formatPublishedAt(
      signal.createdAt,
    );

  const reasons = Array.from(
    new Set(
      (signal.reasons ?? [])
        .map((reason) =>
          reason.trim(),
        )
        .filter(Boolean),
    ),
  );

  const metricItems = [
    {
      label: "Entry",
      value: formatValue(
        signal.entry,
      ),
    },
    {
      label: "Stop Loss",
      value: formatValue(
        signal.stopLoss,
      ),
    },
    {
      label: "Take Profit 1",
      value: formatValue(
        signal.takeProfit1,
      ),
    },
    {
      label: "Take Profit 2",
      value: formatValue(
        signal.takeProfit2,
      ),
    },
    {
      label: "Risk–Reward",
      value: formatRiskReward(
        signal.riskReward,
      ),
    },
  ];

  return (
    <article className="midnight-panel overflow-hidden rounded-3xl">
      <div className="flex flex-col gap-4 border-b border-blue-400/10 p-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="break-all text-xl font-black text-white">
              {formatValue(
                signal.symbol,
              )}
            </h3>

            <span className="rounded-full border border-blue-400/10 bg-blue-500/[0.04] px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.12em] text-cyan-200">
              {formatValue(
                signal.timeframe,
              )}
            </span>

            <span
              className={`rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.12em] ${directionStyle}`}
            >
              {signal.direction}
            </span>
          </div>

          <p className="mt-2 break-all text-[10px] font-bold uppercase tracking-[0.12em] text-slate-600">
            Signal ID:{" "}
            {formatValue(signal.id)}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <span
            className={`midnight-status-dot h-2.5 w-2.5 rounded-full ${statusPresentation.dotClassName}`}
          />

          <span
            className={`text-[10px] font-black uppercase tracking-[0.14em] ${statusPresentation.textClassName}`}
          >
            {statusPresentation.label}
          </span>
        </div>
      </div>

      <div className="grid gap-3 p-5 sm:grid-cols-2 xl:grid-cols-5">
        {metricItems.map((item) => (
          <div
            key={item.label}
            className="rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4"
          >
            <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
              {item.label}
            </p>

            <p className="mt-2 break-words text-sm font-black text-white">
              {item.value}
            </p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 border-t border-blue-400/10 p-5 md:grid-cols-3">
        <div className="rounded-2xl border border-cyan-300/15 bg-cyan-300/[0.04] p-4">
          <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
            Confidence
          </p>

          <div className="mt-3 flex items-center justify-between gap-3">
            <p className="text-2xl font-black text-cyan-200">
              {confidence}%
            </p>

            <div
              className="h-2 flex-1 overflow-hidden rounded-full bg-slate-900"
              aria-label={`Confidence ${confidence}%`}
            >
              <div
                className="h-full rounded-full bg-gradient-to-r from-blue-600 to-cyan-300"
                style={{
                  width: `${confidence}%`,
                }}
              />
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4">
          <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
            Confirmations
          </p>

          <p className="mt-3 text-2xl font-black text-white">
            {confirmations}
          </p>

          <p className="mt-1 text-[10px] text-slate-600">
            Minimum required: 3
          </p>
        </div>

        <div className="rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4">
          <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
            Market Structure
          </p>

          <p className="mt-3 break-words text-sm font-black text-white">
            {signal.marketStructure?.trim() ||
              "Not provided"}
          </p>

          <p className="mt-1 text-[10px] text-slate-600">
            Backend analysis result
          </p>
        </div>
      </div>

      {reasons.length > 0 ? (
        <div className="border-t border-blue-400/10 p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
            Signal Confirmations
          </p>

          <div className="mt-3 flex flex-wrap gap-2">
            {reasons.map(
              (reason, index) => (
                <span
                  key={`${reason}-${index}`}
                  className="rounded-full border border-blue-400/10 bg-blue-500/[0.04] px-3 py-1.5 text-[10px] font-bold text-slate-400"
                >
                  {reason}
                </span>
              ),
            )}
          </div>
        </div>
      ) : null}

      {publishedAt ? (
        <div className="border-t border-blue-400/10 px-5 py-3">
          <p className="text-right text-[10px] font-bold uppercase tracking-[0.12em] text-slate-700">
            Published {publishedAt}
          </p>
        </div>
      ) : null}
    </article>
  );
}