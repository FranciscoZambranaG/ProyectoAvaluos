import type { ReactNode } from "react";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  InformationCircleIcon,
  ExclamationTriangleIcon,
} from "@heroicons/react/24/solid";

const TYPES = {
  success: { container: "border-state-success/30 bg-state-success/10 text-slate-800", icon: CheckCircleIcon, iconColor: "text-state-success" },
  error: { container: "border-state-danger/30 bg-state-danger/10 text-state-danger", icon: ExclamationCircleIcon, iconColor: "text-state-danger" },
  warning: { container: "border-state-amber/40 bg-state-amber/10 text-slate-800", icon: ExclamationTriangleIcon, iconColor: "text-state-amber" },
  info: { container: "border-accent-400/30 bg-accent-300/20 text-slate-800", icon: InformationCircleIcon, iconColor: "text-accent-600" },
} as const;

type Props = {
  type?: keyof typeof TYPES;
  title?: string;
  message?: ReactNode;
  children?: ReactNode;
  className?: string;
};

export function Alert({ type = "info", title, message, children, className = "" }: Props) {
  const current = TYPES[type] || TYPES.info;
  const Icon = current.icon;

  return (
    <div role="alert" className={`flex items-start gap-2.5 rounded-2xl border p-4 text-xs ${current.container} ${className}`}>
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${current.iconColor}`} aria-hidden="true" />
      <div className="flex-1">
        {title && <p className="font-semibold">{title}</p>}
        {message && <p className={title ? "mt-0.5" : ""}>{message}</p>}
        {children}
      </div>
    </div>
  );
}

export default Alert;
