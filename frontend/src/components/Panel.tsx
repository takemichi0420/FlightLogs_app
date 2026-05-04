import { PropsWithChildren } from "react";

type Props = PropsWithChildren<{
  title?: string;
  eyebrow?: string;
  actions?: React.ReactNode;
}>;

export function Panel({ title, eyebrow, actions, children }: Props) {
  return (
    <section className="panel p-6">
      {(title || eyebrow || actions) && (
        <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
          <div>
            {eyebrow ? <p className="text-xs font-semibold text-sky-700">{eyebrow}</p> : null}
            {title ? <h2 className="mt-2 text-xl font-semibold text-ink">{title}</h2> : null}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}
