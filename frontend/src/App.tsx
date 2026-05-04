import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { api } from "./lib/api";
import { AuthUser } from "./lib/types";
import { AircraftPage } from "./pages/AircraftPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { PilotsPage } from "./pages/PilotsPage";
import { RecordDetailPage } from "./pages/RecordDetailPage";
import { RecordsPage } from "./pages/RecordsPage";

export function App() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadUser() {
    try {
      const response = await api.get<AuthUser>("/auth/me/");
      setUser(response.data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadUser();
  }, []);

  async function handleLogout() {
    await api.post("/auth/logout/");
    setUser(null);
  }

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center text-slate-500">読み込み中...</div>;
  }

  if (!user) {
    return <LoginPage onSuccess={setUser} />;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell onLogout={handleLogout} user={user} />}>
          <Route element={<DashboardPage />} path="/" />
          <Route element={<AircraftPage />} path="/aircraft" />
          <Route element={<PilotsPage />} path="/pilots" />
          <Route element={<RecordsPage />} path="/records" />
          <Route element={<RecordDetailPage />} path="/records/:recordId" />
          <Route element={<Navigate replace to="/" />} path="*" />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
