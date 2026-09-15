import { useEffect, useMemo, useState } from "react";
import { DecimalInput } from "./DecimalInput";
import { mediaUrl } from "../lib/api";

export type CharOption = {
  id: string;
  code: string;
  label: string;
  description?: string | null;
  image_url?: string | null;
};

export type CharGroup = {
  id: string;
  code: string;
  name: string;
  max_percent: number;
  applies_to?: string;
  options: CharOption[];
};

export type CharPick = { option_id: string; percentage: number };

type Props = {
  groups: CharGroup[];
  value: Record<string, CharPick[]>;
  onChange: (next: Record<string, CharPick[]>) => void;
  apiBase: string;
  readOnly?: boolean;
};

export function CharacteristicsPanel({ groups, value, onChange, apiBase: _apiBase, readOnly = false }: Props) {
  const [groupId, setGroupId] = useState(groups[0]?.id || "");
  const [focusOptionId, setFocusOptionId] = useState<string | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);

  useEffect(() => {
    if (!groupId && groups[0]) setGroupId(groups[0].id);
    if (groupId && groups.length && !groups.some((g) => g.id === groupId) && groups[0]) {
      setGroupId(groups[0].id);
    }
  }, [groups, groupId]);

  const group = groups.find((g) => g.id === groupId) || groups[0];
  const picks = group ? value[group.id] || [] : [];

  useEffect(() => {
    if (!group) return;
    if (focusOptionId && picks.some((p) => p.option_id === focusOptionId)) return;
    if (picks[0]) setFocusOptionId(picks[0].option_id);
    else setFocusOptionId(null);
  }, [group?.id, picks, focusOptionId]);

  const selectedOption = useMemo(() => {
    if (!group || !focusOptionId) return null;
    return group.options.find((o) => o.id === focusOptionId) || null;
  }, [group, focusOptionId]);

  const groupSum = picks.reduce((acc, p) => acc + (Number(p.percentage) || 0), 0);
  const maxPct = Number(group?.max_percent ?? 100);

  function setGroupPicks(next: CharPick[]) {
    if (!group) return;
    onChange({ ...value, [group.id]: next });
  }

  function pickOf(optionId: string) {
    return picks.find((p) => p.option_id === optionId);
  }

  function toggleSubtype(opt: CharOption) {
    if (readOnly || !group) return;
    setHelpOpen(false);
    const existing = pickOf(opt.id);
    if (existing) {
      setFocusOptionId(opt.id);
      return;
    }
    const remaining = Math.max(0, maxPct - groupSum);
    const pct = remaining > 0 ? remaining : 0;
    setGroupPicks([...picks, { option_id: opt.id, percentage: pct || (groupSum === 0 ? 100 : 0) }]);
    setFocusOptionId(opt.id);
  }

  function removeSubtype(optionId: string) {
    if (readOnly || !group) return;
    const next = picks.filter((p) => p.option_id !== optionId);
    setGroupPicks(next);
    if (focusOptionId === optionId) setFocusOptionId(next[0]?.option_id || null);
  }

  function updatePercent(optionId: string, percentage: number) {
    if (readOnly || !group) return;
    const n = Number.isFinite(percentage) ? Math.max(0, Math.min(100, percentage)) : 0;
    const others = picks.filter((p) => p.option_id !== optionId).reduce((a, p) => a + Number(p.percentage || 0), 0);
    const capped = Math.min(n, Math.max(0, maxPct - others));
    const exists = picks.some((p) => p.option_id === optionId);
    if (!exists) {
      if (capped <= 0) return;
      setGroupPicks([...picks, { option_id: optionId, percentage: capped }]);
      return;
    }
    setGroupPicks(picks.map((p) => (p.option_id === optionId ? { ...p, percentage: capped } : p)));
  }

  if (!group) {
    return <div className="hint">No hay catálogo de características cargado.</div>;
  }

  return (
    <div className="chars-panel">
      <div className="chars-grid">
        <div className="chars-lists">
          <div className="chars-list">
            <div className="chars-list__title">Tipo</div>
            <ul>
              {groups.map((g) => {
                const gPicks = value[g.id] || [];
                const on = g.id === group.id;
                const hasValue = gPicks.some((p) => Number(p.percentage) > 0);
                const count = gPicks.filter((p) => Number(p.percentage) > 0).length;
                return (
                  <li key={g.id}>
                    <button
                      type="button"
                      className={`${on ? "on" : ""} ${hasValue ? "picked" : ""}`}
                      onClick={() => {
                        setGroupId(g.id);
                        setHelpOpen(false);
                      }}
                    >
                      <span>
                        {g.name}
                        {count > 1 ? ` (${count})` : ""}
                      </span>
                      {hasValue && <em>✓</em>}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="chars-list">
            <div className="chars-list__title">Subtipos (puede elegir varios)</div>
            <ul>
              {group.options.map((o) => {
                const assigned = pickOf(o.id);
                const isFocused = focusOptionId === o.id;
                const isAssigned = Boolean(assigned && Number(assigned.percentage) > 0);
                return (
                  <li key={o.id}>
                    <button
                      type="button"
                      className={`${isFocused ? "on" : ""} ${assigned ? "picked" : ""}`}
                      onClick={() => toggleSubtype(o)}
                    >
                      <span>
                        {o.label}
                        {assigned ? ` · ${Number(assigned.percentage).toLocaleString("es-BO")}%` : ""}
                      </span>
                      {isAssigned && <em>✓</em>}
                    </button>
                  </li>
                );
              })}
            </ul>
            <p className="muted chars-hint">
              Pulse un subtipo para agregarlo. Puede asignar varios con porcentajes independientes (máx. {maxPct}% en total).
            </p>
          </div>
        </div>

        <div className="chars-preview">
          <div className="chars-preview__frame">
            {selectedOption?.image_url ? (
              <img src={mediaUrl(selectedOption.image_url)} alt={selectedOption.label} />
            ) : (
              <div className="chars-preview__empty">Seleccione un subtipo para ver la imagen</div>
            )}
            {selectedOption?.description && (
              <div className="chars-help">
                <button
                  type="button"
                  className="chars-help__btn"
                  aria-label="Ver descripción"
                  onClick={() => setHelpOpen((v) => !v)}
                  onMouseEnter={() => setHelpOpen(true)}
                  onMouseLeave={() => setHelpOpen(false)}
                >
                  ?
                </button>
                {helpOpen && (
                  <div className="chars-help__bubble" role="tooltip">
                    {selectedOption.description}
                  </div>
                )}
              </div>
            )}
          </div>
          {selectedOption && <div className="chars-preview__caption">{selectedOption.label}</div>}
        </div>
      </div>

      <div className="chars-value">
        <div className="chars-list__title">
          Valores asignados · total {groupSum.toLocaleString("es-BO")}% / {maxPct}%
        </div>
        {picks.length === 0 ? (
          <p className="muted chars-hint" style={{ paddingLeft: 0 }}>
            Aún no hay subtipos asignados en este tipo.
          </p>
        ) : (
          <div className="chars-assigned">
            {picks.map((p) => {
              const opt = group.options.find((o) => o.id === p.option_id);
              if (!opt) return null;
              return (
                <div key={p.option_id} className={`chars-assigned__row${focusOptionId === p.option_id ? " on" : ""}`}>
                  <button type="button" className="chars-assigned__label" onClick={() => setFocusOptionId(p.option_id)}>
                    {opt.label}
                  </button>
                  <label className="chars-value__pct">
                    %
                    <DecimalInput
                      min={0}
                      max={100}
                      disabled={readOnly}
                      value={p.percentage}
                      onChange={(n) => updatePercent(p.option_id, n ?? 0)}
                      onFocus={() => setFocusOptionId(p.option_id)}
                    />
                  </label>
                  <button
                    type="button"
                    className="btn btn-out"
                    style={{ padding: ".3rem .55rem" }}
                    disabled={readOnly}
                    onClick={() => removeSubtype(p.option_id)}
                  >
                    Quitar
                  </button>
                </div>
              );
            })}
          </div>
        )}
        {groupSum > maxPct && (
          <div className="error" style={{ marginTop: ".5rem" }}>
            La suma de porcentajes de este tipo no puede superar {maxPct}%.
          </div>
        )}
      </div>
    </div>
  );
}
