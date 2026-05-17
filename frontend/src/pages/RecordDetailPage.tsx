import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useParams } from "react-router-dom";
import { z } from "zod";
import { MapContainer, Marker, Polyline, Popup, TileLayer } from "react-leaflet";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { Panel } from "../components/Panel";
import { StatusBadge } from "../components/StatusBadge";
import { api } from "../lib/api";
import { Aircraft, AltitudeProfilePoint, FlightRecord, Pilot, WaypointPoint } from "../lib/types";

const schema = z.object({
  aircraft: z.coerce.number().nullable(),
  pilot: z.coerce.number().nullable(),
  purpose: z.array(z.string()).default([]),
  purpose_other: z.string().default(""),
  special_flight_types: z.array(z.string()).default([]),
  route_summary: z.string().default(""),
  official_weather: z.string().min(1),
  official_temperature_c: z.coerce.number(),
  official_wind_speed_mps: z.coerce.number(),
  safety_notes: z.string().default(""),
  article_notes: z.string().default(""),
  pilot_signature: z.string().default(""),
}).superRefine((values, context) => {
  if (values.purpose.includes("その他") && !values.purpose_other.trim()) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      message: "その他の内容を入力してください",
      path: ["purpose_other"],
    });
  }
});

const PURPOSE_OPTIONS = [
  "空撮",
  "取材",
  "点検",
  "警備",
  "物流",
  "測量",
  "農林水産業",
  "資材管理",
  "自然観測",
  "事故・災害",
  "趣味",
  "研究開発",
  "訓練",
  "その他",
] as const;

const FLIGHT_METHOD_OPTIONS = [
  "空港周辺",
  "150m以上",
  "人口集中地区（DID）",
  "緊急用務空域",
  "目視外飛行",
  "夜間飛行",
  "人または物件から30m未満",
  "催し場所上空",
  "危険物の輸送",
  "物件投下",
] as const;

type RecordFormValues = z.infer<typeof schema>;
const YAMASHIRO_SHINMEICHO_ADDRESS = "石川県加賀市山代温泉神明町付近";
const YAMASHIRO_SHINMEICHO_COORD = { lat: 36.28646816998257, lng: 136.35569629956606 };
const recordItemClass = "grid gap-1 rounded-2xl border border-slate-200 bg-white/70 px-4 py-3 md:grid-cols-[13rem_1fr] md:items-start";
const recordLabelClass = "font-semibold text-slate-500";
const recordValueClass = "text-slate-800";

function formatNumber(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return value.toFixed(digits);
}

function formatDate(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  return new Date(`${value}T00:00:00`).toLocaleDateString("ja-JP");
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("ja-JP");
}

function formatCompactNumber(value: number, digits: number) {
  return value.toFixed(digits).replace(/\.0+$/, "").replace(/(\.\d*?)0+$/, "$1");
}

function formatDurationMinutes(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "-";
  }
  const minutes = value / 60;
  return `${formatCompactNumber(minutes, minutes < 10 ? 1 : 0)}分`;
}

function formatDurationHours(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "-";
  }
  const hours = value / 3600;
  return `${formatCompactNumber(hours, hours < 1 ? 2 : 1)}時間`;
}

function formatCoordinate(lat: number | null | undefined, lng: number | null | undefined) {
  if (lat === null || lat === undefined || lng === null || lng === undefined) {
    return "";
  }
  return `緯度 ${lat.toFixed(6)}, 経度 ${lng.toFixed(6)}`;
}

