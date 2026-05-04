import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useParams } from "react-router-dom";
import { z } from "zod";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MapContainer, Marker, Polyline, Popup, TileLayer } from "react-leaflet";
import { Panel } from "../components/Panel";
import { StatusBadge } from "../components/StatusBadge";
import { api } from "../lib/api";
import { Aircraft, FlightRecord, Pilot } from "../lib/types";

const schema = z.object({
  aircraft: z.coerce.number().nullable(),
  pilot: z.coerce.number().nullable(),
  purpose: z.string().default(""),
  special_flight_types: z.string().default(""),
  route_summary: z.string().default(""),
  official_weather: z.string().min(1),
  official_temperature_c: z.coerce.number(),
  official_wind_speed_mps: z.coerce.number(),
  safety_notes: z.string().default(""),
  article_notes: z.string().default(""),
});

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
    setRecord(recordRes.data);
    setAircraft(aircraftRes.data.results);
    setPilots(pilotsRes.data.results);
    form.reset({
      aircraft: recordRes.data.aircraft,
      pilot: recordRes.data.pilot,
      purpose: recordRes.data.purpose,
      special_flight_types: recordRes.data.special_flight_types,
      route_summary: recordRes.data.route_summary,
      official_weather: recordRes.data.official_weather || "晴れ",
      official_temperature_c: recordRes.data.official_temperature_c ?? 20,
      official_wind_speed_mps: recordRes.data.official_wind_speed_mps ?? 1,
      safety_notes: recordRes.data.safety_notes,
      article_notes: recordRes.data.article_notes,
    });
  }

  useEffect(() => {
    void load();
  }, [recordId]);

  async function save(values: z.infer<typeof schema>) {
    setSaving(true);
    try {
      await api.put(`/flight-records/${recordId}/`, values);
      await load();
    } finally {
      setSaving(false);
    }
  }

  async function finalizeRecord() {
    setBusyAction("finalize");
    try {
      await api.post(`/flight-records/${recordId}/finalize/`);
      await load();
    } finally {
      setBusyAction("");
    }
  }

  async function generatePdf() {
    setBusyAction("pdf");
    try {
      await api.post(`/flight-records/${recordId}/generate-pdf/`);
      await load();
    } finally {
      setBusyAction("");
    }
  }

  if (!record) {
    return <Panel title="読み込み中" eyebrow="Log" />;
  }

  const metrics = [
    { name: "高度", value: record.analysis?.max_altitude_m ?? 0 },
    { name: "速度", value: record.analysis?.max_speed_mps ?? 0 },
    { name: "距離", value: record.analysis?.max_distance_m ?? 0 },
  ];

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
            <div><label className="label">飛行目的</label><textarea className="input min-h-28" {...form.register("purpose")} /></div>
            <div><label className="label">特定飛行の種類</label><textarea className="input min-h-24" {...form.register("special_flight_types")} /></div>
            <div><label className="label">飛行経路概要</label><textarea className="input min-h-24" {...form.register("route_summary")} /></div>
            <div className="grid gap-4 md:grid-cols-3">
              <div><label className="label">正式天気</label><input className="input" {...form.register("official_weather")} /></div>
              <div><label className="label">正式気温 ℃</label><input className="input" type="number" step="0.1" {...form.register("official_temperature_c")} /></div>
              <div><label className="label">正式風速 m/s</label><input className="input" type="number" step="0.1" {...form.register("official_wind_speed_mps")} /></div>
            </div>
            <div><label className="label">安全確認事項</label><textarea className="input min-h-24" {...form.register("safety_notes")} /></div>
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
              <p className="text-sm font-semibold text-slate-500">解析情報</p>
              <div className="mt-3 space-y-2 text-sm text-slate-700">
                <p>離陸場所: {record.takeoff_address || "解析待ち"}</p>
                <p>着陸場所: {record.landing_address || "解析待ち"}</p>
                <p>飛行時間: {record.duration_seconds ?? 0} 秒</p>
                <p>参考気象: {record.reference_weather || "参考値なし"}</p>
              </div>
            </div>
            <div className="panel-muted h-80 p-4">
              <p className="mb-3 text-sm font-semibold text-slate-500">指標</p>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={metrics}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#d6e2ea" />
                  <XAxis dataKey="name" stroke="#587080" />
                  <YAxis stroke="#587080" />
                  <Tooltip />
                  <Line type="monotone" dataKey="value" stroke="#0f8ec7" strokeWidth={3} />
                </LineChart>
              </ResponsiveContainer>
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
