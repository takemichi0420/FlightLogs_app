import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Panel } from "../components/Panel";
import { api } from "../lib/api";
import { Paginated, Pilot } from "../lib/types";

const schema = z.object({
  name: z.string().trim().min(1, "氏名を入力してください"),
  license_number: z.string().trim().optional().default(""),
  organization: z.string().trim().optional().default(""),
});

function getErrorMessage(error: unknown, fallback: string) {
  if (error && typeof error === "object" && "response" in error) {
    const response = (error as { response?: { data?: Record<string, unknown> } }).response;
    const data = response?.data;
    if (typeof data?.detail === "string") {
      return data.detail;
    }
    if (typeof data?.message === "string") {
      return data.message;
    }
    for (const value of Object.values(data ?? {})) {
      if (Array.isArray(value) && value[0]) {
        return String(value[0]);
      }
      if (typeof value === "string") {
        return value;
      }
    }
  }
  return fallback;
}

export function PilotsPage() {
  const [items, setItems] = useState<Pilot[]>([]);
  const [message, setMessage] = useState("");
  const [submitError, setSubmitError] = useState("");
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", license_number: "", organization: "" },
  });

  async function load() {
    try {
      const response = await api.get<Paginated<Pilot>>("/pilots/");
      setItems(response.data.results);
    } catch (error) {
      setSubmitError(getErrorMessage(error, "操縦者一覧を取得できませんでした。"));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function onSubmit(values: z.infer<typeof schema>) {
    setMessage("");
    setSubmitError("");
    try {
      await api.post("/pilots/", values);
      reset({ name: "", license_number: "", organization: "" });
      await load();
      setMessage("操縦者を登録しました。");
    } catch (error) {
      setSubmitError(getErrorMessage(error, "操縦者を登録できませんでした。"));
    }
  }

  async function remove(id: number) {
    setMessage("");
    setSubmitError("");
    try {
      await api.delete(`/pilots/${id}/`);
      await load();
      setMessage("操縦者を削除しました。");
    } catch (error) {
      setSubmitError(getErrorMessage(error, "操縦者を削除できませんでした。"));
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <Panel title="操縦者登録" eyebrow="Master">
        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
          <div>
            <label className="label">氏名</label>
            <input className="input" {...register("name")} />
            {errors.name ? <p className="mt-2 text-sm text-rose-600">{errors.name.message}</p> : null}
          </div>
          <div><label className="label">技能証明番号</label><input className="input" {...register("license_number")} /></div>
          <div><label className="label">所属</label><input className="input" {...register("organization")} /></div>
          <button className="btn-primary w-full" disabled={isSubmitting} type="submit">{isSubmitting ? "保存中..." : "操縦者を保存"}</button>
          {message ? <p className="text-sm font-semibold text-sky-700">{message}</p> : null}
          {submitError ? <p className="text-sm font-semibold text-rose-600">{submitError}</p> : null}
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
