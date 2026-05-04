import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Panel } from "../components/Panel";
import { StatusBadge } from "../components/StatusBadge";
import { api } from "../lib/api";
import { Aircraft, AnalysisJob, FlightRecord, MavlinkLogEntry, Paginated, Pilot } from "../lib/types";

function formatBytes(value: number) {
  if (value >= 1024 * 1024) {
    return `${(value / 1024 / 1024).toFixed(1)} MB`;
  }
  if (value >= 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${value} bytes`;
}

function formatLogTime(value: number) {
  if (!value) {
    return "日時不明";
  }
  return new Date(value * 1000).toLocaleString("ja-JP");
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error && typeof error === "object" && "response" in error) {
    const response = (error as { response?: { data?: Record<string, unknown> } }).response;
    const data = response?.data;
    const connection = data?.connection;
    if (Array.isArray(connection) && connection[0]) {
      return String(connection[0]);
    }
    if (typeof connection === "string") {
      return connection;
    }
    if (typeof data?.detail === "string") {
      return data.detail;
    }
  }
  return fallback;
}

export function RecordsPage() {
  const [records, setRecords] = useState<FlightRecord[]>([]);
  const [aircraft, setAircraft] = useState<Aircraft[]>([]);
  const [pilots, setPilots] = useState<Pilot[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [aircraftId, setAircraftId] = useState("");
  const [pilotId, setPilotId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [pollingJobId, setPollingJobId] = useState<string | null>(null);
  const [mavlinkConnection, setMavlinkConnection] = useState("udp:127.0.0.1:14550");
  const [mavlinkBaud, setMavlinkBaud] = useState("115200");
  const [mavlinkAircraftId, setMavlinkAircraftId] = useState("");
  const [mavlinkPilotId, setMavlinkPilotId] = useState("");
  const [mavlinkLogs, setMavlinkLogs] = useState<MavlinkLogEntry[]>([]);
  const [mavlinkLogId, setMavlinkLogId] = useState("");
  const [mavlinkLoading, setMavlinkLoading] = useState(false);
  const [mavlinkImporting, setMavlinkImporting] = useState(false);
  const [mavlinkMessage, setMavlinkMessage] = useState("");
  const [mavlinkError, setMavlinkError] = useState("");

  async function load() {
    const [recordsRes, aircraftRes, pilotsRes] = await Promise.all([
      api.get<Paginated<FlightRecord>>("/flight-records/"),
      api.get<Paginated<Aircraft>>("/aircraft/"),
      api.get<Paginated<Pilot>>("/pilots/"),
    ]);
    setRecords(recordsRes.data.results);
    setAircraft(aircraftRes.data.results);
    setPilots(pilotsRes.data.results);
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (!pollingJobId) {
      return;
    }

    const timer = window.setInterval(() => {
      void api.get<AnalysisJob>(`/jobs/${pollingJobId}/`).then(async (response) => {
        if (response.data.status === "succeeded" || response.data.status === "failed") {
          window.clearInterval(timer);
          setPollingJobId(null);
          await load();
        }
      });
    }, 1500);

    return () => window.clearInterval(timer);
  }, [pollingJobId]);

  async function submitUpload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      return;
    }

    setSubmitting(true);
    const form = new FormData();
    form.append("file", file);
    if (aircraftId) form.append("aircraft_id", aircraftId);
    if (pilotId) form.append("pilot_id", pilotId);

    try {
      const response = await api.post<AnalysisJob>("/uploads/logs/", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setPollingJobId(response.data.id);
      setFile(null);
      setAircraftId("");
      setPilotId("");
      await load();
    } finally {
      setSubmitting(false);
    }
  }

  async function fetchMavlinkLogs() {
    setMavlinkLoading(true);
    setMavlinkError("");
    setMavlinkMessage("");
    try {
      const response = await api.post<{ logs: MavlinkLogEntry[] }>("/mavlink/logs/", {
        connection: mavlinkConnection,
        baud: Number(mavlinkBaud) || 115200,
      });
      setMavlinkLogs(response.data.logs);
      setMavlinkLogId(response.data.logs[0]?.id.toString() ?? "");
      setMavlinkMessage(response.data.logs.length ? "ログ一覧を取得しました。" : "取得可能なログがありません。");
    } catch (error) {
      setMavlinkLogs([]);
      setMavlinkLogId("");
      setMavlinkError(getErrorMessage(error, "MAVLinkログ一覧の取得に失敗しました。"));
    } finally {
      setMavlinkLoading(false);
    }
  }

  async function importMavlinkLog() {
    setMavlinkImporting(true);
    setMavlinkError("");
    setMavlinkMessage("");
    try {
      const payload: Record<string, string | number> = {
        connection: mavlinkConnection,
        baud: Number(mavlinkBaud) || 115200,
      };
      if (mavlinkLogId) payload.log_id = Number(mavlinkLogId);
      if (mavlinkAircraftId) payload.aircraft_id = Number(mavlinkAircraftId);
      if (mavlinkPilotId) payload.pilot_id = Number(mavlinkPilotId);

      const response = await api.post<AnalysisJob>("/mavlink/import-log/", payload);
      setPollingJobId(response.data.id);
      setMavlinkMessage("MAVLinkログを取り込み、解析ジョブを開始しました。");
      await load();
    } catch (error) {
      setMavlinkError(getErrorMessage(error, "MAVLinkログの取り込みに失敗しました。"));
    } finally {
      setMavlinkImporting(false);
    }
  }

  return (
    <div className="space-y-6">
      <Panel title="フライトログアップロード" eyebrow="取込">
        <form className="grid gap-4 md:grid-cols-2" onSubmit={submitUpload}>
          <div className="md:col-span-2">
            <label className="label">ログファイル（.bin / .log）</label>
            <label className="flex min-h-40 cursor-pointer items-center justify-center rounded-[28px] border border-dashed border-sky-300 bg-sky-50/70 p-6 text-center text-sm text-slate-600 transition hover:border-sky-500 hover:bg-sky-100/80">
              <input className="hidden" type="file" accept=".bin,.log" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
              {file ? file.name : "ログをドロップまたは選択"}
            </label>
          </div>
          <div>
            <label className="label">機体</label>
            <select className="input" value={aircraftId} onChange={(event) => setAircraftId(event.target.value)}>
              <option value="">機体を選択</option>
              {aircraft.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">操縦者</label>
            <select className="input" value={pilotId} onChange={(event) => setPilotId(event.target.value)}>
              <option value="">操縦者を選択</option>
              {pilots.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </div>
          <div className="md:col-span-2">
            <button className="btn-primary w-full" disabled={!file || submitting} type="submit">
              {submitting ? "アップロード中..." : "アップロードして解析"}
            </button>
          </div>
        </form>
      </Panel>

      <Panel title="MAVLinkから取り込み" eyebrow="自動取得">
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="label">接続先</label>
            <input className="input" value={mavlinkConnection} onChange={(event) => setMavlinkConnection(event.target.value)} />
          </div>
          <div>
            <label className="label">ボーレート</label>
            <input className="input" type="number" value={mavlinkBaud} onChange={(event) => setMavlinkBaud(event.target.value)} />
          </div>
          <div>
            <label className="label">機体</label>
            <select className="input" value={mavlinkAircraftId} onChange={(event) => setMavlinkAircraftId(event.target.value)}>
              <option value="">機体を選択</option>
              {aircraft.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">操縦者</label>
            <select className="input" value={mavlinkPilotId} onChange={(event) => setMavlinkPilotId(event.target.value)}>
              <option value="">操縦者を選択</option>
              {pilots.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </div>
          <div className="md:col-span-2">
            <button className="btn-secondary w-full" disabled={!mavlinkConnection || mavlinkLoading || mavlinkImporting} onClick={() => void fetchMavlinkLogs()} type="button">
              {mavlinkLoading ? "ログ一覧取得中..." : "ログ一覧を取得"}
            </button>
          </div>
          {mavlinkLogs.length ? (
            <div className="md:col-span-2">
              <label className="label">取り込むログ</label>
              <select className="input" value={mavlinkLogId} onChange={(event) => setMavlinkLogId(event.target.value)}>
                {mavlinkLogs.map((item) => (
                  <option key={item.id} value={item.id}>
                    ID {item.id} / {formatBytes(item.size)} / {formatLogTime(item.time_utc)}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          <div className="md:col-span-2">
            <button className="btn-primary w-full" disabled={!mavlinkConnection || mavlinkLoading || mavlinkImporting} onClick={() => void importMavlinkLog()} type="button">
              {mavlinkImporting ? "取り込み中..." : mavlinkLogId ? "選択ログを取り込んで解析" : "最新ログを取り込んで解析"}
            </button>
          </div>
          {mavlinkMessage ? <p className="text-sm text-slate-600 md:col-span-2">{mavlinkMessage}</p> : null}
          {mavlinkError ? <p className="text-sm text-rose-600 md:col-span-2">{mavlinkError}</p> : null}
        </div>
      </Panel>

      <Panel title="飛行記録一覧" eyebrow="一覧">
        <div className="space-y-3">
          {records.map((record) => (
            <Link key={record.id} to={`/records/${record.id}`} className="panel-muted flex flex-wrap items-center justify-between gap-4 p-4 transition hover:border-sky-300">
              <div>
                <p className="font-semibold text-ink">{record.source_original_name}</p>
                <p className="text-sm text-slate-600">{record.takeoff_address || "解析待ち"}</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge value={record.status} />
                {record.diagnostic_grade ? <StatusBadge value={record.diagnostic_grade} /> : null}
              </div>
            </Link>
          ))}
          {records.length === 0 ? <p className="text-sm text-slate-600">ログをアップロードするとここに記録が出ます。</p> : null}
        </div>
      </Panel>
    </div>
  );
}
