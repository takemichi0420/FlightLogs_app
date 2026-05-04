import clsx from "clsx";

type Props = {
  value: string;
};

const palette: Record<string, string> = {
  uploaded: "bg-slate-100 text-slate-700",
  analyzing: "bg-amber-100 text-amber-800",
  analysis_failed: "bg-rose-100 text-rose-700",
  draft: "bg-sky-100 text-sky-800",
  finalized: "bg-emerald-100 text-emerald-800",
  normal: "bg-emerald-100 text-emerald-800",
  warning: "bg-amber-100 text-amber-800",
  danger: "bg-rose-100 text-rose-700",
};

const labels: Record<string, string> = {
  uploaded: "アップロード済み",
  analyzing: "解析中",
  analysis_failed: "解析失敗",
  draft: "下書き",
  finalized: "確定済み",
  normal: "正常",
  warning: "要確認",
  danger: "危険",
};

export function StatusBadge({ value }: Props) {
  return (
    <span className={clsx("inline-flex rounded-full px-3 py-1 text-xs font-semibold", palette[value] ?? "bg-slate-100 text-slate-700")}>
      {labels[value] ?? value}
    </span>
  );
}
