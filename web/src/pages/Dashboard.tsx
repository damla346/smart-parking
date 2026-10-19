// Canlı doluluk dashboard'u. Sahip: Esra.
// İSKELET — Hafta 1. Şu an mock_gateway'in WS yayınına bağlanıp çalışır durumda.

import { LiveBadge } from "../components/LiveBadge";
import { isMock } from "../api/client";
import { useOccupancy } from "../store/occupancy";

export function Dashboard() {
  const { data, connected, error } = useOccupancy(1);

  if (error) {
    return (
      <div className="p-8 text-rose-700">
        Veri alınamadı: {error}
        <p className="mt-2 text-sm text-slate-600">
          mock_gateway çalışıyor mu? <code>python infra/mocks/mock_gateway.py</code>
        </p>
      </div>
    );
  }

  if (!data) return <div className="p-8 text-slate-500">Yükleniyor…</div>;

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Doluluk Durumu</h1>
        <LiveBadge connected={connected} mock={isMock} />
      </div>

      <div className="mb-8 grid grid-cols-3 gap-4">
        <Stat label="Toplam" value={data.total} />
        <Stat label="Dolu" value={data.occupied} tone="rose" />
        <Stat label="Boş" value={data.free} tone="emerald" />
      </div>

      <h2 className="mb-3 text-lg font-medium">Katlar</h2>
      <div className="space-y-2">
        {data.by_floor.map((kat) => (
          <div key={kat.floor_id} className="rounded border border-slate-200 p-4">
            <div className="mb-2 flex justify-between text-sm">
              <span className="font-medium">{kat.level}. Kat</span>
              <span className="text-slate-600">
                {kat.occupied} / {kat.total} dolu
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded bg-slate-100">
              <div
                className="h-full bg-slate-700 transition-all duration-500"
                style={{ width: `${(kat.occupied / kat.total) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: "rose" | "emerald" }) {
  const renk =
    tone === "rose" ? "text-rose-600" : tone === "emerald" ? "text-emerald-600" : "text-slate-900";
  return (
    <div className="rounded border border-slate-200 p-4">
      <div className="text-sm text-slate-500">{label}</div>
      <div className={`text-3xl font-semibold ${renk}`}>{value}</div>
    </div>
  );
}
