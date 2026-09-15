import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import { api } from "../lib/api";

const DefaultIcon = L.icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});
L.Marker.prototype.options.icon = DefaultIcon;

export type ParcelIdentify = {
  cadastral_code: string;
  subdistrict: string;
  block_code: string;
  plot_code: string;
  use_code: string;
  building_code: string;
  floor_code: string;
  unit_code: string;
  property_number?: string | null;
  district?: string | null;
  commune?: string | null;
  subdistrict_name?: string | null;
  area_m2?: number | null;
  zone_code?: string | null;
  zone_item_id?: string | null;
  zone_label?: string | null;
  slope_raw?: string | null;
  topography_code?: string | null;
  topography_item_id?: string | null;
  topography_label?: string | null;
  road_material_code?: string | null;
  road_material_item_id?: string | null;
  road_material_label?: string | null;
  shape_code?: string | null;
  shape_item_id?: string | null;
  shape_label?: string | null;
  address?: string | null;
  rings?: number[][][];
  centroid_lat?: number | null;
  centroid_lng?: number | null;
};

export type PropertyMapPickerHandle = {
  showParcel: (parcel: ParcelIdentify) => void;
};

type Props = {
  latitude: number;
  longitude: number;
  onChange: (lat: number, lng: number) => void;
  onParcel?: (parcel: ParcelIdentify) => void;
  height?: number;
  interactive?: boolean;
  /** Si es false, el mapa sigue montado pero no recibe clics (evita saltos al volver al paso). */
  active?: boolean;
};

const COCHABAMBA: [number, number] = [-17.3935, -66.157];
const WMS_URL = "https://gs.catastrocbba.com/arcgis/services/catastro/predios_cba/MapServer/WMSServer";
const LIMITS_WMS_URL = "https://gs.catastrocbba.com/arcgis/services/planificacion/limites_cba/MapServer/WMSServer";
const OSM_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const SATELLITE_TILE_URL =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const SATELLITE_ATTRIBUTION = "Teselas © Esri — Source: Esri, Maxar, Earthstar Geographics";
const CERCADO_BOUNDS = { south: -17.53119, west: -66.2807, north: -17.25731, east: -66.06952 };
const LIMITS_COLOR = "#FFD400";
const LIMITS_SEPIA_HUE = 45;

type LayerBounds = { south: number; west: number; north: number; east: number };

type GisLayerCfg = {
  code?: string;
  name?: string;
  visible?: boolean;
  layer_type?: string;
  tile_url?: string;
  wms_url?: string;
  wms_layer?: string;
  min_zoom?: number;
  max_zoom?: number;
  attribution?: string;
  z_index?: number;
  constrain_map?: boolean;
  bounds?: Partial<LayerBounds>;
  color?: string;
  print_only?: boolean;
};

