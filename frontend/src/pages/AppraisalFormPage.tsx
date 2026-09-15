import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CharacteristicsPanel, type CharGroup, type CharPick } from "../components/CharacteristicsPanel";
import { DecimalInput } from "../components/DecimalInput";
import {
  PropertyMapPicker,
  pointInParcelRings,
  type ParcelIdentify,
  type PropertyMapPickerHandle,
} from "../components/PropertyMapPicker";
import { api, API_URL, mediaUrl } from "../lib/api";
import { printAppraisalPdf } from "../lib/printPdf";

type CatalogOption = { id: string; code: string; label: string; numeric_value?: number | null };
type Owner = {
  person_type: "natural" | "legal";
  first_name?: string | null;
  last_name_1?: string | null;
  last_name_2?: string | null;
  legal_name?: string | null;
  document_number?: string | null;
  ownership_percent?: number;
  phone?: string | null;
  email?: string | null;
  deed_number?: string | null;
  notary_name?: string | null;
  registry_matricula?: string | null;
  registry_asiento?: string | null;
  registry_ddr_date?: string | null;
};
type Detail = {
  approved_area?: number | null;
  front_length?: number | null;
  depth_length?: number | null;
  zone_item_id?: string | null;
  topography_item_id?: string | null;
  shape_item_id?: string | null;
  location_item_id?: string | null;
  road_material_item_id?: string | null;
  service_item_ids?: string[];
  equipment_item_ids?: string[];
  observations?: string | null;
  building_name?: string | null;
  block_label?: string | null;
  floor_label?: string | null;
  apartment_label?: string | null;
};
type Block = {
  id: string;
  unit_kind: "block" | "improvement";
  unit_number: string;
  area: number;
  floors_count: number;
  construction_year: number;
  modification_year?: number | null;
  observations?: string | null;
  total_score?: number | null;
  unit_value?: number | null;
  use_coeff_item_id?: string | null;
  depreciation_item_id?: string | null;
  improvement_type_item_id?: string | null;
  characteristics?: {
    group_id: string;
    group_code: string;
    group_name: string;
    option_id: string;
    option_label: string;
    percentage: number;
    score: number;
    base_score: number;
  }[];
};
type Photo = {
  id: string;
  media_type_code: string;
  media_type_name: string;
  original_name?: string | null;
  url: string;
  width_px?: number | null;
  height_px?: number | null;
};
type MediaType = { id: string; code: string; name: string; category: string };
type Appraisal = {
  id: string;
  form_number?: string | null;
  status_code: string;
  status_name: string;
  address: string;
  door_number?: string | null;
  building_name?: string | null;
  block_label?: string | null;
  floor_label?: string | null;
  apartment_label?: string | null;
  cadastral_code?: string | null;
  subdistrict?: string | null;
  block_code?: string | null;
  plot_code?: string | null;
  use_code?: string | null;
  building_code?: string | null;
  floor_code?: string | null;
  unit_code?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  owner?: Owner | null;
  detail?: Detail | null;
  blocks?: Block[];
  photos?: Photo[];
  can_edit?: boolean;
  is_own?: boolean;
  can_enable_correction?: boolean;
  can_migrate?: boolean;
  is_remigration?: boolean;
};

type Valuation = {
  land_value: number;
  blocks_value: number;
  improvements_value: number;
  total_value: number;
  zone_m2: number;
  vsz: number;
  vsvia: number;
  approved_area: number;
  indices: {
    ipiu: number;
    ipes: number;
    iprt: number;
    ipv: number;
  };
  formula?: { land_value?: string | null };
};

function money(n: number | null | undefined) {
  return new Intl.NumberFormat("es-BO", { style: "currency", currency: "BOB", maximumFractionDigits: 2 }).format(n || 0);
}

const STEPS = [
  { key: "owner", label: "Propietario" },
  { key: "code", label: "Código catastral" },
  { key: "detail", label: "Detalle predio" },
  { key: "blocks", label: "Bloques" },
  { key: "chars", label: "Características" },
  { key: "photos", label: "Fotografías" },
] as const;

type StepKey = (typeof STEPS)[number]["key"];

const CBBA = { lat: -17.3935, lng: -66.157 };

function composeCadastralCode(parts: {
  subdistrict: string;
  block_code: string;
  plot_code: string;
  use_code: string;
  building_code: string;
  floor_code: string;
  unit_code: string;
}) {
  const alnum = (value: string) => (value || "").replace(/[^0-9A-Za-z]/g, "");
  const sub = alnum(parts.subdistrict).padStart(2, "0").slice(-2);
  const block = alnum(parts.block_code).padStart(3, "0").slice(0, 11);
  const plot = alnum(parts.plot_code).padStart(3, "0").slice(0, 11);
  const use = alnum(parts.use_code || "0").padStart(1, "0").slice(0, 2);
  const building = alnum(parts.building_code || "0").padStart(1, "0").slice(0, 2);
  const floor = alnum(parts.floor_code || "0").padStart(1, "0").slice(0, 2);
  const unit = alnum(parts.unit_code || "0").padStart(1, "0").slice(0, 2);
  return `${sub}${block}${plot}${use}${building}${floor}${unit}`.padEnd(17, "0").slice(0, 17);
}

