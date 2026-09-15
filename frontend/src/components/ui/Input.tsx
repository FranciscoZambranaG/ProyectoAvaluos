import type { ComponentType, InputHTMLAttributes, ReactNode, SVGProps } from "react";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  badgeText?: string;
  error?: string;
  icon?: ComponentType<SVGProps<SVGSVGElement>>;
  rightElement?: ReactNode;
  containerClassName?: string;
};

export function Input({
  id,
  name,
  label,
  badgeText,
  error,
  icon: Icon,
  rightElement,
  className = "",
  containerClassName = "",
  type = "text",
  ...props
}: Props) {
  return (
    <div className={`flex flex-col ${containerClassName}`}>
      {(label || badgeText) && (
        <div className="mb-1.5 flex items-center justify-between">
          {label && (
            <label htmlFor={id || name} className="block text-sm font-medium text-slate-700">
              {label}
            </label>
          )}
          {badgeText && <span className="text-[11px] font-medium text-accent-600">{badgeText}</span>}
        </div>
      )}

      <div className="relative">
        {Icon && <Icon className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />}

        <input
          id={id || name}
          name={name}
          type={type}
          aria-invalid={Boolean(error)}
          aria-describedby={error && id ? `${id}-error` : undefined}
          className={`w-full rounded-xl border bg-white/60 py-3 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition-colors duration-200 focus:border-accent-500/60 focus:bg-white focus-visible:ring-2 focus-visible:ring-accent-400/40 ${
            Icon ? "pl-10" : "pl-4"
          } ${rightElement ? "pr-10" : "pr-4"} ${error ? "border-state-danger/50" : "border-slate-200"} ${className}`}
          {...props}
        />

        {rightElement && <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center">{rightElement}</div>}
      </div>

      {error && (
        <p id={id ? `${id}-error` : undefined} className="mt-1.5 text-xs text-state-danger">
          {error}
        </p>
      )}
    </div>
  );
}

export default Input;
