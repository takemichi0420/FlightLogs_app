import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Panel } from "../components/Panel";
import { api } from "../lib/api";
import { Paginated, Pilot } from "../lib/types";

const schema = z.object({
  name: z.string().min(1),
  license_number: z.string().optional(),
  organization: z.string().optional(),
});

export function PilotsPage() {
  const [items, setItems] = useState<Pilot[]>([]);
  const { register, handleSubmit, reset, formState: { isSubmitting } } = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
  });

  async function load() {
    const response = await api.get<Paginated<Pilot>>("/pilots/");
    setItems(response.data.results);
  }

  useEffect(() => {
    void load();
  }, []);

  async function onSubmit(values: z.infer<typeof schema>) {
    await api.post("/pilots/", values);
    reset({ name: "", license_number: "", organization: "" });
    await load();
  }

  async function remove(id: number) {
    await api.delete(`/pilots/${id}/`);
    await load();
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <Panel title="操縦者登録" eyebrow="Master">
        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
          <div><label className="label">氏名</label><input className="input" {...register("name")} /></div>
          <div><label className="label">技能証明番号</label><input className="input" {...register("license_number")} /></div>
          <div><label className="label">所属</label><input className="input" {...register("organization")} /></div>
          <button className="btn-primary w-full" disabled={isSubmitting} type="submit">{isSubmitting ? "保存中..." : "操縦者を保存"}</button>
        </form>
      </Panel>
      <Panel title="操縦者一覧" eyebrow="List">
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="panel-muted flex flex-wrap items-center justify-between gap-4 p-4">
              <div>
                <p className="font-semibold text-ink">{item.name}</p>
                <p className="text-sm text-slate-600">{item.license_number || "証明番号未入力"} / {item.organization || "所属未入力"}</p>
              </div>
              <button className="btn-secondary" onClick={() => void remove(item.id)}>削除</button>
            </div>
          ))}
          {items.length === 0 ? <p className="text-sm text-slate-600">操縦者がまだ登録されていません。</p> : null}
        </div>
      </Panel>
    </div>
  );
}
