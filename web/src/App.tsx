// Sahip: Esra. İSKELET — diğer sayfalar Hafta 2-3'te eklenecek.

import { NavLink, Route, BrowserRouter as Router, Routes } from "react-router-dom";

import { Dashboard } from "./pages/Dashboard";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 text-sm rounded ${isActive ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100"}`;

export default function App() {
  return (
    <Router>
      <nav className="flex gap-1 border-b border-slate-200 px-6 py-3">
        <span className="mr-4 self-center font-semibold">Smart Parking</span>
        <NavLink to="/" className={linkClass} end>
          Doluluk
        </NavLink>
        {/* TODO(Esra): FloorPlan · SessionLog — Hafta 2-3 */}
        {/* TODO(havuz #4): Tariffs · Reports */}
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
      </Routes>
    </Router>
  );
}
