import { useEffect, useRef, useState, type InputHTMLAttributes } from "react";
import { formatDecimal, isNumpadDecimal, parseDecimal } from "../lib/decimal";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type"> & {
  value: number | null | undefined;
  onChange: (value: number | null) => void;
};

export function DecimalInput({ value, onChange, onKeyDown, onFocus, onBlur, ...rest }: Props) {
  const [text, setText] = useState(formatDecimal(value));
  const focused = useRef(false);

  useEffect(() => {
    if (focused.current) return;
    setText(formatDecimal(value));
  }, [value]);

  function commit(next: string) {
    setText(next);
    onChange(parseDecimal(next));
  }

  return (
    <input
      {...rest}
      type="text"
      inputMode="decimal"
      autoComplete="off"
      value={text}
      onFocus={(e) => {
        focused.current = true;
        onFocus?.(e);
      }}
      onBlur={(e) => {
        focused.current = false;
        setText(formatDecimal(value));
        onBlur?.(e);
      }}
      onChange={(e) => commit(e.target.value)}
      onKeyDown={(e) => {
        if (isNumpadDecimal(e)) {
          e.preventDefault();
          const el = e.currentTarget;
          const start = el.selectionStart ?? text.length;
          const end = el.selectionEnd ?? start;
          commit(text.slice(0, start) + "," + text.slice(end));
          requestAnimationFrame(() => {
            const pos = start + 1;
            el.setSelectionRange(pos, pos);
          });
        }
        onKeyDown?.(e);
      }}
    />
  );
}
