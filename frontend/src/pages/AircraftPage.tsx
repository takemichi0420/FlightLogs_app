import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Panel } from "../components/Panel";
import { api } from "../lib/api";
import { Aircraft, Paginated } from "../lib/types";

const schema = z.object({
  name: z.string().min(1),
  model: z.string().min(1),
  serial_number: z.string().min(1),
  registration_number: z.string().optional(),
  is_certified: z.boolean().default(false),
  remote_id: z.string().optional(),
  initial_total_flight_seconds: z.coerce.number().min(0),
}).superRefine((values, context) => {
  if (values.is_certified && !values.remote_id?.trim()) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      message: "機体認証済みの場合はリモートIDを入力してください",
      path: ["remote_id"],
    });
  }
});

export function AircraftPage() {
  const [items, setItems] = useState<Aircraft[]>([]);
  const { register, handleSubmit, reset, watch, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { initial_total_flight_seconds: 0, is_certified: false },
  });
  const isCertified = watch("is_certified");

  async function load() {
    const response = await api.get<Paginated<Aircraft>>("/aircraft/");
    setItems(response.data.results);
  }

  useEffect(() => {
    void load();
  }, []);

  async function onSubmit(values: z.infer<typeof schema>) {
    await api.post("/aircraft/", {
      ...values,
      remote_id: values.is_certified ? values.remote_id?.trim() ?? "" : "",
    });
    reset({
      name: "",
      model: "",
      serial_number: "",
      registration_number: "",
      is_certified: false,
      remote_id: "",
      initial_total_flight_seconds: 0,
    });
    await load();
  }

  async function remove(id: number) {
    await api.delete(`/aircraft/${id}/`);
    await load();
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <Panel title="機体登録" eyebrow="Entry">
        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
          <div><label className="label">機体名</label><input className="input" {...register("name")} /></div>
          <div><label className="label">機体Type</label><input className="input" {...register("model")} /></div>
          <div><label className="label">製造番号</label><input className="input" {...register("serial_number")} /></div>
          <div><label className="label">機体登録番号</label><input className="input" {...register("registration_number")} /></div>
          <div>
            <label className="label">機体認証</label>
            <label className="flex min-h-12 cursor-pointer items-center gap-3 rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-sky-400">
              <input className="h-4 w-4 rounded border-slate-300 accent-sky-700" type="checkbox" {...register("is_certified")} />
              <span>機体認証を受けている</span>
            </label>
          </div>
          {isCertified ? (
            <div>
              <label className="label">リモートID</label>
              <input className="input" {...register("remote_id")} />
              {errors.remote_id ? <p className="mt-2 text-sm text-rose-600">{errors.remote_id.message}</p> : null}
            </div>
          ) : null}
          <div><label className="label">初期総飛行時間（h）</label><input className="input" type="number" {...register("initial_total_flight_seconds")} /></div>
          <button className="btn-primary w-full" disabled={isSubmitting} type="submit">{isSubmitting ? "保存中..." : "機体を保存"}</button>
        </form>
      </Panel>
      <Panel title="機体一覧" eyebrow="List">
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="panel-muted flex flex-wrap items-center justify-between gap-4 p-4">
              <div>
                <p className="font-semibold text-ink">{item.name}</p>
                <p className="text-sm text-slate-600">{item.model} / {item.serial_number}</p>
                {item.registration_number ? <p className="text-sm text-slate-600">機体登録番号：{item.registration_number}</p> : null}
                <p className="text-sm text-slate-600">機体認証：{item.is_certified ? "あり" : "なし"}</p>
                {item.is_certified ? <p className="text-sm text-slate-600">リモートID：{item.remote_id || "未入力"}</p> : null}
              </div>
              <div className="flex items-center gap-3">
                <p className="text-sm text-slate-600">{item.current_total_flight_seconds} 秒</p>
                <button className="btn-secondary" onClick={() => void remove(item.id)}>削除</button>
              </div>
            </div>
          ))}
          {items.length === 0 ? <p className="text-sm text-slate-600">機体がまだ登録されていません。</p> : null}
        </div>
      </Panel>
    </div>
  );
}
