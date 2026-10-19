// WS bağlantı durumu rozeti. Sahip: Esra.

interface Props {
  connected: boolean;
  mock?: boolean;
}

export function LiveBadge({ connected, mock }: Props) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span
        className={`inline-block h-2.5 w-2.5 rounded-full ${
          connected ? "bg-emerald-500" : "bg-rose-500"
        }`}
      />
      <span className={connected ? "text-emerald-700" : "text-rose-700"}>
        {connected ? "Canlı" : "Bağlantı yok"}
      </span>
      {mock && (
        <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">MOCK</span>
      )}
    </div>
  );
}
