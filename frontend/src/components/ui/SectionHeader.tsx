import type { ComponentType, ReactNode, SVGProps } from "react";

type Props = {
  icon?: ComponentType<SVGProps<SVGSVGElement>>;
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  className?: string;
};

export function SectionHeader({ icon: Icon, eyebrow, title, subtitle, actions, className = "" }: Props) {
  return (
    <div className={`mb-6 flex items-start justify-between gap-3 border-b border-slate-200/60 pb-4 ${className}`}>
      <div className="flex items-center gap-3">
        {Icon && (
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-50 text-accent-600 ring-1 ring-accent-200">
            <Icon className="h-5 w-5" />
          </span>
        )}
        <div>
          {eyebrow && <p className="text-xs font-semibold uppercase tracking-wider text-accent-600">{eyebrow}</p>}
          {title && <h2 className="text-lg font-bold text-slate-900">{title}</h2>}
          {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

export default SectionHeader;
