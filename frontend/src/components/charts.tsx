import { inr, inrCompact } from "../lib/format";
import { LEVEL_FILL } from "./ui";

export const SERIES = { one: "rgb(var(--series-1))", two: "rgb(var(--series-2))", three: "rgb(var(--series-3))", accent: "rgb(var(--series-accent))", mark: "rgb(var(--mark))" };

/** Recessive axes and hairline grid, shared by every Recharts chart. */
export const AXIS = { tick: { fill: "rgb(var(--muted))", fontSize: 11 }, stroke: "rgb(var(--line))", tickLine: false } as const;
export const GRID = { stroke: "rgb(var(--line))", vertical: false } as const;

interface TooltipEntry { name?: string | number; value?: unknown; color?: string; dataKey?: string | number }

export function ChartTooltip({ active, payload, label, format }: {
  active?: boolean; payload?: readonly TooltipEntry[]; label?: string | number; format?: (value: number, name: string) => string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded border border-line bg-surface px-3 py-2 text-xs shadow-sm">
      {label !== undefined && <p className="mb-1 font-medium">{label}</p>}
      {payload.filter((p) => p.value != null).map((p) => (
        <p key={String(p.dataKey)} className="flex items-center gap-2 text-muted">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: p.color }} />
          {p.name}: <span className="font-medium text-fg">{format ? format(Number(p.value), String(p.name)) : String(p.value)}</span>
        </p>
      ))}
    </div>
  );
}

export function Legend({ items }: { items: { label: string; color: string; dashed?: boolean; dot?: boolean }[] }) {
  return (
    <div className="mb-2 flex flex-wrap gap-4 text-xs text-muted">
      {items.map((item) => (
        <span key={item.label} className="inline-flex items-center gap-1.5">
          {item.dot
            ? <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: item.color }} />
            : <span className="inline-block w-5 border-t-2" style={{ borderColor: item.color, borderStyle: item.dashed ? "dashed" : "solid" }} />}
          {item.label}
        </span>
      ))}
    </div>
  );
}

/** A 0 to 1 semicircle with the tier cut-offs marked. */
export function RiskGauge({ risk, level, cuts }: { risk: number; level: string; cuts: number[] }) {
  const radius = 80;
  const point = (t: number, r = radius) => {
    const angle = Math.PI * (1 - t);
    return [100 + r * Math.cos(angle), 100 - r * Math.sin(angle)];
  };
  const [x, y] = point(Math.min(risk, 0.999));
  return (
    <svg viewBox="0 0 200 118" className="w-full max-w-[220px]" role="img" aria-label={`Risk score ${risk.toFixed(2)}, ${level}`}>
      <path d={`M 20 100 A ${radius} ${radius} 0 0 1 180 100`} fill="none" stroke="rgb(var(--line))" strokeWidth="14" />
      <path d={`M 20 100 A ${radius} ${radius} 0 0 1 ${x} ${y}`} fill="none" stroke={LEVEL_FILL[level]} strokeWidth="14" />
      {cuts.map((t) => {
        const [x1, y1] = point(t, 70);
        const [x2, y2] = point(t, 90);
        return <line key={t} x1={x1} y1={y1} x2={x2} y2={y2} stroke="rgb(var(--surface))" strokeWidth="2" />;
      })}
      <text x="100" y="92" textAnchor="middle" className="fill-fg font-serif" fontSize="34" fontWeight="500">{risk.toFixed(2)}</text>
      <text x="100" y="112" textAnchor="middle" className="fill-muted" fontSize="11">risk score</text>
    </svg>
  );
}

export function Meter({ label, hint, value, color = "rgb(var(--accent))" }: { label: string; hint?: string; value: number | null; color?: string }) {
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
        <span>{label}{hint && <span className="ml-2 text-xs text-muted">{hint}</span>}</span>
        <span className="tabular-nums font-medium">{value == null ? "Not run" : value.toFixed(2)}</span>
      </div>
      <div className="h-2 rounded bg-bg">{value != null && <div className="h-2 rounded" style={{ width: `${Math.max(value * 100, 1)}%`, background: color }} />}</div>
    </div>
  );
}

/** This event against the vendor's normal range, on a log scale so a 10x spike still fits. */
export function RangeStrip({ amount, p10, p50, p90 }: { amount: number; p10: number; p50: number; p90: number }) {
  const low = Math.log(Math.min(p10, amount) / 1.3);
  const high = Math.log(Math.max(p90, amount) * 1.3);
  const at = (value: number) => ((Math.log(value) - low) / (high - low)) * 100;
  const event = at(amount);
  const place = event > 70 ? "right-0 text-right" : event < 30 ? "left-0" : "-translate-x-1/2";
  return (
    <div role="img" aria-label={`This invoice ${inr(amount)}. Usual range ${inr(p10)} to ${inr(p90)}, median ${inr(p50)}.`}>
      <div className="relative h-24">
        <div className={`absolute top-0 whitespace-nowrap text-xs ${place}`} style={place.includes("translate") ? { left: `${event}%` } : undefined}>
          <span className="font-semibold">This invoice</span> {inr(amount)}
        </div>
        <div className="absolute inset-x-0 top-[50px] h-px bg-line" />
        <div className="absolute top-10 h-5 rounded bg-olive-300" style={{ left: `${at(p10)}%`, width: `${Math.max(at(p90) - at(p10), 1)}%` }} />
        <div className="absolute top-9 h-7 w-0.5 bg-stone-800 dark:bg-cream-100" style={{ left: `${at(p50)}%` }} />
        <div className="absolute top-6 h-10 w-1 -translate-x-1/2 rounded-sm" style={{ left: `${event}%`, background: SERIES.mark }} />
        <div className="absolute top-[72px] whitespace-nowrap text-xs text-muted" style={{ left: `${Math.min(at(p10), 62)}%` }}>
          Usual {inr(p10)} to {inr(p90)}, median {inr(p50)}
        </div>
      </div>
    </div>
  );
}

export const axisAmount = (value: number) => inrCompact(value);
