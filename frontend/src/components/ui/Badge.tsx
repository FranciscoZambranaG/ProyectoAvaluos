import type { ReactNode } from "react";

const VARIANTS = {
  success: "border-state-success/30 bg-state-success/10 text-slate-700",
  accent: "border-accent-400/30 bg-accent-300/20 text-accent-600",
  neutral: "border-slate-200 bg-slate-100 text-slate-600",
  warning: "border-state-amber/40 bg-state-amber/10 text-slate-700",
  danger: "border-state-danger/30 bg-state-danger/10 text-state-danger",
} as const;

type Props = {
  children: ReactNode;
  variant?: keyof typeof VARIANTS;
  dot?: boolean;
  dotPulse?: boolean;
  className?: string;
};

export function Badge({ children, variant = "neutral", dot = false, dotPulse = false, className = "" }: Props) {
  const variantClass = VARIANTS[variant] || VARIANTS.neutral;
  const dotColor =
    variant === "success"
      ? "bg-state-success"
      : variant === "danger"
        ? "bg-state-danger"
        : variant === "warning"
          ? "bg-state-amber"
          : "bg-accent-500";

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-0.5 text-xs font-semibold ${variantClass} ${className}`}>
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${dotColor} ${dotPulse ? "animate-pulse" : ""}`} />}
      {children}
    </span>
  );
}

export default Badge;
