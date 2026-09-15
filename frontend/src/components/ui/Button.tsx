import type { ButtonHTMLAttributes, ComponentType, SVGProps } from "react";
import { Spinner } from "./Spinner";

const VARIANTS = {
  primary:
    "bg-brand-800 text-white shadow-md shadow-brand-800/20 hover:bg-brand-600 focus-visible:ring-brand-600/40",
  secondary:
    "bg-white/80 text-slate-800 border border-slate-200 shadow-xs hover:bg-white hover:border-slate-300 focus-visible:ring-slate-400/50",
  danger:
    "bg-white/80 text-state-danger border border-state-danger/30 shadow-xs hover:bg-state-danger/10 hover:border-state-danger/50 focus-visible:ring-state-danger/40",
  warning:
    "bg-state-amber text-white shadow-md shadow-state-amber/20 hover:bg-state-orange-deep focus-visible:ring-state-amber/40",
  ghost: "text-slate-600 hover:bg-slate-100/70 hover:text-slate-900 focus-visible:ring-slate-400/50",
} as const;

const SIZES = {
  sm: "px-3 py-1.5 text-xs rounded-lg",
  md: "px-4 py-2.5 text-xs sm:text-sm rounded-xl",
  lg: "px-5 py-3 text-sm rounded-xl",
} as const;

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof VARIANTS;
  size?: keyof typeof SIZES;
  loading?: boolean;
  icon?: ComponentType<SVGProps<SVGSVGElement>>;
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  disabled = false,
  className = "",
  icon: Icon,
  type = "button",
  ...props
}: Props) {
  const variantClass = VARIANTS[variant] || VARIANTS.primary;
  const sizeClass = SIZES[size] || SIZES.md;

  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 font-semibold transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer ${variantClass} ${sizeClass} ${className}`}
      {...props}
    >
      {loading ? <Spinner className="h-4 w-4" /> : Icon ? <Icon className="h-4 w-4 shrink-0" aria-hidden="true" /> : null}
      <span>{children}</span>
    </button>
  );
}

export default Button;