function hexToRgb(hex: string): [number, number, number] {
  const raw = hex.replace("#", "").trim();
  const full = raw.length === 3 ? raw.split("").map((c) => c + c).join("") : raw;
  const n = Number.parseInt(full, 16);
  if (!Number.isFinite(n)) return [255, 212, 0];
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function rgbToHue(r: number, g: number, b: number): number {
  const R = r / 255;
  const G = g / 255;
  const B = b / 255;
  const max = Math.max(R, G, B);
  const min = Math.min(R, G, B);
  const d = max - min;
  if (d === 0) return 0;
  let h = 0;
  if (max === R) h = ((G - B) / d) % 6;
  else if (max === G) h = (B - R) / d + 2;
  else h = (R - G) / d + 4;
  h *= 60;
  return h < 0 ? h + 360 : h;
}

function limitsColorFilter(hex: string): string {
  const [r, g, b] = hexToRgb(hex);
  const rotate = rgbToHue(r, g, b) - LIMITS_SEPIA_HUE;
  return `sepia(1) saturate(18) hue-rotate(${rotate}deg) brightness(1.5) contrast(1.4) drop-shadow(0 0 1px #111) drop-shadow(0 0 3px ${hex})`;
}

function applyLimitsColor(pane: HTMLElement | undefined, hex: string) {
  if (!pane) return;
  pane.style.filter = limitsColorFilter(hex || LIMITS_COLOR);
}

function toLatLngBounds(b: Partial<LayerBounds> | undefined, pad = 0.004): L.LatLngBounds {
  const south = Number(b?.south ?? CERCADO_BOUNDS.south) - pad;
  const west = Number(b?.west ?? CERCADO_BOUNDS.west) - pad;
  const north = Number(b?.north ?? CERCADO_BOUNDS.north) + pad;
  const east = Number(b?.east ?? CERCADO_BOUNDS.east) + pad;
  return L.latLngBounds(L.latLng(south, west), L.latLng(north, east));
}

function defaultZIndex(code: string, layer: GisLayerCfg): number {
  if (typeof layer.z_index === "number") return layer.z_index;
  if (layer.layer_type === "xyz" || code === "satellite") return 0;
  if (code === "zone_homogeneous") return 10;
  if (code === "topography") return 15;
  if (code === "road_material") return 20;
  if (code === "parcels") return 30;
  if (code === "municipal_limits") return 40;
  return 12;
}

function isXyzLayer(code: string, layer: GisLayerCfg): boolean {
  return layer.layer_type === "xyz" || code === "satellite" || Boolean(layer.tile_url && !layer.wms_url);
}

function pointInRing(lng: number, lat: number, ring: number[][]): boolean {
  const pts = ring.filter((pt) => pt.length >= 2);
  const closed =
    pts.length >= 2 && pts[0][0] === pts[pts.length - 1][0] && pts[0][1] === pts[pts.length - 1][1]
      ? pts.slice(0, -1)
      : pts;
  const n = closed.length;
  if (n < 3) return false;
  let inside = false;
  let j = n - 1;
  for (let i = 0; i < n; i += 1) {
    const xi = closed[i][0];
    const yi = closed[i][1];
    const xj = closed[j][0];
    const yj = closed[j][1];
    if ((yi > lat) !== (yj > lat)) {
      const denom = yj - yi;
      if (Math.abs(denom) > 1e-18) {
        const xCross = ((xj - xi) * (lat - yi)) / denom + xi;
        if (lng < xCross) inside = !inside;
      }
    }
    j = i;
  }
  return inside;
}

export function pointInParcelRings(lat: number, lng: number, rings?: number[][][] | null): boolean {
  if (!rings?.length) return false;
  if (!pointInRing(lng, lat, rings[0])) return false;
  for (let i = 1; i < rings.length; i += 1) {
    if (pointInRing(lng, lat, rings[i])) return false;
  }
  return true;
}

function applyParcelGeometry(
  map: L.Map,
  marker: L.Marker,
  parcelLayerRef: { current: L.Polygon | null },
  parcel: ParcelIdentify,
  onChange: (lat: number, lng: number) => void,
  snapToCentroid = false,
) {
  const cLat = parcel.centroid_lat;
  const cLng = parcel.centroid_lng;
  const current = marker.getLatLng();
  const inside = pointInParcelRings(current.lat, current.lng, parcel.rings);
  if ((snapToCentroid || !inside) && cLat != null && cLng != null) {
    const snapped = L.latLng(cLat, cLng);
    marker.setLatLng(snapped);
    onChange(Number(cLat.toFixed(8)), Number(cLng.toFixed(8)));
  }
  if (parcelLayerRef.current) {
    parcelLayerRef.current.remove();
    parcelLayerRef.current = null;
  }
  const ring = parcel.rings?.[0];
  if (ring && ring.length >= 3) {
    const latlngs = ring.map((pt) => L.latLng(pt[1], pt[0]));
    parcelLayerRef.current = L.polygon(latlngs, {
      color: "#c81e1e",
      weight: 2,
      fillColor: "#00A7D6",
      fillOpacity: 0.18,
    }).addTo(map);
    map.fitBounds(parcelLayerRef.current.getBounds(), { maxZoom: 19, padding: [24, 24] });
  } else if (cLat != null && cLng != null) {
    map.setView([cLat, cLng], Math.max(map.getZoom(), 18));
  }
  marker.bindPopup(`Predio: <b>${parcel.cadastral_code}</b>`).openPopup();
}

export const PropertyMapPicker = forwardRef<PropertyMapPickerHandle, Props>(function PropertyMapPicker(
  { latitude, longitude, onChange, onParcel, height = 380, interactive = true, active = true },
  ref,
) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.Marker | null>(null);
  const parcelLayerRef = useRef<L.Polygon | null>(null);
  const onChangeRef = useRef(onChange);
  const onParcelRef = useRef(onParcel);
  const interactiveRef = useRef(interactive);
  const activeRef = useRef(active);
  const ignoreClicksUntilRef = useRef(0);
  onChangeRef.current = onChange;
  onParcelRef.current = onParcel;
  interactiveRef.current = interactive;
  activeRef.current = active;

  const [status, setStatus] = useState(
    interactive
      ? "Mapa limitado al Cercado. Satélite + predios WMS. Zoom ≥ 17, clic = pin + código, o «Centrar en mapa»."
      : "Vista solo lectura del mapa.",
  );
  const [busy, setBusy] = useState(false);

  useImperativeHandle(ref, () => ({
    showParcel(parcel) {
      const map = mapRef.current;
      const marker = markerRef.current;
      if (!map || !marker) return;
      applyParcelGeometry(map, marker, parcelLayerRef, parcel, onChangeRef.current, true);
      const label = [parcel.cadastral_code, parcel.commune, parcel.subdistrict_name].filter(Boolean).join(" · ");
      setStatus(`Predio centrado: ${label}`);
      setTimeout(() => map.invalidateSize(), 80);
    },
  }));

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const lat = Number.isFinite(latitude) ? latitude : COCHABAMBA[0];
    const lng = Number.isFinite(longitude) ? longitude : COCHABAMBA[1];

    const initialBounds = toLatLngBounds(CERCADO_BOUNDS);
    const start = initialBounds.contains([lat, lng]) ? ([lat, lng] as [number, number]) : COCHABAMBA;

    const map = L.map(containerRef.current, {
      center: start,
      zoom: 18,
      minZoom: 12,
      maxZoom: 20,
      maxBounds: initialBounds,
      maxBoundsViscosity: 1,
      scrollWheelZoom: true,
    });

    const satelliteLayer = L.tileLayer(SATELLITE_TILE_URL, {
      attribution: SATELLITE_ATTRIBUTION,
      maxZoom: 19,
      zIndex: 0,
    }).addTo(map);

    L.tileLayer
      .wms(WMS_URL, {
        layers: "0",
        format: "image/png",
        transparent: true,
        version: "1.1.1",
        attribution: 'Predios · <a href="https://gs.catastrocbba.com">GAMC Catastro</a>',
        maxZoom: 20,
        minZoom: 16,
        zIndex: 30,
      })
      .addTo(map);

    map.createPane("municipalLimits");
    const limitsPane = map.getPane("municipalLimits");
    if (limitsPane) {
      limitsPane.style.zIndex = "450";
      limitsPane.style.pointerEvents = "none";
      applyLimitsColor(limitsPane, LIMITS_COLOR);
    }

    const limitsLayer = L.tileLayer.wms(LIMITS_WMS_URL, {
      layers: "0",
      format: "image/png",
      transparent: true,
      version: "1.1.1",
      attribution: "Límites Cercado · GAMC",
      maxZoom: 20,
      minZoom: 12,
      zIndex: 40,
      pane: "municipalLimits",
    }).addTo(map);

    async function addConfiguredLayers() {
      let layers: Record<string, GisLayerCfg> = {};
      try {
        const params = await api<{ key: string; value_json: unknown }[]>("/api/v1/public/parameters");
        const gis = params.find((p) => p.key === "gis_layers")?.value_json;
        if (gis && typeof gis === "object") {
          layers = gis as Record<string, GisLayerCfg>;
        }
      } catch {
        return;
      }

      const sat = layers.satellite;
      if (sat && sat.visible === false) {
        satelliteLayer.remove();
        L.tileLayer(OSM_TILE_URL, {
          attribution: "&copy; OpenStreetMap",
          maxZoom: 20,
          zIndex: 0,
        }).addTo(map);
      } else if (sat?.tile_url && sat.tile_url !== SATELLITE_TILE_URL) {
        satelliteLayer.setUrl(sat.tile_url);
      }

      const limits = layers.municipal_limits;
      if (limits && limits.visible === false) {
        limitsLayer.remove();
      } else if (limits?.wms_url && limits.wms_url !== LIMITS_WMS_URL) {
        limitsLayer.setUrl(limits.wms_url);
      }
      applyLimitsColor(limitsPane, String(limits?.color || LIMITS_COLOR));
      if (limits?.constrain_map === false) {
        map.setMaxBounds(L.latLngBounds([-90, -180], [90, 180]));
      } else {
        map.setMaxBounds(toLatLngBounds(limits?.bounds || CERCADO_BOUNDS));
      }

      const ordered = Object.entries(layers).sort(
        ([aCode, a], [bCode, b]) => defaultZIndex(aCode, a || {}) - defaultZIndex(bCode, b || {}),
      );
      for (const [code, layer] of ordered) {
        if (!layer?.visible || layer.print_only || code === "satellite" || code === "parcels" || code === "municipal_limits") continue;
        if (isXyzLayer(code, layer) && layer.tile_url) continue;
        if (!layer.wms_url) continue;
        L.tileLayer
          .wms(layer.wms_url, {
            layers: String(layer.wms_layer || "0"),
            format: "image/png",
            transparent: true,
            version: "1.1.1",
            attribution: layer.name || "GAMC Catastro",
            maxZoom: 20,
            minZoom: Number(layer.min_zoom || 16),
            zIndex: defaultZIndex(code, layer),
          })
          .addTo(map);
      }
    }
    void addConfiguredLayers();

    const marker = L.marker([lat, lng], { draggable: interactive }).addTo(map);
    marker.bindPopup("Pin del predio").openPopup();

    async function identifyAt(latlng: L.LatLng) {
      if (!interactiveRef.current || !activeRef.current) return;
      if (Date.now() < ignoreClicksUntilRef.current) return;
      marker.setLatLng(latlng);
      onChangeRef.current(Number(latlng.lat.toFixed(8)), Number(latlng.lng.toFixed(8)));
      if (!onParcelRef.current) return;
      setBusy(true);
      setStatus("Identificando predio…");
      try {
        const data = await api<{ found: boolean; parcel: ParcelIdentify | null }>(
          `/api/v1/gis/parcel-identify?lat=${latlng.lat}&lng=${latlng.lng}`,
          {},
          true,
        );
        if (data.found && data.parcel) {
          const parcel = data.parcel;
          applyParcelGeometry(map, marker, parcelLayerRef, parcel, onChangeRef.current, false);
          onParcelRef.current(parcel);
          const label = [parcel.cadastral_code, parcel.commune, parcel.subdistrict_name].filter(Boolean).join(" · ");
          setStatus(`Predio identificado: ${label}`);
        } else {
          setStatus("No hay predio WMS en ese punto. Ajuste el pin o pulse «Centrar en mapa».");
        }
      } catch (err) {
        setStatus(err instanceof Error ? err.message : "Error al identificar predio");
      } finally {
        setBusy(false);
      }
    }

    if (interactive) {
      marker.on("dragend", () => {
        void identifyAt(marker.getLatLng());
      });
      map.on("click", (e: L.LeafletMouseEvent) => {
        if (!activeRef.current || Date.now() < ignoreClicksUntilRef.current) return;
        void identifyAt(e.latlng);
      });
    }

    mapRef.current = map;
    markerRef.current = marker;
    ignoreClicksUntilRef.current = Date.now() + 500;
    setTimeout(() => map.invalidateSize(), 80);

    return () => {
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
      parcelLayerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const marker = markerRef.current;
    if (!map || !marker || !Number.isFinite(latitude) || !Number.isFinite(longitude)) return;
    const current = marker.getLatLng();
    if (Math.abs(current.lat - latitude) < 1e-8 && Math.abs(current.lng - longitude) < 1e-8) return;
    marker.setLatLng([latitude, longitude]);
    map.panTo([latitude, longitude]);
  }, [latitude, longitude]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (active) {
      ignoreClicksUntilRef.current = Date.now() + 450;
      const t = window.setTimeout(() => map.invalidateSize(), 80);
      return () => window.clearTimeout(t);
    }
    return undefined;
  }, [active]);

  return (
    <div className={`map-picker${active ? "" : " map-picker--idle"}`}>
      <div ref={containerRef} className="map-picker__canvas" style={{ height }} />
      <p className={`map-picker__hint ${busy ? "" : "muted"}`}>
        {busy ? "Consultando servicio WMS de predios…" : status}
      </p>
    </div>
  );
});
