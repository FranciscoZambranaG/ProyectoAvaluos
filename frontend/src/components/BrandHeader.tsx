import { Link } from "react-router-dom";
import { useBranding } from "../lib/branding";

type Props = {
  variant?: "on-cyan" | "on-light";
  subtitle?: string;
};

export function BrandHeader({ variant = "on-cyan", subtitle }: Props) {
  const b = useBranding();
  const src = variant === "on-light" ? "/brand/cocha-cyan.png" : "/brand/cocha-outline.png";
  const extra = subtitle ?? b.unit;

  return (
    <Link to="/" className={`brand brand--${variant}`}>
      <img className="brand-logo" src={src} alt="Cocha" />
      <span>
        <strong>{b.portal}</strong>
        {extra ? <small>{extra}</small> : null}
      </span>
    </Link>
  );
}
