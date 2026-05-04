import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Panel } from "../components/Panel";
import { StatusBadge } from "../components/StatusBadge";
import { api } from "../lib/api";
import { Aircraft, FlightRecord, Paginated, Pilot } from "../lib/types";

export function DashboardPage() {
  const [aircraft, setAircraft] = useState<Aircraft[]>([]);
  const [pilots, setPilots] = useState<Pilot[]>([]);
  const [records, setRecords] = useState<FlightRecord[]>([]);

  useEffect(() => {
    void Promise.all([
      api.get<Paginated<Aircraft>>("/aircraft/"),
      api.get<Paginated<Pilot>>("/pilots/"),
      api.get<Paginated<FlightRecord>>("/flight-records/"),
    ]).then(([aircraftRes, pilotsRes, recordsRes]) => {
      setAircraft(aircraftRes.data.results);
      setPilots(pilotsRes.data.results);
      setRecords(recordsRes.data.results);
    });
  }, []);

  return (
    <>
      <section className="grid gap-4 md:grid-cols-3">
        {[
          { label: "機体", value: aircraft.length.toString(), caption: "登録済み機体" },
          { label: "操縦者", value: pilots.length.toString(), caption: "登録済み操縦者" },
          { label: "飛行記録", value: records.length.toString(), caption: "飛行記録" },
        ].map((item) => (
          <div key={item.label} className="panel overflow-hidden p-6">
            <div className="h-2 w-24 rounded-full bg-gradient-to-r from-tide to-sea" />
            <p className="mt-5 text-sm font-semibold text-slate-500">{item.label}</p>
            <p className="mt-3 text-4xl font-semibold text-ink">{item.value}</p>
            <p className="mt-2 text-sm text-slate-600">{item.caption}</p>
          </div>
        ))}
      </section>

      <Panel title="最近の飛行記録" eyebrow="概要">
        <div className="space-y-3">
          {records.slice(0, 5).map((record) => (
            <Link key={record.id} to={`/records/${record.id}`} className="panel-muted flex flex-wrap items-center justify-between gap-3 p-4 transition hover:border-sky-300">
              <div>
                <p className="font-semibold text-ink">{record.source_original_name}</p>
                <p className="text-sm text-slate-600">{record.takeoff_address || "解析待ち"}</p>
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge value={record.status} />
                <StatusBadge value={record.diagnostic_grade || "uploaded"} />
              </div>
            </Link>
          ))}
          {records.length === 0 ? <p className="text-sm text-slate-600">まだ飛行記録がありません。</p> : null}
        </div>
      </Panel>
    </>
  );
}
