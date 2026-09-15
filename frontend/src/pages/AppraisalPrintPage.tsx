import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { printAppraisalPdf } from "../lib/printPdf";

export function AppraisalPrintPage() {
  const { id } = useParams();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    let active = true;
    setLoading(true);
    setError("");
    printAppraisalPdf(id)
      .catch((e) => {
        if (!active) return;
        const msg = e instanceof Error ? e.message : "Error";
        setError(
          msg === "Failed to fetch" || msg.includes("NetworkError")
            ? "No se pudo conectar con el servidor. Verifique que el backend esté en marcha."
            : msg,
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id]);

  return (
    <div className="page" style={{ maxWidth: 520 }}>
      <div className="actions" style={{ marginBottom: ".75rem" }}>
        <div>
          <h2>Imprimir</h2>
          <p className="muted">Declaración jurada de datos técnicos.</p>
        </div>
        {id && (
          <Link className="btn btn-out" to={`/app/formularios/${id}`}>
            Volver
          </Link>
        )}
      </div>
      {error && <div className="error">{error}</div>}
      {loading && (
        <div className="print-loader" style={{ margin: "2rem auto" }}>
          <div className="print-loader__spin" aria-hidden />
          <strong>Generando documento…</strong>
          <p className="muted" style={{ margin: ".45rem 0 0" }}>
            Se abrirá el diálogo de impresión del navegador.
          </p>
        </div>
      )}
      {!loading && !error && (
        <div className="hint">
          Si el diálogo de impresión no apareció, pulse{" "}
          <button type="button" className="linkish" onClick={() => id && void printAppraisalPdf(id).catch((e) => setError(e instanceof Error ? e.message : "Error"))}>
            reintentar
          </button>
          .
        </div>
      )}
    </div>
  );
}
