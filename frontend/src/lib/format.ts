export function inr(value: number | null | undefined): string {
  if (value == null) return "n/a";
  return `Rs. ${Math.round(value).toLocaleString("en-IN")}`;
}

/** Short axis labels using the Indian system: 4.8L, 1.2Cr. */
export function inrCompact(value: number): string {
  if (value >= 1e7) return `${+(value / 1e7).toFixed(1)}Cr`;
  if (value >= 1e5) return `${+(value / 1e5).toFixed(1)}L`;
  if (value >= 1e3) return `${+(value / 1e3).toFixed(0)}k`;
  return String(Math.round(value));
}

export const count = (value: number | null | undefined) => (value == null ? "n/a" : value.toLocaleString("en-IN"));
export const percent = (value: number | null | undefined, digits = 0) => (value == null ? "n/a" : `${(value * 100).toFixed(digits)}%`);

/** The API sends naive UTC timestamps. */
const parse = (value: string) => new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);

export const date = (value?: string | null) =>
  value ? new Date(value).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "n/a";
const CLOCK = { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" } as const;
/** System timestamps (runs, reviews): stored in UTC, shown in the reader's time. */
export const dateTime = (value?: string | null) => (value ? parse(value).toLocaleString("en-IN", CLOCK) : "n/a");
/** Business timestamps (invoice approvals): no timezone, so the recorded clock time is shown as it is. */
export const wallClock = (value?: string | null) => (value ? new Date(value).toLocaleString("en-IN", CLOCK) : "n/a");

export const RULE_LABELS: Record<string, string> = {
  duplicate_invoice: "Duplicate invoice", invoice_splitting: "Invoice splitting", sod_violation: "Segregation of duties",
  bank_change: "Bank account change", new_vendor_large: "New vendor, large payment", burst: "Invoice burst",
  off_hours_approval: "Off-hours approval", rushed_approval: "Rushed approval", round_amount: "Round amount",
  near_limit: "Near approval limit",
};

export const humanise = (text: string) => text.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()).replace(/^Sod\b/, "SoD").replace(/^Po\b/, "PO");

export const plural = (n: number, word: string) => `${n.toLocaleString("en-IN")} ${word}${n === 1 ? "" : "s"}`;
