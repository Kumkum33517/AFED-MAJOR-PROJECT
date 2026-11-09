import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import Layout from "./components/Layout";
import { ErrorState, Forbidden, Loading, NotFound } from "./components/ui";
import type { Role } from "./lib/api";
import { OPERATE, useAuth } from "./lib/auth";
import AlertDetail from "./pages/AlertDetail";
import Alerts from "./pages/Alerts";
import { CaseDetail, Cases } from "./pages/Cases";
import Dashboard from "./pages/Dashboard";
import { Entities, EntityProfile } from "./pages/Entities";
import Evaluation from "./pages/Evaluation";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Notifications from "./pages/Notifications";
import Profile from "./pages/Profile";
import Reports from "./pages/Reports";
import Settings from "./pages/Settings";
import Upload from "./pages/Upload";
import Users from "./pages/Users";

function RequireLogin() {
  const { user, ready, error, retry } = useAuth();
  const location = useLocation();
  if (!ready) return <div className="p-8"><Loading /></div>;
  if (error) return <div className="p-8"><ErrorState error={error} retry={retry} /></div>;
  return user ? <Layout><Outlet /></Layout> : <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
}

/** UI convenience only: every one of these routes is also enforced by the API. */
function RequireRole({ roles }: { roles: Role[] }) {
  const { user } = useAuth();
  return user && roles.includes(user.role) ? <Outlet /> : <Forbidden />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route element={<RequireLogin />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/alerts/:id" element={<AlertDetail />} />
        <Route path="/cases" element={<Cases />} />
        <Route path="/cases/:id" element={<CaseDetail />} />
        <Route path="/entities" element={<Entities />} />
        <Route path="/entities/:type/:id" element={<EntityProfile />} />
        <Route path="/evaluation" element={<Evaluation />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/notifications" element={<Notifications />} />
        <Route path="/profile" element={<Profile />} />
        <Route element={<RequireRole roles={OPERATE} />}>
          <Route path="/upload" element={<Upload />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
        <Route element={<RequireRole roles={["Admin"]} />}>
          <Route path="/users" element={<Users />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