function distanceMeters(lat1: number, lng1: number, lat2: number, lng2: number) {
  const radius = 6371000;
  const phi1 = lat1 * Math.PI / 180;
  const phi2 = lat2 * Math.PI / 180;
  const dphi = (lat2 - lat1) * Math.PI / 180;
  const dlambda = (lng2 - lng1) * Math.PI / 180;
  const a = Math.sin(dphi / 2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin(dlambda / 2) ** 2;
  return 2 * radius * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function isNearYamashiroShinmeicho(lat: number | null | undefined, lng: number | null | undefined) {
  if (lat === null || lat === undefined || lng === null || lng === undefined) {
    return false;
  }
  return distanceMeters(lat, lng, YAMASHIRO_SHINMEICHO_COORD.lat, YAMASHIRO_SHINMEICHO_COORD.lng) <= 700;
}

function formatPlace(address: string, lat: number | null | undefined, lng: number | null | undefined) {
  const coordinate = formatCoordinate(lat, lng);
  if (isNearYamashiroShinmeicho(lat, lng)) {
    return YAMASHIRO_SHINMEICHO_ADDRESS;
  }
  if (!address && !coordinate) {
    return "-";
  }
  if (!address) {
    return coordinate;
  }
  return address;
}

function needsAddressRefresh(record: FlightRecord) {
  const isFallback = (address: string) => !address || address.startsWith("緯度 ");
  return (
    (record.takeoff_lat !== null && record.takeoff_lng !== null && isFallback(record.takeoff_address)) ||
    (record.landing_lat !== null && record.landing_lng !== null && isFallback(record.landing_address))
  );
}

function splitStoredValues(value: string) {
  return value
    .split(/[、,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parsePurpose(value: string) {
  const selected = new Set<string>();
  const otherValues: string[] = [];
  for (const item of splitStoredValues(value)) {
    if (PURPOSE_OPTIONS.includes(item as (typeof PURPOSE_OPTIONS)[number])) {
      selected.add(item);
      continue;
    }
    if (item.startsWith("その他:")) {
      selected.add("その他");
      const otherValue = item.slice("その他:".length).trim();
      if (otherValue) {
        otherValues.push(otherValue);
      }
      continue;
    }
    otherValues.push(item);
  }
  if (otherValues.length) {
    selected.add("その他");
  }
  return { purpose: Array.from(selected), purpose_other: otherValues.join("、") };
}

function parseFlightMethods(value: string) {
  return splitStoredValues(value).filter((item) => (
    FLIGHT_METHOD_OPTIONS.includes(item as (typeof FLIGHT_METHOD_OPTIONS)[number])
  ));
}

function toFlightRecordPayload(values: RecordFormValues) {
  const { purpose_other, ...payload } = values;
  const selectedPurposes = values.purpose.filter((item) => item !== "その他");
  if (values.purpose.includes("その他")) {
    selectedPurposes.push(`その他: ${purpose_other.trim()}`);
  }
  return {
    ...payload,
    purpose: selectedPurposes.join("、"),
    special_flight_types: values.special_flight_types.join("、"),
  };
}

function formatAltitudeMeters(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  const rounded = Math.round(value * 10) / 10;
  return `${Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1)}m`;
}

function formatDistanceMeters(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  if (value >= 1000) {
    return `${formatCompactNumber(value / 1000, 1)}km`;
  }
  return `${Math.round(value)}m`;
}

function waypointDistanceMeters(start: WaypointPoint, end: WaypointPoint) {
  if (
    Number.isFinite(start.lat) &&
    Number.isFinite(start.lng) &&
    Number.isFinite(end.lat) &&
    Number.isFinite(end.lng)
  ) {
    return distanceMeters(start.lat, start.lng, end.lat, end.lng);
  }
  return Math.hypot(end.x_m - start.x_m, end.y_m - start.y_m);
}

function addCylinderBetween(scene: THREE.Scene | THREE.Group, start: THREE.Vector3, end: THREE.Vector3, material: THREE.Material, radius = 0.045) {
  const direction = new THREE.Vector3().subVectors(end, start);
  const length = direction.length();
  if (length <= 0) {
    return;
  }

  const geometry = new THREE.CylinderGeometry(radius, radius, length, 12);
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.copy(new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5));
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
  scene.add(mesh);
}

function addLine(scene: THREE.Scene | THREE.Group, points: THREE.Vector3[], material: THREE.LineBasicMaterial) {
  if (points.length < 2) {
    return;
  }
  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  scene.add(new THREE.Line(geometry, material));
}

function addLineSegments(scene: THREE.Scene | THREE.Group, segments: THREE.Vector3[], material: THREE.LineBasicMaterial) {
  if (segments.length < 2) {
    return;
  }
  const geometry = new THREE.BufferGeometry().setFromPoints(segments);
  scene.add(new THREE.LineSegments(geometry, material));
}

function createLabelSprite(text: string, color = "#334155", width = 256, scaleX = 0.72) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = 96;
  const context = canvas.getContext("2d");
  if (context) {
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.font = "700 42px sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.lineWidth = 8;
    context.strokeStyle = "rgba(255,255,255,0.92)";
    context.strokeText(text, canvas.width / 2, canvas.height / 2);
    context.fillStyle = color;
    context.fillText(text, canvas.width / 2, canvas.height / 2);
  }
  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(scaleX, 0.27, 1);
  return sprite;
}

type AltitudeProfile3DProps = {
  profile: AltitudeProfilePoint[];
  waypoints: WaypointPoint[];
};

function AltitudeProfile3D({ profile, waypoints }: AltitudeProfile3DProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const hasProfile = profile.length >= 2;

  useEffect(() => {
    if (!hasProfile || !containerRef.current || !canvasRef.current) {
      return;
    }

    const container = containerRef.current;
    const canvas = canvasRef.current;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf8fbfd);

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 120);
    camera.position.set(7.4, 6.2, 8.6);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 4.5;
    controls.maxDistance = 22;
    controls.target.set(0, 2.1, 0);

    const renderScene = () => {
      renderer.render(scene, camera);
    };

    const resize = () => {
      const width = container.clientWidth;
      const height = container.clientHeight;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderScene();
    };

    const group = new THREE.Group();
    scene.add(group);

    scene.add(new THREE.AmbientLight(0xffffff, 1.35));
    const light = new THREE.DirectionalLight(0xffffff, 1.9);
    light.position.set(3, 7, 4);
    scene.add(light);
    const fillLight = new THREE.DirectionalLight(0xdcfce7, 0.7);
    fillLight.position.set(-5, 4, -6);
    scene.add(fillLight);

    const plotWaypoints = waypoints.filter(
      (point) => Number.isFinite(point.x_m) && Number.isFinite(point.y_m) && Number.isFinite(point.relative_altitude_m),
    );
    const xValues = [...profile.map((point) => point.x_m), ...plotWaypoints.map((point) => point.x_m)];
    const yValues = [...profile.map((point) => point.y_m), ...plotWaypoints.map((point) => point.y_m)];
    const altitudeValues = [
      ...profile.map((point) => Math.max(point.relative_altitude_m ?? 0, 0)),
      ...plotWaypoints.map((point) => Math.max(point.relative_altitude_m ?? 0, 0)),
    ];
    const xMin = Math.min(...xValues);
    const xMax = Math.max(...xValues);
    const yMin = Math.min(...yValues);
    const yMax = Math.max(...yValues);
    const xCenter = (xMin + xMax) / 2;
    const yCenter = (yMin + yMax) / 2;
    const horizontalScale = 8.2 / Math.max(xMax - xMin, yMax - yMin, 1);
    const verticalScale = 4.7 / Math.max(...altitudeValues, 1);

    const toScenePoint = (x_m: number, y_m: number, relative_altitude_m: number, groundLevel = false) =>
      new THREE.Vector3(
        (x_m - xCenter) * horizontalScale,
        groundLevel ? 0.05 : Math.max(relative_altitude_m, 0) * verticalScale + 0.08,
        (y_m - yCenter) * horizontalScale,
      );

    const topPoints = profile.map((point) => toScenePoint(point.x_m, point.y_m, point.relative_altitude_m ?? 0));
    const groundPoints = profile.map((point) => toScenePoint(point.x_m, point.y_m, point.relative_altitude_m ?? 0, true));
    const waypointPoints = plotWaypoints.map((point) => toScenePoint(point.x_m, point.y_m, point.relative_altitude_m ?? 0));

    const boxHalfX = 4.7;
    const boxHalfZ = 4.35;
    const boxHeight = 4.95;

    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(boxHalfX * 2, boxHalfZ * 2),
      new THREE.MeshBasicMaterial({ color: 0xf4fbf7, side: THREE.DoubleSide }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.set(0, 0, 0);
    group.add(ground);

    const grid = new THREE.GridHelper(boxHalfX * 2, 8, 0xcbddea, 0xddebf2);
    grid.position.set(0, 0.01, -2.6);
    grid.scale.z = (boxHalfZ * 2) / (boxHalfX * 2);
    grid.position.z = 0;
    group.add(grid);

    const boxMaterial = new THREE.LineBasicMaterial({ color: 0xcbd5df, transparent: true, opacity: 0.8 });
    const boxSegments: THREE.Vector3[] = [];
    const corners = [
      new THREE.Vector3(-boxHalfX, 0, -boxHalfZ),
      new THREE.Vector3(boxHalfX, 0, -boxHalfZ),
      new THREE.Vector3(boxHalfX, 0, boxHalfZ),
      new THREE.Vector3(-boxHalfX, 0, boxHalfZ),
      new THREE.Vector3(-boxHalfX, boxHeight, -boxHalfZ),
      new THREE.Vector3(boxHalfX, boxHeight, -boxHalfZ),
      new THREE.Vector3(boxHalfX, boxHeight, boxHalfZ),
      new THREE.Vector3(-boxHalfX, boxHeight, boxHalfZ),
    ];
    [
      [0, 1], [1, 2], [2, 3], [3, 0],
      [4, 5], [5, 6], [6, 7], [7, 4],
      [0, 4], [1, 5], [2, 6], [3, 7],
    ].forEach(([start, end]) => {
      boxSegments.push(corners[start], corners[end]);
    });
    for (let index = 1; index < 4; index += 1) {
      const y = (boxHeight / 4) * index;
      boxSegments.push(new THREE.Vector3(-boxHalfX, y, -boxHalfZ), new THREE.Vector3(boxHalfX, y, -boxHalfZ));
      boxSegments.push(new THREE.Vector3(-boxHalfX, y, -boxHalfZ), new THREE.Vector3(-boxHalfX, y, boxHalfZ));
    }
    addLineSegments(group, boxSegments, boxMaterial);

    const labelX = createLabelSprite("X");
    labelX.position.set(boxHalfX + 0.45, 0.22, boxHalfZ);
    group.add(labelX);
    const labelY = createLabelSprite("Y");
    labelY.position.set(-boxHalfX, 0.22, boxHalfZ + 0.52);
    group.add(labelY);
    const labelZ = createLabelSprite("Z");
    labelZ.position.set(-boxHalfX - 0.35, boxHeight + 0.24, -boxHalfZ);
    group.add(labelZ);

    const ribbonHalfWidth = 0.23;
    const wallVertices: number[] = [];
    const wallIndices: number[] = [];
    const ribbonVertices: number[] = [];
    const ribbonIndices: number[] = [];
    for (let index = 0; index < topPoints.length; index += 1) {
      const previous = topPoints[Math.max(index - 1, 0)];
      const next = topPoints[Math.min(index + 1, topPoints.length - 1)];
      const tangentX = next.x - previous.x;
      const tangentZ = next.z - previous.z;
      const tangentLength = Math.hypot(tangentX, tangentZ);
      const normal = tangentLength > 0.001
        ? new THREE.Vector3(-tangentZ / tangentLength, 0, tangentX / tangentLength).multiplyScalar(ribbonHalfWidth)
        : new THREE.Vector3(ribbonHalfWidth, 0, 0);
      const left = topPoints[index].clone().add(normal);
      const right = topPoints[index].clone().sub(normal);
      ribbonVertices.push(left.x, left.y, left.z, right.x, right.y, right.z);
      wallVertices.push(groundPoints[index].x, groundPoints[index].y, groundPoints[index].z);
      wallVertices.push(topPoints[index].x, topPoints[index].y, topPoints[index].z);
      if (index < topPoints.length - 1) {
        const base = index * 2;
        ribbonIndices.push(base, base + 1, base + 3, base, base + 3, base + 2);
        wallIndices.push(base, base + 1, base + 3, base, base + 3, base + 2);
      }
    }

    const ribbonGeometry = new THREE.BufferGeometry();
    ribbonGeometry.setAttribute("position", new THREE.Float32BufferAttribute(ribbonVertices, 3));
    ribbonGeometry.setIndex(ribbonIndices);
    ribbonGeometry.computeVertexNormals();
    group.add(
      new THREE.Mesh(
        ribbonGeometry,
        new THREE.MeshPhongMaterial({
          color: 0x166534,
          side: THREE.DoubleSide,
          shininess: 86,
        }),
      ),
    );

    const wallGeometry = new THREE.BufferGeometry();
    wallGeometry.setAttribute("position", new THREE.Float32BufferAttribute(wallVertices, 3));
    wallGeometry.setIndex(wallIndices);
    wallGeometry.computeVertexNormals();
    group.add(
      new THREE.Mesh(
        wallGeometry,
        new THREE.MeshPhongMaterial({
          color: 0x22c55e,
          transparent: true,
          opacity: 0.16,
          side: THREE.DoubleSide,
          shininess: 22,
        }),
      ),
    );

    const lineMaterial = new THREE.MeshPhongMaterial({ color: 0x052e16, shininess: 70 });
    const shadowMaterial = new THREE.MeshBasicMaterial({ color: 0x64748b, transparent: true, opacity: 0.38 });
    for (let index = 0; index < topPoints.length - 1; index += 1) {
      addCylinderBetween(group, topPoints[index], topPoints[index + 1], lineMaterial, 0.035);
      addCylinderBetween(group, groundPoints[index], groundPoints[index + 1], shadowMaterial, 0.014);
    }

    const markerGeometry = new THREE.SphereGeometry(0.13, 18, 18);
    const startMaterial = new THREE.MeshPhongMaterial({ color: 0xffffff, emissive: 0x16a34a, emissiveIntensity: 0.18 });
    [0, topPoints.length - 1].forEach((index) => {
      const marker = new THREE.Mesh(markerGeometry, startMaterial);
      marker.position.copy(topPoints[index]);
      group.add(marker);
    });

    if (waypointPoints.length > 0) {
      const waypointMaterial = new THREE.MeshPhongMaterial({ color: 0xf97316, emissive: 0xf97316, emissiveIntensity: 0.18 });
      const waypointLineMaterial = new THREE.LineBasicMaterial({ color: 0xf97316, transparent: true, opacity: 0.72 });
      const waypointStemMaterial = new THREE.MeshBasicMaterial({ color: 0xf97316, transparent: true, opacity: 0.42 });
      addLine(group, waypointPoints, waypointLineMaterial);
      for (let index = 0; index < waypointPoints.length - 1; index += 1) {
        const midpoint = new THREE.Vector3().addVectors(waypointPoints[index], waypointPoints[index + 1]).multiplyScalar(0.5);
        const distance = waypointDistanceMeters(plotWaypoints[index], plotWaypoints[index + 1]);
        const label = createLabelSprite(`約${formatDistanceMeters(distance)}`, "#0f766e", 320, 0.82);
        label.position.set(midpoint.x, midpoint.y + 0.22 + (index % 2) * 0.14, midpoint.z);
        group.add(label);
      }
      waypointPoints.forEach((position, index) => {
        const waypoint = plotWaypoints[index];
        const marker = new THREE.Mesh(new THREE.SphereGeometry(0.14, 18, 18), waypointMaterial);
        marker.position.copy(position);
        group.add(marker);
        addCylinderBetween(group, new THREE.Vector3(position.x, 0.05, position.z), position, waypointStemMaterial, 0.014);
        const label = createLabelSprite(`WP${waypoint.seq} ${formatAltitudeMeters(waypoint.altitude_m)}`, "#c2410c", 384, 0.98);
        label.position.set(position.x, position.y + 0.34 + (index % 2) * 0.16, position.z);
        group.add(label);
      });
    }

    const axisMaterial = new THREE.MeshBasicMaterial({ color: 0x475569 });
    addCylinderBetween(group, new THREE.Vector3(-boxHalfX, 0.04, boxHalfZ), new THREE.Vector3(boxHalfX, 0.04, boxHalfZ), axisMaterial, 0.018);
    addCylinderBetween(group, new THREE.Vector3(-boxHalfX, 0.04, -boxHalfZ), new THREE.Vector3(-boxHalfX, 0.04, boxHalfZ), axisMaterial, 0.018);
    addCylinderBetween(group, new THREE.Vector3(-boxHalfX, 0.04, -boxHalfZ), new THREE.Vector3(-boxHalfX, boxHeight, -boxHalfZ), axisMaterial, 0.018);

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);

    let animationFrame = 0;
    const animate = () => {
      controls.update();
      renderScene();
      animationFrame = window.requestAnimationFrame(animate);
    };
    animate();

    return () => {
      window.cancelAnimationFrame(animationFrame);
      observer.disconnect();
      controls.dispose();
      group.traverse((object) => {
        if (object instanceof THREE.Mesh || object instanceof THREE.LineSegments) {
          object.geometry.dispose();
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          materials.forEach((material) => material.dispose());
        }
        if (object instanceof THREE.Line) {
          object.geometry.dispose();
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          materials.forEach((material) => material.dispose());
        }
        if (object instanceof THREE.Sprite) {
          object.material.map?.dispose();
          object.material.dispose();
        }
      });
      renderer.dispose();
    };
  }, [hasProfile, profile, waypoints]);

  if (!hasProfile) {
    return (
      <div className="flex h-full min-h-72 items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white/70 px-4 text-center text-sm font-semibold text-slate-500">
        高度時系列データがまだありません。ログを再解析すると3D高度グラフを表示できます。
      </div>
    );
  }

  return (
    <div className="relative h-full min-h-72 overflow-hidden rounded-2xl border border-slate-200 bg-slate-50" ref={containerRef}>
      <canvas className="block h-full w-full" ref={canvasRef} />
      <div className="pointer-events-none absolute left-4 top-4 rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-xs font-semibold text-slate-600 shadow-sm">
        3D高度 / waypoint / WP間距離
      </div>
    </div>
  );
}

export function RecordDetailPage() {
  const { recordId } = useParams();
  const [record, setRecord] = useState<FlightRecord | null>(null);
  const [aircraft, setAircraft] = useState<Aircraft[]>([]);
  const [pilots, setPilots] = useState<Pilot[]>([]);
  const [saving, setSaving] = useState(false);
  const [busyAction, setBusyAction] = useState<string>("");
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
  });

  async function load() {
    const [recordRes, aircraftRes, pilotsRes] = await Promise.all([
      api.get<FlightRecord>(`/flight-records/${recordId}/`),
      api.get("/aircraft/"),
      api.get("/pilots/"),
    ]);
    let recordData = recordRes.data;
    if (needsAddressRefresh(recordData)) {
      try {
        const refreshed = await api.post<FlightRecord>(`/flight-records/${recordId}/refresh-addresses/`);
        recordData = refreshed.data;
      } catch {
        recordData = recordRes.data;
      }
    }
    setRecord(recordData);
    setAircraft(aircraftRes.data.results);
    setPilots(pilotsRes.data.results);
    const purpose = parsePurpose(recordData.purpose);
    form.reset({
      aircraft: recordData.aircraft,
      pilot: recordData.pilot,
      purpose: purpose.purpose,
      purpose_other: purpose.purpose_other,
      special_flight_types: parseFlightMethods(recordData.special_flight_types),
      route_summary: recordData.route_summary,
      official_weather: recordData.official_weather || "晴れ",
      official_temperature_c: recordData.official_temperature_c ?? 20,
      official_wind_speed_mps: recordData.official_wind_speed_mps ?? 1,
      safety_notes: recordData.safety_notes,
      article_notes: recordData.article_notes,
      pilot_signature: recordData.pilot_signature,
    });
  }

  useEffect(() => {
    void load();
  }, [recordId]);

  async function persistForm(values: RecordFormValues) {
    await api.put(`/flight-records/${recordId}/`, toFlightRecordPayload(values));
  }

  async function save(values: RecordFormValues) {
    setSaving(true);
    try {
      await persistForm(values);
      await load();
    } finally {
      setSaving(false);
    }
  }

  async function finalizeRecord() {
    setBusyAction("finalize");
    try {
      const isValid = await form.trigger();
      if (!isValid) {
        return;
      }
      await persistForm(form.getValues());
      await api.post(`/flight-records/${recordId}/finalize/`);
      await load();
    } finally {
      setBusyAction("");
    }
  }

  async function generatePdf() {
    setBusyAction("pdf");
    try {
      const isValid = await form.trigger();
      if (!isValid) {
        return;
      }
      await persistForm(form.getValues());
      await api.post(`/flight-records/${recordId}/generate-pdf/`);
      await load();
    } finally {
      setBusyAction("");
    }
  }

  const altitudeProfile = useMemo(
    () => (
      record?.analysis?.summary_json?.altitude_profile?.filter(
        (point) => Number.isFinite(point.time_s) && Number.isFinite(point.altitude_m) && Number.isFinite(point.x_m) && Number.isFinite(point.y_m),
      ) ?? []
    ),
    [record?.analysis?.summary_json?.altitude_profile],
  );
  const waypoints = useMemo(
    () => (
      record?.analysis?.summary_json?.waypoints?.filter(
        (point) => Number.isFinite(point.x_m) && Number.isFinite(point.y_m) && Number.isFinite(point.relative_altitude_m),
      ) ?? []
    ),
    [record?.analysis?.summary_json?.waypoints],
  );

  if (!record) {
    return <Panel title="読み込み中" eyebrow="Log" />;
  }

  const selectedPurposes = form.watch("purpose") ?? [];
  const selectedAircraftId = form.watch("aircraft");
  const selectedPilotId = form.watch("pilot");
  const selectedAircraft = aircraft.find((item) => item.id === Number(selectedAircraftId)) ?? null;
  const selectedPilot = pilots.find((item) => item.id === Number(selectedPilotId)) ?? null;
  const remoteIdDisplay = selectedAircraft?.remote_id || "";
  const aircraftRegistrationNumber = selectedAircraft?.registration_number || "";
  const selectedFlightMethods = form.watch("special_flight_types") ?? [];
  const purposeOther = form.watch("purpose_other")?.trim();
  const purposeDisplay = [
    ...selectedPurposes.filter((item) => item !== "その他"),
    ...(selectedPurposes.includes("その他") && purposeOther ? [`その他: ${purposeOther}`] : []),
  ].join("、") || "-";
  const flightMethodsDisplay = selectedFlightMethods.join("、") || "-";
  const routeSummary = form.watch("route_summary") || "-";
  const safetyNotes = form.watch("safety_notes") || "-";
  const articleNotes = form.watch("article_notes") || "-";
  const pilotSignature = form.watch("pilot_signature") || "-";
  const totalFlightSeconds = selectedAircraft?.current_total_flight_seconds ?? record.duration_seconds ?? 0;
  const mapReady = record.takeoff_lat !== null && record.takeoff_lng !== null && record.landing_lat !== null && record.landing_lng !== null;

  return (
    <div className="space-y-6">
      <Panel
        title={`飛行記録 #${record.id}`}
        eyebrow="飛行記録"
        actions={
          <div className="flex flex-wrap gap-2">
            <StatusBadge value={record.status} />
            {record.diagnostic_grade ? <StatusBadge value={record.diagnostic_grade} /> : null}
          </div>
        }
      >
        <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <form className="space-y-4" onSubmit={form.handleSubmit(save)}>
            <div>
              <label className="label">機体</label>
              <select className="input" {...form.register("aircraft")}>
                <option value="">機体を選択</option>
                {aircraft.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label">操縦者</label>
              <select className="input" {...form.register("pilot")}>
                <option value="">操縦者を選択</option>
                {pilots.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </div>
            <fieldset>
              <legend className="label">飛行の目的</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {PURPOSE_OPTIONS.map((option) => (
                  <label key={option} className="flex min-h-12 cursor-pointer items-center gap-3 rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-sky-400">
                    <input className="h-4 w-4 rounded border-slate-300 accent-sky-700" type="checkbox" value={option} {...form.register("purpose")} />
                    <span>{option}</span>
                  </label>
                ))}
              </div>
              {selectedPurposes.includes("その他") ? (
                <div className="mt-3">
                  <label className="label">その他の内容</label>
                  <input className="input" {...form.register("purpose_other")} />
                  {form.formState.errors.purpose_other ? (
                    <p className="mt-2 text-sm text-rose-600">{form.formState.errors.purpose_other.message}</p>
                  ) : null}
                </div>
              ) : null}
            </fieldset>
            <fieldset>
              <legend className="label">飛行方法</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {FLIGHT_METHOD_OPTIONS.map((option) => (
                  <label key={option} className="flex min-h-12 cursor-pointer items-center gap-3 rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-sky-400">
                    <input className="h-4 w-4 rounded border-slate-300 accent-sky-700" type="checkbox" value={option} {...form.register("special_flight_types")} />
                    <span>{option}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <div><label className="label">飛行経路概要</label><textarea className="input min-h-24" {...form.register("route_summary")} /></div>
            <div className="grid gap-4 md:grid-cols-3">
              <div><label className="label">正式天気</label><input className="input" {...form.register("official_weather")} /></div>
              <div><label className="label">正式気温 ℃</label><input className="input" type="number" step="0.1" {...form.register("official_temperature_c")} /></div>
              <div><label className="label">正式風速 m/s</label><input className="input" type="number" step="0.1" {...form.register("official_wind_speed_mps")} /></div>
            </div>
            <div><label className="label">安全確認事項</label><textarea className="input min-h-24" {...form.register("safety_notes")} /></div>
            <div><label className="label">飛行させた者の署名</label><input className="input" {...form.register("pilot_signature")} /></div>
            <div><label className="label">備考</label><textarea className="input min-h-24" {...form.register("article_notes")} /></div>
            <div className="flex flex-wrap gap-3">
              <button className="btn-primary" disabled={saving} type="submit">{saving ? "保存中..." : "下書き保存"}</button>
              <button className="btn-secondary" disabled={busyAction === "finalize"} onClick={() => void finalizeRecord()} type="button">
                {busyAction === "finalize" ? "確定中..." : "確定"}
              </button>
              <button className="btn-secondary" disabled={busyAction === "pdf"} onClick={() => void generatePdf()} type="button">
                {busyAction === "pdf" ? "生成中..." : "PDF生成"}
              </button>
              {record.generated_assets[0] ? (
                <a className="btn-secondary" href={`/api/flight-records/${record.id}/download-pdf/`}>
                  PDFダウンロード
                </a>
              ) : null}
            </div>
          </form>

          <div className="space-y-4">
            <div className="panel-muted p-4">
              <p className="text-sm font-semibold text-slate-500">記録項目</p>
              <p className="mt-1 text-lg font-bold text-ink">飛行記録 ①〜⑬</p>
              <div className="mt-4 grid gap-3 text-sm">
                <div className={recordItemClass}><p className={recordLabelClass}>① 無人航空機のリモートID</p><p className={recordValueClass}>{remoteIdDisplay}</p></div>
                <div className={recordItemClass}><p className={recordLabelClass}>機体登録番号</p><p className={recordValueClass}>{aircraftRegistrationNumber}</p></div>
                <div className={recordItemClass}><p className={recordLabelClass}>② 年月日</p><p className={recordValueClass}>{formatDate(record.flight_date)}</p></div>
                <div className={recordItemClass}><p className={recordLabelClass}>③ 飛行させた者の氏名</p><p className={recordValueClass}>{selectedPilot ? `${selectedPilot.name}${selectedPilot.license_number ? ` / ${selectedPilot.license_number}` : ""}` : "-"}</p></div>
                <div className={recordItemClass}>
                  <p className={recordLabelClass}>④ 飛行概要</p>
                  <div className={`${recordValueClass} space-y-1`}>
                    <p>目的: {purposeDisplay}</p>
                    <p>飛行方法: {flightMethodsDisplay}</p>
                    <p>経路概要: {routeSummary}</p>
                  </div>
                </div>
                <div className={recordItemClass}><p className={recordLabelClass}>⑤ 離陸場所</p><p className={recordValueClass}>{formatPlace(record.takeoff_address, record.takeoff_lat, record.takeoff_lng)}</p></div>
                <div className={recordItemClass}><p className={recordLabelClass}>⑥ 着陸場所</p><p className={recordValueClass}>{formatPlace(record.landing_address, record.landing_lat, record.landing_lng)}</p></div>
                <div className={recordItemClass}><p className={recordLabelClass}>⑦ 離陸時刻</p><p className={recordValueClass}>{formatDateTime(record.takeoff_at_utc)}</p></div>
                <div className={recordItemClass}><p className={recordLabelClass}>⑧ 着陸時刻</p><p className={recordValueClass}>{formatDateTime(record.landing_at_utc)}</p></div>
                <div className={recordItemClass}><p className={recordLabelClass}>⑨ 飛行時間</p><p className={recordValueClass}>{formatDurationMinutes(record.duration_seconds)}</p></div>
                <div className={recordItemClass}><p className={recordLabelClass}>⑩ 総飛行時間</p><p className={recordValueClass}>{formatDurationHours(totalFlightSeconds)}</p></div>
                <div className={recordItemClass}><p className={recordLabelClass}>⑪ 飛行させた者の署名</p><p className={recordValueClass}>{pilotSignature}</p></div>
                <div className={recordItemClass}><p className={recordLabelClass}>⑫ 飛行の安全に影響のあった事項</p><p className={recordValueClass}>{safetyNotes}</p></div>
                <div className={recordItemClass}><p className={recordLabelClass}>⑬ 記事</p><p className={recordValueClass}>{articleNotes}</p></div>
              </div>
            </div>
            <div className="panel-muted p-4">
              <p className="text-sm font-semibold text-slate-500">解析情報</p>
              <div className="mt-3 space-y-2 text-sm text-slate-700">
                <p>離陸場所: {formatPlace(record.takeoff_address, record.takeoff_lat, record.takeoff_lng)}</p>
                <p>着陸場所: {formatPlace(record.landing_address, record.landing_lat, record.landing_lng)}</p>
                <p>飛行時間: {formatDurationMinutes(record.duration_seconds)}</p>
                <p>参考気象: {record.reference_weather || "参考値なし"}</p>
              </div>
            </div>
            <div className="panel-muted p-4">
              <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-500">高度プロファイル</p>
                  <p className="mt-1 text-lg font-bold text-ink">3D高度変化</p>
                </div>
                <div className="grid grid-cols-4 gap-2 text-right text-xs text-slate-500">
                  <div>
                    <p className="font-semibold text-slate-400">最大高度</p>
                    <p className="text-sm font-bold text-slate-700">{formatNumber(record.analysis?.max_altitude_m)} m</p>
                  </div>
                  <div>
                    <p className="font-semibold text-slate-400">最大速度</p>
                    <p className="text-sm font-bold text-slate-700">{formatNumber(record.analysis?.max_speed_mps)} m/s</p>
                  </div>
                  <div>
                    <p className="font-semibold text-slate-400">飛行時間</p>
                    <p className="text-sm font-bold text-slate-700">{record.duration_seconds ?? 0} 秒</p>
                  </div>
                  <div>
                    <p className="font-semibold text-slate-400">WP</p>
                    <p className="text-sm font-bold text-slate-700">{waypoints.length}</p>
                  </div>
                </div>
              </div>
              <div className="h-96">
                <AltitudeProfile3D
                  profile={altitudeProfile}
                  waypoints={waypoints}
                />
              </div>
            </div>
            <div className="panel-muted overflow-hidden p-0">
              <div className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-500">地図</div>
              {mapReady ? (
                <MapContainer
                  center={[record.takeoff_lat!, record.takeoff_lng!]}
                  style={{ height: "320px", width: "100%" }}
                  zoom={14}
                >
                  <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />
                  <Marker position={[record.takeoff_lat!, record.takeoff_lng!]}><Popup>離陸</Popup></Marker>
                  <Marker position={[record.landing_lat!, record.landing_lng!]}><Popup>着陸</Popup></Marker>
                  <Polyline positions={[[record.takeoff_lat!, record.takeoff_lng!], [record.landing_lat!, record.landing_lng!]]} />
                </MapContainer>
              ) : (
                <div className="p-6 text-sm text-slate-600">地図に表示できる座標がまだありません。</div>
              )}
            </div>
          </div>
        </div>
      </Panel>
    </div>
  );
}