export function AppraisalFormPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = !id || id === "nuevo";
  const [step, setStep] = useState<StepKey>("owner");
  const [appraisal, setAppraisal] = useState<Appraisal | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [catalogs, setCatalogs] = useState<Record<string, CatalogOption[]>>({});

  const [address, setAddress] = useState("");
  const [door, setDoor] = useState("");
  const [owner, setOwner] = useState<Owner>({
    person_type: "natural",
    first_name: "",
    last_name_1: "",
    last_name_2: "",
    document_number: "",
    ownership_percent: 100,
    phone: "",
    email: "",
  });
  const [detail, setDetail] = useState<Detail>({
    approved_area: 0,
    front_length: 0,
    depth_length: 0,
    service_item_ids: [],
    equipment_item_ids: [],
    building_name: "",
    block_label: "",
    floor_label: "",
    apartment_label: "",
  });
  const [code, setCode] = useState({
    subdistrict: "",
    block_code: "",
    plot_code: "",
    use_code: "0",
    building_code: "0",
    floor_code: "0",
    unit_code: "0",
    door_number: "",
    building_name: "",
  });
  const [coords, setCoords] = useState({ latitude: CBBA.lat, longitude: CBBA.lng });
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [charGroups, setCharGroups] = useState<CharGroup[]>([]);
  const [charByBlock, setCharByBlock] = useState<Record<string, Record<string, CharPick[]>>>({});
  const [mediaTypes, setMediaTypes] = useState<MediaType[]>([]);
  const [activeBlockId, setActiveBlockId] = useState<string>("");
  const [photoType, setPhotoType] = useState("photo_front");
  const [photoDragOver, setPhotoDragOver] = useState(false);
  const [parcelInfo, setParcelInfo] = useState("");
  const [locating, setLocating] = useState(false);
  const [locationConfirmed, setLocationConfirmed] = useState(false);
  const mapPickerRef = useRef<PropertyMapPickerHandle | null>(null);
  const [blockForm, setBlockForm] = useState({
    unit_kind: "block" as "block" | "improvement",
    unit_number: "1",
    area: 0,
    floors_count: 1,
    construction_year: new Date().getFullYear(),
    modification_year: "" as number | "",
    observations: "",
    use_coeff_item_id: "",
    depreciation_item_id: "",
    improvement_type_item_id: "",
  });
  const [editingBlockId, setEditingBlockId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState(blockForm);
  const [printing, setPrinting] = useState(false);
  const [valuation, setValuation] = useState<Valuation | null>(null);

  const apiBase = API_URL;
  const readOnly = !isNew && appraisal != null && appraisal.can_edit === false;

  function hydrate(data: Appraisal, opts?: { resetChars?: boolean }) {
    setAppraisal(data);
    setAddress(data.address || "");
    setDoor(data.door_number || "");
    if (data.owner) setOwner({ ...data.owner, person_type: (data.owner.person_type as "natural" | "legal") || "natural" });
    if (data.detail) {
      setDetail({
        ...data.detail,
        service_item_ids: data.detail.service_item_ids || [],
        equipment_item_ids: data.detail.equipment_item_ids || [],
        building_name: data.detail.building_name ?? data.building_name ?? "",
        block_label: data.detail.block_label ?? data.block_label ?? "",
        floor_label: data.detail.floor_label ?? data.floor_label ?? "",
        apartment_label: data.detail.apartment_label ?? data.apartment_label ?? "",
      });
    } else {
      setDetail((prev) => ({
        ...prev,
        building_name: data.building_name || "",
        block_label: data.block_label || "",
        floor_label: data.floor_label || "",
        apartment_label: data.apartment_label || "",
      }));
    }
    setCode({
      subdistrict: data.subdistrict || "",
      block_code: data.block_code || "",
      plot_code: data.plot_code || "",
      use_code: data.use_code || "0",
      building_code: data.building_code || "0",
      floor_code: data.floor_code || "0",
      unit_code: data.unit_code || "0",
      door_number: data.door_number || "",
      building_name: data.building_name || "",
    });
    setCoords({
      latitude: data.latitude != null ? Number(data.latitude) : CBBA.lat,
      longitude: data.longitude != null ? Number(data.longitude) : CBBA.lng,
    });
    if (data.latitude != null && data.longitude != null) {
      const sameDefault =
        Math.abs(Number(data.latitude) - CBBA.lat) < 1e-5 && Math.abs(Number(data.longitude) - CBBA.lng) < 1e-5;
      setLocationConfirmed(!sameDefault);
    }
    const nextBlocks = data.blocks || [];
    setBlocks(nextBlocks);
    setPhotos(data.photos || []);
    if (!activeBlockId && nextBlocks.length) setActiveBlockId(nextBlocks[0].id);
    if (opts?.resetChars) {
      const map: Record<string, Record<string, CharPick[]>> = {};
      for (const b of nextBlocks) {
        const sel: Record<string, CharPick[]> = {};
        for (const c of b.characteristics || []) {
          if (!sel[c.group_id]) sel[c.group_id] = [];
          sel[c.group_id].push({ option_id: c.option_id, percentage: Number(c.percentage) });
        }
        map[b.id] = sel;
      }
      setCharByBlock(map);
    }
  }

  useEffect(() => {
    if (isNew) return;
    setLoading(true);
    api<Appraisal>(`/api/v1/appraisals/${id}`, {}, true)
      .then((data) => {
        hydrate(data, { resetChars: true });
        void loadValuation(data.id);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Error al cargar"))
      .finally(() => setLoading(false));
  }, [id, isNew]);

  useEffect(() => {
    const types = [
      "zone_homogeneous",
      "topography",
      "parcel_shape",
      "parcel_location",
      "road_material",
      "utility_service",
      "ipes_factor",
      "land_use",
      "depreciation",
      "improvement_type",
    ];
    Promise.all([
      ...types.map((t) => api<CatalogOption[]>(`/api/v1/catalogs/${t}`, {}, true).then((rows) => [t, rows] as const)),
      api<MediaType[]>("/api/v1/media-types?category=photo", {}, true).then((rows) => ["__media", rows] as const),
    ])
      .then((pairs) => {
        const map = Object.fromEntries(pairs.filter((p) => !String(p[0]).startsWith("__")));
        setCatalogs(map as Record<string, CatalogOption[]>);
        const media = pairs.find((p) => p[0] === "__media");
        if (media) {
          const mt = media[1] as MediaType[];
          setMediaTypes(mt);
          if (mt[0]) setPhotoType(mt[0].code);
        }
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    const year = blocks.find((b) => b.id === activeBlockId)?.construction_year;
    const qs = year ? `?construction_year=${year}` : "";
    api<CharGroup[]>(`/api/v1/characteristics/catalog${qs}`, {}, true)
      .then(setCharGroups)
      .catch(() => undefined);
  }, [activeBlockId, blocks]);

  const stepIndex = useMemo(() => STEPS.findIndex((s) => s.key === step), [step]);

  async function createForm(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const created = await api<Appraisal>(
        "/api/v1/appraisals",
        {
          method: "POST",
          body: JSON.stringify({
            address,
            door_number: door || null,
            owner,
            latitude: coords.latitude,
            longitude: coords.longitude,
          }),
        },
        true,
      );
      hydrate(created);
      setStep("code");
      navigate(`/app/formularios/${created.id}`, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear");
    } finally {
      setLoading(false);
    }
  }

  async function saveOwner(e: FormEvent) {
    e.preventDefault();
    if (readOnly || !appraisal) return;
    setLoading(true);
    setError("");
    try {
      const updated = await api<Appraisal>(
        `/api/v1/appraisals/${appraisal.id}/owner`,
        { method: "PUT", body: JSON.stringify({ ...owner, address, door_number: door || null }) },
        true,
      );
      hydrate(updated);
      setStep("code");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al guardar propietario");
    } finally {
      setLoading(false);
    }
  }

  async function saveDetail(e: FormEvent) {
    e.preventDefault();
    if (readOnly || !appraisal) return;
    setLoading(true);
    setError("");
    try {
      const updated = await api<Appraisal>(
        `/api/v1/appraisals/${appraisal.id}/detail`,
        {
          method: "PUT",
          body: JSON.stringify({
            ...detail,
            latitude: coords.latitude,
            longitude: coords.longitude,
            registry_matricula: owner.registry_matricula || null,
            registry_asiento: owner.registry_asiento || null,
            registry_ddr_date: owner.registry_ddr_date || null,
          }),
        },
        true,
      );
      hydrate(updated);
      void loadValuation(updated.id);
      setStep("blocks");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al guardar detalle");
    } finally {
      setLoading(false);
    }
  }

  async function saveCode(e: FormEvent) {
    e.preventDefault();
    if (readOnly || !appraisal) return;
    if (!locationConfirmed) {
      setError("Ubique el predio en el mapa (pin) o pulse «Centrar en mapa».");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const gisFromCode = {
        approved_area: detail.approved_area,
        zone_item_id: detail.zone_item_id,
        topography_item_id: detail.topography_item_id,
        road_material_item_id: detail.road_material_item_id,
        shape_item_id: detail.shape_item_id,
      };
      const updated = await api<Appraisal>(
        `/api/v1/appraisals/${appraisal.id}/cadastral`,
        {
          method: "PUT",
          body: JSON.stringify({
            ...code,
            latitude: coords.latitude,
            longitude: coords.longitude,
            address: address || null,
          }),
        },
        true,
      );
      hydrate(updated);
      setDetail((prev) => ({
        ...prev,
        approved_area: gisFromCode.approved_area || prev.approved_area,
        zone_item_id: gisFromCode.zone_item_id || prev.zone_item_id,
        topography_item_id: gisFromCode.topography_item_id || prev.topography_item_id,
        road_material_item_id: gisFromCode.road_material_item_id || prev.road_material_item_id,
        shape_item_id: gisFromCode.shape_item_id || prev.shape_item_id,
      }));
      setStep("detail");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al guardar código");
    } finally {
      setLoading(false);
    }
  }

  async function addBlock(e: FormEvent) {
    e.preventDefault();
    if (readOnly || !appraisal) return;
    setLoading(true);
    setError("");
    try {
      const updated = await api<Appraisal>(
        `/api/v1/appraisals/${appraisal.id}/blocks`,
        {
          method: "POST",
          body: JSON.stringify({
            ...blockForm,
            modification_year: blockForm.modification_year === "" ? null : blockForm.modification_year,
            observations: blockForm.observations || null,
            use_coeff_item_id: blockForm.use_coeff_item_id || null,
            depreciation_item_id: blockForm.depreciation_item_id || null,
            improvement_type_item_id: blockForm.unit_kind === "improvement" ? blockForm.improvement_type_item_id || null : null,
          }),
        },
        true,
      );
      hydrate(updated);
      setBlockForm((prev) => ({
        ...prev,
        unit_number: String(Number(prev.unit_number || "0") + 1),
        area: 0,
        modification_year: "",
        observations: "",
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al agregar bloque");
    } finally {
      setLoading(false);
    }
  }

  async function removeBlock(blockId: string) {
    if (readOnly || !appraisal) return;
    setLoading(true);
    setError("");
    try {
      const updated = await api<Appraisal>(`/api/v1/appraisals/${appraisal.id}/blocks/${blockId}`, { method: "DELETE" }, true);
      hydrate(updated);
      if (editingBlockId === blockId) setEditingBlockId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al eliminar bloque");
    } finally {
      setLoading(false);
    }
  }

  function openEditBlock(b: Block) {
    setEditForm({
      unit_kind: b.unit_kind,
      unit_number: b.unit_number,
      area: Number(b.area),
      floors_count: b.floors_count,
      construction_year: b.construction_year,
      modification_year: b.modification_year ?? "",
      observations: b.observations || "",
      use_coeff_item_id: b.use_coeff_item_id || "",
      depreciation_item_id: b.depreciation_item_id || "",
      improvement_type_item_id: b.improvement_type_item_id || "",
    });
    setEditingBlockId(b.id);
  }

  async function saveEditBlock(e: FormEvent) {
    e.preventDefault();
    if (readOnly || !appraisal || !editingBlockId) return;
    setLoading(true);
    setError("");
    try {
      const updated = await api<Appraisal>(
        `/api/v1/appraisals/${appraisal.id}/blocks/${editingBlockId}`,
        {
          method: "PUT",
          body: JSON.stringify({
            ...editForm,
            modification_year: editForm.modification_year === "" ? null : editForm.modification_year,
            observations: editForm.observations || null,
            use_coeff_item_id: editForm.use_coeff_item_id || null,
            depreciation_item_id: editForm.depreciation_item_id || null,
            improvement_type_item_id: editForm.unit_kind === "improvement" ? editForm.improvement_type_item_id || null : null,
          }),
        },
        true,
      );
      hydrate(updated);
      setEditingBlockId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al editar bloque");
    } finally {
      setLoading(false);
    }
  }

  async function handlePrint() {
    if (!appraisal) return;
    setPrinting(true);
    setError("");
    try {
      await printAppraisalPdf(appraisal.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo imprimir");
    } finally {
      setPrinting(false);
    }
  }

  useEffect(() => {
    setCharByBlock((prev) => {
      const next = { ...prev };
      let changed = false;
      for (const b of blocks) {
        if (next[b.id]) continue;
        const sel: Record<string, CharPick[]> = {};
        for (const c of b.characteristics || []) {
          if (!sel[c.group_id]) sel[c.group_id] = [];
          sel[c.group_id].push({ option_id: c.option_id, percentage: Number(c.percentage) });
        }
        next[b.id] = sel;
        changed = true;
      }
      for (const id of Object.keys(next)) {
        if (!blocks.some((b) => b.id === id)) {
          delete next[id];
          changed = true;
        }
      }
      return changed ? next : prev;
    });
    if (blocks.length && !blocks.some((b) => b.id === activeBlockId)) {
      setActiveBlockId(blocks[0].id);
    }
  }, [blocks, activeBlockId]);

  const charSelections = charByBlock[activeBlockId] || {};
  const activeBlock = blocks.find((b) => b.id === activeBlockId);
  const visibleCharGroups = useMemo(() => {
    const kind = activeBlock?.unit_kind || "block";
    const filtered = charGroups.filter(
      (g) => !g.applies_to || g.applies_to === "both" || g.applies_to === kind,
    );
    if (kind === "improvement" && filtered.length === 0) {
      return charGroups.filter(
        (g) => !g.applies_to || g.applies_to === "both" || g.applies_to === "block",
      );
    }
    return filtered;
  }, [charGroups, activeBlock?.unit_kind]);

  function setCharSelections(next: Record<string, CharPick[]>) {
    if (!activeBlockId) return;
    setCharByBlock((prev) => ({ ...prev, [activeBlockId]: next }));
  }

  function applyParcel(parcel: ParcelIdentify) {
    setCode({
      subdistrict: parcel.subdistrict || "",
      block_code: parcel.block_code || "",
      plot_code: parcel.plot_code || "",
      use_code: parcel.use_code || "0",
      building_code: parcel.building_code || "0",
      floor_code: parcel.floor_code || "0",
      unit_code: parcel.unit_code || "0",
      door_number: parcel.property_number || "",
      building_name: "",
    });
    setDetail((prev) => ({
      ...prev,
      approved_area: parcel.area_m2 != null ? Number(Number(parcel.area_m2).toFixed(2)) : prev.approved_area,
      zone_item_id: parcel.zone_item_id ?? prev.zone_item_id,
      topography_item_id: parcel.topography_item_id ?? prev.topography_item_id,
      road_material_item_id: parcel.road_material_item_id ?? prev.road_material_item_id,
      shape_item_id: parcel.shape_item_id ?? prev.shape_item_id,
    }));
    if (parcel.address) setAddress(parcel.address);
    setParcelInfo(
      [
        parcel.cadastral_code,
        parcel.commune,
        parcel.subdistrict_name,
        parcel.area_m2 != null ? `${Number(parcel.area_m2).toFixed(0)} m²` : null,
        parcel.zone_label,
        parcel.road_material_label,
        parcel.topography_label || parcel.slope_raw,
        parcel.shape_label,
        parcel.address,
      ]
        .filter(Boolean)
        .join(" · "),
    );
    if (parcel.centroid_lat != null && parcel.centroid_lng != null) {
      setCoords((prev) => {
        if (pointInParcelRings(prev.latitude, prev.longitude, parcel.rings)) return prev;
        return {
          latitude: Number(parcel.centroid_lat!.toFixed(8)),
          longitude: Number(parcel.centroid_lng!.toFixed(8)),
        };
      });
    }
    setLocationConfirmed(true);
  }

  async function centerOnMap() {
    if (readOnly) return;
    const cad = composeCadastralCode(code);
    const filled = [code.subdistrict, code.block_code, code.plot_code].every(
      (v) => (v || "").replace(/[^0-9A-Za-z]/g, "").length > 0,
    );
    if (!filled) {
      setError("Complete subdistrito, manzana y predio para centrar el mapa.");
      return;
    }
    setLocating(true);
    setError("");
    try {
      const data = await api<{ found: boolean; parcel: ParcelIdentify | null }>(
        `/api/v1/gis/parcel-by-code?code=${encodeURIComponent(cad)}`,
        {},
        true,
      );
      if (!data.found || !data.parcel) {
        setError("No se encontró ese código catastral en la capa de predios.");
        return;
      }
      applyParcel(data.parcel);
      mapPickerRef.current?.showParcel(data.parcel);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo buscar el predio");
    } finally {
      setLocating(false);
    }
  }

  async function centerByCoords() {
    if (readOnly) return;
    const lat = Number(coords.latitude);
    const lng = Number(coords.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      setError("Indique latitud y longitud válidas.");
      return;
    }
    if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
      setError("Latitud/longitud fuera de rango.");
      return;
    }
    setLocating(true);
    setError("");
    setLocationConfirmed(true);
    try {
      const data = await api<{ found: boolean; parcel: ParcelIdentify | null }>(
        `/api/v1/gis/parcel-identify?lat=${lat}&lng=${lng}`,
        {},
        true,
      );
      if (!data.found || !data.parcel) {
        mapPickerRef.current?.showParcel({
          cadastral_code: "(sin predio)",
          subdistrict: code.subdistrict || "00",
          block_code: code.block_code || "000",
          plot_code: code.plot_code || "000",
          use_code: "0",
          building_code: "0",
          floor_code: "0",
          unit_code: "0",
          centroid_lat: lat,
          centroid_lng: lng,
          rings: [],
        });
        setError("No hay predio WMS en esas coordenadas. El mapa se centró en el punto indicado.");
        return;
      }
      applyParcel(data.parcel);
      mapPickerRef.current?.showParcel(data.parcel);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo identificar el predio");
    } finally {
      setLocating(false);
    }
  }

  async function saveCharacteristics(e: FormEvent) {
    e.preventDefault();
    if (readOnly || !appraisal) return;
    if (blocks.length === 0) {
      setStep("photos");
      return;
    }
    setLoading(true);
    setError("");
    try {
      let updated: Appraisal | null = null;
      for (const block of blocks) {
        const selections = charByBlock[block.id] || {};
        const items = Object.values(selections)
          .flat()
          .filter((x) => x.option_id && Number(x.percentage) > 0);
        updated = await api<Appraisal>(
          `/api/v1/appraisals/${appraisal.id}/blocks/${block.id}/characteristics`,
          { method: "PUT", body: JSON.stringify({ items }) },
          true,
        );
      }
      if (updated) hydrate(updated, { resetChars: true });
      void loadValuation(appraisal.id);
      setStep("photos");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al guardar características");
    } finally {
      setLoading(false);
    }
  }

  async function uploadPhoto(file: File) {
    if (readOnly || !appraisal) return;
    setLoading(true);
    setError("");
    try {
      const fd = new FormData();
      fd.append("media_type_code", photoType);
      fd.append("file", file);
      const updated = await api<Appraisal>(`/api/v1/appraisals/${appraisal.id}/photos`, { method: "POST", body: fd }, true);
      hydrate(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al subir foto");
    } finally {
      setLoading(false);
    }
  }

  async function changePhotoType(photoId: string, mediaTypeCode: string) {
    if (readOnly || !appraisal) return;
    setLoading(true);
    setError("");
    try {
      const updated = await api<Appraisal>(
        `/api/v1/appraisals/${appraisal.id}/photos/${photoId}`,
        { method: "PATCH", body: JSON.stringify({ media_type_code: mediaTypeCode }) },
        true,
      );
      hydrate(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cambiar el tipo de foto");
    } finally {
      setLoading(false);
    }
  }

  async function removePhoto(photoId: string) {
    if (readOnly || !appraisal) return;
    setLoading(true);
    setError("");
    try {
      const updated = await api<Appraisal>(`/api/v1/appraisals/${appraisal.id}/photos/${photoId}`, { method: "DELETE" }, true);
      hydrate(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al eliminar foto");
    } finally {
      setLoading(false);
    }
  }

  function toggleService(idSvc: string) {
    const current = detail.service_item_ids || [];
    setDetail({
      ...detail,
      service_item_ids: current.includes(idSvc) ? current.filter((x) => x !== idSvc) : [...current, idSvc],
    });
  }

  function toggleEquipment(idEq: string) {
    const current = detail.equipment_item_ids || [];
    setDetail({
      ...detail,
      equipment_item_ids: current.includes(idEq) ? current.filter((x) => x !== idEq) : [...current, idEq],
    });
  }

  async function loadValuation(appraisalId: string) {
    try {
      const data = await api<Valuation>(`/api/v1/appraisals/${appraisalId}/valuation`, {}, true);
      setValuation(data);
    } catch {
      setValuation(null);
    }
  }

  async function enableCorrection() {
    if (!appraisal) return;
    setLoading(true);
    setError("");
    try {
      const data = await api<Appraisal>(`/api/v1/appraisals/${appraisal.id}/enable-correction`, { method: "POST" }, true);
      hydrate(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo habilitar la corrección");
    } finally {
      setLoading(false);
    }
  }

  async function migrateForm() {
    if (!appraisal) return;
    const label = appraisal.is_remigration ? "remigrar" : "migrar";
    if (!window.confirm(`¿Confirma ${label} el formulario ${appraisal.form_number || ""} al servidor municipal?`)) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await api<Appraisal>(`/api/v1/appraisals/${appraisal.id}/migrate`, { method: "POST" }, true);
      hydrate(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo migrar el formulario");
    } finally {
      setLoading(false);
    }
  }

  if (loading && !appraisal && !isNew) return <div className="page">Cargando formulario…</div>;

  return (
    <div className="page">
      <div className="actions" style={{ marginBottom: "1rem" }}>
        <div>
          <h2>{isNew ? "Nuevo formulario" : `Formulario ${appraisal?.form_number || ""}`}</h2>
          <p className="muted">
            {appraisal ? `${appraisal.status_name} · ${appraisal.address}` : "Paso 1: propietario y dirección del predio"}
          </p>
          {readOnly && (
            <div className="hint" style={{ marginTop: ".55rem" }}>
              {appraisal?.status_code === "migrated"
                ? "Formulario migrado: bloqueado para edición. Un funcionario puede habilitarlo para corrección y luego remigrar."
                : "Solo lectura: este formulario pertenece a otro usuario. Puede consultarlo pero no modificarlo."}
            </div>
          )}
          {appraisal?.status_code === "needs_correction" && appraisal.can_edit && (
            <div className="hint" style={{ marginTop: ".55rem" }}>
              Formulario habilitado para corrección. Tras editar, un funcionario puede remigrarlo (la versión municipal anterior quedará inactiva).
            </div>
          )}
        </div>
        <div style={{ display: "flex", gap: ".5rem", flexWrap: "wrap" }}>
          {appraisal?.can_enable_correction && (
            <button className="btn btn-primary" type="button" disabled={loading} onClick={() => void enableCorrection()}>
              Habilitar para corrección
            </button>
          )}
          {appraisal?.can_migrate && (
            <button className="btn btn-primary" type="button" disabled={loading} onClick={() => void migrateForm()}>
              {appraisal.is_remigration ? "Remigrar" : "Migrar"}
            </button>
          )}
          {!isNew && appraisal && (
            <button className="btn btn-out" type="button" disabled={printing} onClick={() => void handlePrint()}>
              {printing ? "Generando…" : "Imprimir"}
            </button>
          )}
          <Link className="btn btn-out" to="/app/formularios">
            Volver al listado
          </Link>
        </div>
      </div>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <div className="form-stepper">
          {STEPS.map((s, i) => (
            <button
              key={s.key}
              type="button"
              className={`st ${i < stepIndex ? "done" : ""} ${s.key === step ? "on" : ""}`}
              onClick={() => {
                if (!isNew || s.key === "owner") setStep(s.key);
              }}
            >
              {i + 1}. {s.label}
            </button>
          ))}
        </div>
        {error && <div className="error">{error}</div>}

        <fieldset disabled={readOnly} style={{ border: 0, margin: 0, padding: 0, minWidth: 0 }}>
        {(isNew || step === "owner") && (
          <form onSubmit={isNew ? createForm : saveOwner} className="grid2" style={{ marginTop: "1rem" }}>
            <div className="field" style={{ gridColumn: "1 / -1" }}>
              <label>Dirección del predio *</label>
              <input required minLength={3} value={address} onChange={(e) => setAddress(e.target.value)} />
              <span className="muted">Editable. Al ubicar el predio en el mapa se completa sola (puede corregirla).</span>
            </div>
            <div className="field">
              <label>Nº puerta</label>
              <input value={door} onChange={(e) => setDoor(e.target.value)} disabled={!isNew && step !== "owner"} />
            </div>
            <div className="field">
              <label>Tipo de persona *</label>
              <select
                value={owner.person_type}
                onChange={(e) => setOwner({ ...owner, person_type: e.target.value as "natural" | "legal" })}
              >
                <option value="natural">Natural</option>
                <option value="legal">Jurídica</option>
              </select>
            </div>
            {owner.person_type === "natural" ? (
              <>
                <div className="field">
                  <label>Nombres *</label>
                  <input required value={owner.first_name || ""} onChange={(e) => setOwner({ ...owner, first_name: e.target.value })} />
                </div>
                <div className="field">
                  <label>Primer apellido *</label>
                  <input required value={owner.last_name_1 || ""} onChange={(e) => setOwner({ ...owner, last_name_1: e.target.value })} />
                </div>
                <div className="field">
                  <label>Segundo apellido</label>
                  <input value={owner.last_name_2 || ""} onChange={(e) => setOwner({ ...owner, last_name_2: e.target.value })} />
                </div>
              </>
            ) : (
              <div className="field" style={{ gridColumn: "1 / -1" }}>
                <label>Razón social *</label>
                <input required value={owner.legal_name || ""} onChange={(e) => setOwner({ ...owner, legal_name: e.target.value })} />
              </div>
            )}
            <div className="field">
              <label>C.I./NIT *</label>
              <input required minLength={5} value={owner.document_number || ""} onChange={(e) => setOwner({ ...owner, document_number: e.target.value })} disabled={readOnly} />
            </div>
            <div className="field">
              <label>Teléfono / WhatsApp *</label>
              <input
                required
                minLength={7}
                value={owner.phone || ""}
                onChange={(e) => setOwner({ ...owner, phone: e.target.value })}
              />
            </div>
            <div className="field">
              <label>Correo de contacto *</label>
              <input
                type="email"
                required
                value={owner.email || ""}
                onChange={(e) => setOwner({ ...owner, email: e.target.value })}
              />
            </div>
            <div className="field">
              <label>% propiedad</label>
              <DecimalInput
                value={owner.ownership_percent ?? 100}
                onChange={(n) => setOwner({ ...owner, ownership_percent: n ?? 100 })}
              />
            </div>
            <div className="field">
              <label>Nº testimonio</label>
              <input value={owner.deed_number || ""} onChange={(e) => setOwner({ ...owner, deed_number: e.target.value })} />
            </div>
            <div className="field">
              <label>Notario</label>
              <input value={owner.notary_name || ""} onChange={(e) => setOwner({ ...owner, notary_name: e.target.value })} />
            </div>
            <div className="actions" style={{ gridColumn: "1 / -1" }}>
              <span className="muted">Luego: detalle del predio, código catastral y mapa.</span>
              <button className="btn btn-primary" disabled={loading} type="submit">
                {isNew ? "Crear y continuar" : "Guardar propietario"}
              </button>
            </div>
          </form>
        )}

        {!isNew && step === "detail" && (
          <form onSubmit={saveDetail} className="grid2" style={{ marginTop: "1rem" }}>
            {parcelInfo && (
              <div className="hint" style={{ gridColumn: "1 / -1" }}>
                Datos tomados del código catastral / capa de predios ({parcelInfo}). Zona homogénea, IPV, IPRT y forma se completaron aquí; puede editarlos antes de guardar.
              </div>
            )}
            <div className="field">
              <label>Superficie lote (m²) *</label>
              <DecimalInput required value={detail.approved_area} onChange={(n) => setDetail({ ...detail, approved_area: n ?? 0 })} />
            </div>
            <div className="field">
              <label>Frente (ml) *</label>
              <DecimalInput required value={detail.front_length} onChange={(n) => setDetail({ ...detail, front_length: n ?? 0 })} />
            </div>
            <div className="field">
              <label>Fondo (ml)</label>
              <DecimalInput value={detail.depth_length} onChange={(n) => setDetail({ ...detail, depth_length: n })} />
            </div>
            <div className="field">
              <label>Matrícula DDRR</label>
              <input
                value={owner.registry_matricula || ""}
                onChange={(e) => setOwner({ ...owner, registry_matricula: e.target.value })}
                placeholder="Matrícula de derechos reales"
              />
            </div>
            <div className="field">
              <label>Asiento DDRR</label>
              <input
                value={owner.registry_asiento || ""}
                onChange={(e) => setOwner({ ...owner, registry_asiento: e.target.value })}
                placeholder="Asiento"
              />
            </div>
            <div className="field">
              <label>Fecha derechos reales (DDRR)</label>
              <input
                type="date"
                value={(owner.registry_ddr_date || "").slice(0, 10)}
                onChange={(e) => setOwner({ ...owner, registry_ddr_date: e.target.value || null })}
              />
            </div>
            <div className="field" style={{ gridColumn: "1 / -1" }}>
              <strong>Descripción del inmueble</strong>
              <p className="muted" style={{ margin: ".25rem 0 0", fontSize: ".85rem" }}>
                Datos de ubicación dentro del edificio o complejo (si aplica).
              </p>
            </div>
            <div className="field">
              <label>Edificio</label>
              <input
                value={detail.building_name || ""}
                onChange={(e) => setDetail({ ...detail, building_name: e.target.value })}
                placeholder="Nombre del edificio"
              />
            </div>
            <div className="field">
              <label>Bloque / torre</label>
              <input
                value={detail.block_label || ""}
                onChange={(e) => setDetail({ ...detail, block_label: e.target.value })}
                placeholder="Ej. Bloque A"
              />
            </div>
            <div className="field">
              <label>Piso</label>
              <input
                value={detail.floor_label || ""}
                onChange={(e) => setDetail({ ...detail, floor_label: e.target.value })}
                placeholder="Ej. 3er piso"
              />
            </div>
            <div className="field">
              <label>Dpto. / unidad</label>
              <input
                value={detail.apartment_label || ""}
                onChange={(e) => setDetail({ ...detail, apartment_label: e.target.value })}
                placeholder="Ej. Dpto. 301"
              />
            </div>
            {(
              [
                ["zone_item_id", "Zona homogénea (Vb)", "zone_homogeneous"],
                ["topography_item_id", "IPRT — Relieve topográfico", "topography"],
                ["road_material_item_id", "IPV — Material de vía", "road_material"],
                ["location_item_id", "Ubicación en manzana", "parcel_location"],
                ["shape_item_id", "Forma del predio", "parcel_shape"],
              ] as const
            ).map(([field, label, cat]) => (
              <div className="field" key={field}>
                <label>{label} *</label>
                <select
                  required
                  value={(detail[field] as string) || ""}
                  onChange={(e) => setDetail({ ...detail, [field]: e.target.value })}
                >
                  <option value="">Seleccione…</option>
                  {(catalogs[cat] || []).map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
            ))}
            <div className="field" style={{ gridColumn: "1 / -1" }}>
              <label>IPIU — Infraestructura urbana (servicios)</label>
              <div className="svcs">
                {(catalogs.utility_service || []).map((s) => (
                  <label key={s.id}>
                    <input
                      type="checkbox"
                      checked={(detail.service_item_ids || []).includes(s.id)}
                      onChange={() => toggleService(s.id)}
                    />{" "}
                    {s.label}
                  </label>
                ))}
              </div>
            </div>
            <div className="field" style={{ gridColumn: "1 / -1" }}>
              <label>IPES — Equipamiento social</label>
              <div className="svcs">
                {(catalogs.ipes_factor || []).map((s) => (
                  <label key={s.id}>
                    <input
                      type="checkbox"
                      checked={(detail.equipment_item_ids || []).includes(s.id)}
                      onChange={() => toggleEquipment(s.id)}
                    />{" "}
                    {s.label}
                  </label>
                ))}
              </div>
            </div>
            <div className="field" style={{ gridColumn: "1 / -1" }}>
              <label>Observaciones</label>
              <input value={detail.observations || ""} onChange={(e) => setDetail({ ...detail, observations: e.target.value })} />
            </div>
            <div className="actions" style={{ gridColumn: "1 / -1" }}>
              <button className="btn btn-out" type="button" onClick={() => setStep("code")}>
                Atrás
              </button>
              <button className="btn btn-primary" disabled={loading} type="submit">
                Guardar y continuar
              </button>
            </div>
          </form>
        )}

        {!isNew && (
          <form
            onSubmit={saveCode}
            className="grid2"
            style={{ marginTop: "1rem", display: step === "code" ? undefined : "none" }}
            aria-hidden={step !== "code"}
          >
            <div className="field">
              <label>Subdistrito *</label>
              <input required value={code.subdistrict} onChange={(e) => setCode({ ...code, subdistrict: e.target.value })} />
            </div>
            <div className="field">
              <label>Manzana *</label>
              <input required value={code.block_code} onChange={(e) => setCode({ ...code, block_code: e.target.value })} />
            </div>
            <div className="field">
              <label>Predio *</label>
              <input required value={code.plot_code} onChange={(e) => setCode({ ...code, plot_code: e.target.value })} />
            </div>
            <div className="field">
              <label>Uso</label>
              <input value={code.use_code} onChange={(e) => setCode({ ...code, use_code: e.target.value })} />
            </div>
            <div className="field">
              <label>Bloque</label>
              <input value={code.building_code} onChange={(e) => setCode({ ...code, building_code: e.target.value })} />
            </div>
            <div className="field">
              <label>Planta</label>
              <input value={code.floor_code} onChange={(e) => setCode({ ...code, floor_code: e.target.value })} />
            </div>
            <div className="field">
              <label>Unidad</label>
              <input value={code.unit_code} onChange={(e) => setCode({ ...code, unit_code: e.target.value })} />
            </div>
            <div className="field">
              <label>Código generado</label>
              <input
                disabled
                value={
                  [code.subdistrict, code.block_code, code.plot_code].some((v) => (v || "").trim())
                    ? composeCadastralCode(code)
                    : appraisal?.cadastral_code || "(se genera al guardar)"
                }
              />
            </div>
            <div className="field" style={{ alignSelf: "end" }}>
              <button
                type="button"
                className="btn btn-out"
                style={{ width: "100%" }}
                disabled={readOnly || locating}
                onClick={() => void centerOnMap()}
              >
                {locating ? "Buscando predio…" : "Centrar por código"}
              </button>
            </div>

            <div className="field" style={{ gridColumn: "1 / -1" }}>
              <label>Mapa satelital + predios WMS GAMC *</label>
              <PropertyMapPicker
                ref={mapPickerRef}
                latitude={coords.latitude}
                longitude={coords.longitude}
                active={step === "code"}
                onChange={(lat, lng) => {
                  setCoords({ latitude: lat, longitude: lng });
                  setLocationConfirmed(true);
                }}
                onParcel={applyParcel}
                interactive={!readOnly}
              />
              {parcelInfo && (
                <div className="hint" style={{ marginTop: ".55rem" }}>
                  Predio WMS: {parcelInfo}. Código y dirección se actualizaron aquí; zona homogénea, material de vía, relieve y forma del predio se completaron en Detalle predio.
                </div>
              )}
            </div>
            <div className="field" style={{ gridColumn: "1 / -1" }}>
              <label>Dirección del predio</label>
              <input
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="Se completa al identificar el predio en el mapa"
              />
            </div>
            <div className="field">
              <label>Latitud</label>
              <input
                type="number"
                step="any"
                readOnly={readOnly}
                value={coords.latitude}
                onChange={(e) => {
                  const latitude = Number(e.target.value);
                  setCoords((c) => ({ ...c, latitude }));
                  if (Number.isFinite(latitude)) setLocationConfirmed(true);
                }}
              />
            </div>
            <div className="field">
              <label>Longitud</label>
              <input
                type="number"
                step="any"
                readOnly={readOnly}
                value={coords.longitude}
                onChange={(e) => {
                  const longitude = Number(e.target.value);
                  setCoords((c) => ({ ...c, longitude }));
                  if (Number.isFinite(longitude)) setLocationConfirmed(true);
                }}
              />
            </div>
            <div className="field" style={{ alignSelf: "end" }}>
              <button
                type="button"
                className="btn btn-out"
                style={{ width: "100%" }}
                disabled={readOnly || locating}
                onClick={() => void centerByCoords()}
              >
                {locating ? "Identificando…" : "Centrar por coordenadas"}
              </button>
            </div>

            <div className="actions" style={{ gridColumn: "1 / -1" }}>
              <button className="btn btn-out" type="button" onClick={() => setStep("owner")}>
                Atrás
              </button>
              <button className="btn btn-primary" disabled={loading} type="submit">
                Guardar ubicación y continuar
              </button>
            </div>
          </form>
        )}

        {!isNew && step === "blocks" && (
          <div style={{ marginTop: "1rem" }}>
            <form onSubmit={addBlock} className="grid2">
              <div className="field">
                <label>Tipo *</label>
                <select
                  value={blockForm.unit_kind}
                  onChange={(e) => setBlockForm({ ...blockForm, unit_kind: e.target.value as "block" | "improvement" })}
                >
                  <option value="block">Bloque constructivo</option>
                  <option value="improvement">Mejora</option>
                </select>
              </div>
              <div className="field">
                <label>Nº unidad *</label>
                <input required value={blockForm.unit_number} onChange={(e) => setBlockForm({ ...blockForm, unit_number: e.target.value })} />
              </div>
              <div className="field">
                <label>Superficie (m²) *</label>
                <DecimalInput
                  required
                  value={blockForm.area || null}
                  onChange={(n) => setBlockForm({ ...blockForm, area: n ?? 0 })}
                />
              </div>
              <div className="field">
                <label>Plantas *</label>
                <input
                  type="number"
                  min={1}
                  required
                  value={blockForm.floors_count}
                  onChange={(e) => setBlockForm({ ...blockForm, floors_count: Number(e.target.value) })}
                />
              </div>
              <div className="field">
                <label>Año construcción *</label>
                <input
                  type="number"
                  min={1800}
                  max={2100}
                  required
                  value={blockForm.construction_year}
                  onChange={(e) => setBlockForm({ ...blockForm, construction_year: Number(e.target.value) })}
                />
              </div>
              <div className="field">
                <label>Año modificación</label>
                <input
                  type="number"
                  min={1800}
                  max={2100}
                  value={blockForm.modification_year}
                  onChange={(e) =>
                    setBlockForm({
                      ...blockForm,
                      modification_year: e.target.value === "" ? "" : Number(e.target.value),
                    })
                  }
                  placeholder="Opcional"
                />
              </div>
              <div className="field" style={{ gridColumn: "1 / -1" }}>
                <p className="muted" style={{ margin: 0, fontSize: ".85rem" }}>
                  El primer registro suele ser el bloque de construcción; luego puede agregar mejoras.
                  En cada fila indique año de construcción y, si hubo remodelación, el año de modificación.
                </p>
              </div>
              <div className="field">
                <label>Uso del bloque</label>
                <select
                  value={blockForm.use_coeff_item_id}
                  onChange={(e) => setBlockForm({ ...blockForm, use_coeff_item_id: e.target.value })}
                >
                  <option value="">Residencial (1,00)</option>
                  {(catalogs.land_use || []).map((o) => (
                    <option key={o.id} value={o.id}>{o.label}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Depreciación / antigüedad</label>
                <select
                  value={blockForm.depreciation_item_id}
                  onChange={(e) => setBlockForm({ ...blockForm, depreciation_item_id: e.target.value })}
                >
                  <option value="">Sin depreciar (1,00)</option>
                  {(catalogs.depreciation || []).map((o) => (
                    <option key={o.id} value={o.id}>{o.label}</option>
                  ))}
                </select>
              </div>
              {blockForm.unit_kind === "improvement" && (
                <div className="field">
                  <label>Tipo de mejora</label>
                  <select
                    value={blockForm.improvement_type_item_id}
                    onChange={(e) => setBlockForm({ ...blockForm, improvement_type_item_id: e.target.value })}
                  >
                    <option value="">Según puntaje de características</option>
                    {(catalogs.improvement_type || []).map((o) => (
                      <option key={o.id} value={o.id}>{o.label}</option>
                    ))}
                  </select>
                </div>
              )}
              <div className="field">
                <label>Observaciones</label>
                <input value={blockForm.observations} onChange={(e) => setBlockForm({ ...blockForm, observations: e.target.value })} />
              </div>
              <div className="actions" style={{ gridColumn: "1 / -1" }}>
                <span className="muted">Puede agregar varios bloques. Las características se definen en el siguiente paso.</span>
                <button className="btn btn-primary" disabled={loading} type="submit">
                  Agregar bloque
                </button>
              </div>
            </form>

            <div className="table-wrap" style={{ marginTop: "1rem" }}>
              <table>
                <thead>
                  <tr>
                    <th>Tipo</th>
                    <th>Nº</th>
                    <th>Área</th>
                    <th>Plantas</th>
                    <th>Año constr.</th>
                    <th>Año modif.</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {blocks.length === 0 && (
                    <tr>
                      <td colSpan={7} className="muted">
                        Sin bloques aún. Puede continuar si el predio no tiene construcción.
                      </td>
                    </tr>
                  )}
                  {blocks.map((b) => (
                    <tr key={b.id}>
                      <td>{b.unit_kind === "block" ? "Bloque" : "Mejora"}</td>
                      <td>{b.unit_number}</td>
                      <td>{b.area} m²</td>
                      <td>{b.floors_count}</td>
                      <td>{b.construction_year}</td>
                      <td>{b.modification_year || "—"}</td>
                      <td>
                        <div style={{ display: "flex", gap: ".35rem", flexWrap: "wrap" }}>
                          <button
                            type="button"
                            className="btn btn-out"
                            style={{ padding: ".35rem .7rem" }}
                            disabled={readOnly}
                            onClick={() => openEditBlock(b)}
                          >
                            Editar
                          </button>
                          <button type="button" className="btn btn-out" style={{ padding: ".35rem .7rem" }} onClick={() => removeBlock(b.id)}>
                            Quitar
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="actions" style={{ marginTop: "1rem" }}>
              <button className="btn btn-out" type="button" onClick={() => setStep("detail")}>
                Atrás
              </button>
              <button className="btn btn-primary" type="button" onClick={() => setStep("chars")}>
                Continuar a características
              </button>
            </div>
          </div>
        )}

        {!isNew && step === "chars" && (
          <form onSubmit={saveCharacteristics} style={{ marginTop: "1rem" }}>
            {blocks.length === 0 ? (
              <div className="hint">No hay bloques. Puede volver atrás a agregarlos o continuar a fotografías.</div>
            ) : (
              <>
                <div className="field" style={{ maxWidth: 360, marginBottom: "1rem" }}>
                  <label>Bloque a caracterizar</label>
                  <select
                    value={activeBlockId}
                    onChange={(e) => setActiveBlockId(e.target.value)}
                  >
                    {blocks.map((b) => {
                      const picks = charByBlock[b.id] || {};
                      const n = Object.values(picks)
                        .flat()
                        .filter((x) => Number(x.percentage) > 0).length;
                      return (
                        <option key={b.id} value={b.id}>
                          {b.unit_kind === "block" ? "Bloque" : "Mejora"} {b.unit_number} ({b.area} m²)
                          {n ? ` · ${n} asignado${n === 1 ? "" : "s"}` : ""}
                        </option>
                      );
                    })}
                  </select>
                  <p className="muted" style={{ margin: ".35rem 0 0", fontSize: ".85rem" }}>
                    Al cambiar de bloque se conservan los valores ya asignados. «Guardar» persiste todos los bloques.
                  </p>
                </div>
                <CharacteristicsPanel
                  groups={visibleCharGroups}
                  value={charSelections}
                  onChange={setCharSelections}
                  apiBase={apiBase}
                  readOnly={readOnly}
                />
              </>
            )}
            <div className="actions" style={{ marginTop: "1rem" }}>
              <button className="btn btn-out" type="button" onClick={() => setStep("blocks")}>
                Atrás
              </button>
              {blocks.length === 0 ? (
                <button className="btn btn-primary" type="button" onClick={() => setStep("photos")}>
                  Continuar a fotografías
                </button>
              ) : (
                <button className="btn btn-primary" disabled={loading || !activeBlockId} type="submit">
                  Guardar características (todos los bloques)
                </button>
              )}
            </div>
          </form>
        )}

        {!isNew && step === "photos" && (
          <div style={{ marginTop: "1rem" }}>
            <div className="photo-uploader">
              <div className="field">
                <label>Tipo de fotografía *</label>
                <select value={photoType} onChange={(e) => setPhotoType(e.target.value)}>
                  {mediaTypes.map((m) => (
                    <option key={m.id} value={m.code}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </div>
              <div
                className={`photo-drop${photoDragOver ? " is-over" : ""}`}
                onDragEnter={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  if (!readOnly) setPhotoDragOver(true);
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  e.dataTransfer.dropEffect = "copy";
                  if (!readOnly) setPhotoDragOver(true);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  if (e.currentTarget.contains(e.relatedTarget as Node)) return;
                  setPhotoDragOver(false);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setPhotoDragOver(false);
                  if (readOnly || loading) return;
                  const files = Array.from(e.dataTransfer.files).filter((f) => f.type.startsWith("image/"));
                  void (async () => {
                    for (const f of files) await uploadPhoto(f);
                  })();
                }}
              >
                <label>
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    disabled={loading || readOnly}
                    onChange={(e) => {
                      const files = Array.from(e.target.files || []);
                      void (async () => {
                        for (const f of files) await uploadPhoto(f);
                      })();
                      e.target.value = "";
                    }}
                  />
                  <strong>Elegir o soltar imágenes</strong>
                  <span className="muted">JPG, PNG o WEBP — se asignan al tipo seleccionado arriba</span>
                </label>
              </div>
            </div>
            <div className="photo-grid">
              {photos.length === 0 && <p className="muted">Sin fotografías todavía.</p>}
              {photos.map((p) => (
                <figure className="photo-card" key={p.id}>
                  <img src={mediaUrl(p.url)} alt={p.media_type_name} />
                  <figcaption>
                    <select
                      value={p.media_type_code}
                      disabled={readOnly || loading}
                      onChange={(e) => void changePhotoType(p.id, e.target.value)}
                      aria-label="Tipo de fotografía"
                    >
                      {mediaTypes.map((m) => (
                        <option key={m.id} value={m.code}>
                          {m.name}
                        </option>
                      ))}
                    </select>
                    <button type="button" className="btn btn-out" style={{ padding: ".25rem .55rem" }} onClick={() => removePhoto(p.id)}>
                      Quitar
                    </button>
                  </figcaption>
                </figure>
              ))}
            </div>
            <div className="actions" style={{ marginTop: "1rem" }}>
              <button className="btn btn-out" type="button" onClick={() => setStep("chars")}>
                Atrás
              </button>
              <Link className="btn btn-primary" to="/app/formularios">
                Finalizar y volver al listado
              </Link>
              {appraisal && (
                <button className="btn btn-out" type="button" disabled={printing} onClick={() => void handlePrint()}>
                  {printing ? "Generando…" : "Imprimir"}
                </button>
              )}
            </div>
            {valuation && (
              <section className="card" style={{ marginTop: "1.25rem" }}>
                <strong>Avalúo calculado</strong>
                <p className="muted" style={{ fontSize: ".85rem" }}>
                  VSz = Vb × IPIU × IPES × IPRT · VSvía = VSz × IPV · terreno = superficie × VSvía × ubicación × forma
                </p>
                <div className="grid2" style={{ marginTop: ".6rem" }}>
                  <div><span className="muted">IPIU</span><div><b>{valuation.indices.ipiu.toFixed(2)}</b></div></div>
                  <div><span className="muted">IPES</span><div><b>{valuation.indices.ipes.toFixed(2)}</b></div></div>
                  <div><span className="muted">IPRT</span><div><b>{valuation.indices.iprt.toFixed(2)}</b></div></div>
                  <div><span className="muted">IPV</span><div><b>{valuation.indices.ipv.toFixed(2)}</b></div></div>
                  <div><span className="muted">Vb zona (Bs/m²)</span><div><b>{money(valuation.zone_m2)}</b></div></div>
                  <div><span className="muted">VSvía (Bs/m²)</span><div><b>{money(valuation.vsvia)}</b></div></div>
                  <div><span className="muted">Terreno</span><div><b>{money(valuation.land_value)}</b></div></div>
                  <div><span className="muted">Bloques</span><div><b>{money(valuation.blocks_value)}</b></div></div>
                  <div><span className="muted">Mejoras</span><div><b>{money(valuation.improvements_value)}</b></div></div>
                  <div><span className="muted">Total</span><div><b>{money(valuation.total_value)}</b></div></div>
                </div>
              </section>
            )}
          </div>
        )}
        </fieldset>
      </div>

      {editingBlockId && (
        <div className="modal-backdrop" role="presentation" onClick={() => setEditingBlockId(null)}>
          <div className="modal modal--wide" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <div className="actions" style={{ marginBottom: ".35rem" }}>
              <strong>Editar bloque / mejora</strong>
              <button type="button" className="btn btn-out" onClick={() => setEditingBlockId(null)}>
                Cerrar
              </button>
            </div>
            <form onSubmit={saveEditBlock} className="grid2">
              <div className="field">
                <label>Tipo *</label>
                <select
                  value={editForm.unit_kind}
                  onChange={(e) => setEditForm({ ...editForm, unit_kind: e.target.value as "block" | "improvement" })}
                >
                  <option value="block">Bloque constructivo</option>
                  <option value="improvement">Mejora</option>
                </select>
              </div>
              <div className="field">
                <label>Nº unidad *</label>
                <input required value={editForm.unit_number} onChange={(e) => setEditForm({ ...editForm, unit_number: e.target.value })} />
              </div>
              <div className="field">
                <label>Superficie (m²) *</label>
                <DecimalInput
                  required
                  value={editForm.area || null}
                  onChange={(n) => setEditForm({ ...editForm, area: n ?? 0 })}
                />
              </div>
              <div className="field">
                <label>Plantas *</label>
                <input
                  type="number"
                  min={1}
                  required
                  value={editForm.floors_count}
                  onChange={(e) => setEditForm({ ...editForm, floors_count: Number(e.target.value) })}
                />
              </div>
              <div className="field">
                <label>Año construcción *</label>
                <input
                  type="number"
                  min={1800}
                  max={2100}
                  required
                  value={editForm.construction_year}
                  onChange={(e) => setEditForm({ ...editForm, construction_year: Number(e.target.value) })}
                />
              </div>
              <div className="field">
                <label>Año modificación</label>
                <input
                  type="number"
                  min={1800}
                  max={2100}
                  value={editForm.modification_year}
                  onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      modification_year: e.target.value === "" ? "" : Number(e.target.value),
                    })
                  }
                  placeholder="Opcional"
                />
              </div>
              <div className="field">
                <label>Uso del bloque</label>
                <select
                  value={editForm.use_coeff_item_id}
                  onChange={(e) => setEditForm({ ...editForm, use_coeff_item_id: e.target.value })}
                >
                  <option value="">Residencial (1,00)</option>
                  {(catalogs.land_use || []).map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Depreciación / antigüedad</label>
                <select
                  value={editForm.depreciation_item_id}
                  onChange={(e) => setEditForm({ ...editForm, depreciation_item_id: e.target.value })}
                >
                  <option value="">Sin depreciar (1,00)</option>
                  {(catalogs.depreciation || []).map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              {editForm.unit_kind === "improvement" && (
                <div className="field">
                  <label>Tipo de mejora</label>
                  <select
                    value={editForm.improvement_type_item_id}
                    onChange={(e) => setEditForm({ ...editForm, improvement_type_item_id: e.target.value })}
                  >
                    <option value="">Según puntaje de características</option>
                    {(catalogs.improvement_type || []).map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div className="field" style={{ gridColumn: "1 / -1" }}>
                <label>Observaciones</label>
                <input value={editForm.observations} onChange={(e) => setEditForm({ ...editForm, observations: e.target.value })} />
              </div>
              <div className="actions" style={{ gridColumn: "1 / -1" }}>
                <button type="button" className="btn btn-out" onClick={() => setEditingBlockId(null)}>
                  Cancelar
                </button>
                <button className="btn btn-primary" disabled={loading} type="submit">
                  Guardar cambios
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {printing && (
        <div className="print-loader-backdrop" role="status" aria-live="polite">
          <div className="print-loader">
            <div className="print-loader__spin" aria-hidden />
            <strong>Generando documento…</strong>
            <p className="muted" style={{ margin: ".45rem 0 0" }}>
              Espere un momento. Se abrirá el diálogo de impresión del navegador.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
