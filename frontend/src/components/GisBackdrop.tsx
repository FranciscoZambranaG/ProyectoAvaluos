import watermarkCocha from "../assets/watermark/cocha-skyline-color.png";

const NOISE_SVG = `
<svg xmlns='http://www.w3.org/2000/svg' width='180' height='180'>
  <filter id='n'>
    <feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch' />
  </filter>
  <rect width='100%' height='100%' filter='url(#n)' />
</svg>`;
const NOISE_DATA_URI = `data:image/svg+xml;utf8,${encodeURIComponent(NOISE_SVG)}`;

/** Fondo institucional fijo: gradiente celeste GAMC + textura sutil + silueta de Cochabamba. */
export function GisBackdrop() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-gradient-to-br from-accent-300 via-accent-400 to-accent-500">
      <div
        className="absolute inset-0 opacity-[0.05] mix-blend-soft-light"
        style={{ backgroundImage: `url("${NOISE_DATA_URI}")`, backgroundSize: "180px 180px" }}
      />
      <div
        className="absolute inset-0 opacity-[0.05]"
        style={{
          backgroundImage:
            "linear-gradient(to right, white 1px, transparent 1px), linear-gradient(to bottom, white 1px, transparent 1px)",
          backgroundSize: "64px 64px",
        }}
      />
      <div
        className="absolute inset-0 bg-no-repeat bg-bottom opacity-[0.09]"
        style={{ backgroundImage: `url("${watermarkCocha}")`, backgroundSize: "min(100vw, 1800px) auto" }}
      />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_40%,rgba(10,13,18,0.14)_100%)]" />
    </div>
  );
}

export default GisBackdrop;
