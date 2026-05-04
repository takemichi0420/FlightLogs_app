import { NavLink, Outlet } from "react-router-dom";
import { AuthUser } from "../lib/types";

type Props = {
  user: AuthUser;
  onLogout: () => Promise<void>;
};

const links = [
  { to: "/", label: "ダッシュボード" },
  { to: "/aircraft", label: "機体" },
  { to: "/pilots", label: "操縦者" },
  { to: "/records", label: "飛行記録" },
];

export function AppShell({ user, onLogout }: Props) {
  return (
    <div className="min-h-screen px-4 py-6 md:px-8">
      <div className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="panel relative overflow-hidden p-6">
          <div className="absolute inset-x-0 top-0 h-28 bg-gradient-to-r from-ink via-sea to-tide opacity-95" />
          <div className="relative">
            <p className="text-xs font-semibold text-sky-100">ArduPilot</p>
            <h1 className="mt-2 text-2xl font-semibold text-white">飛行記録アプリ</h1>
            <p className="mt-3 text-sm text-sky-50/90">{user.username} / {user.email}</p>
          </div>
          <nav className="relative mt-10 space-y-2">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === "/"}
                className={({ isActive }) =>
                  [
                    "block rounded-2xl px-4 py-3 text-sm font-semibold transition",
                    isActive ? "bg-sky-100 text-sea" : "text-slate-700 hover:bg-slate-100",
                  ].join(" ")
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
          <button className="btn-secondary mt-8 w-full" onClick={() => void onLogout()}>
            ログアウト
          </button>
        </aside>
        <main className="space-y-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
