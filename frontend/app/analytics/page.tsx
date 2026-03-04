"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface AnalyticsData {
  total_views: number;
  unique_visitors: number;
  daily: { day: string; views: number }[];
  top_pages: { path: string; views: number }[];
  top_referrers: { referrer: string; views: number }[];
  visitors: { ip: string; views: number; last_seen: string }[];
  recent: {
    path: string;
    referrer: string | null;
    ip: string | null;
    user_agent: string | null;
    session_id: string | null;
    created_at: string;
  }[];
  period_days: number;
}

export default function AnalyticsPage() {
  const router = useRouter();
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const base =
      process.env.NEXT_PUBLIC_API_URL ||
      (typeof window !== "undefined" && window.location.port === "3000"
        ? "http://localhost:8000"
        : "");
    fetch(`${base}/api/analytics?days=${days}`)
      .then((r) => r.json())
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [days]);

  const maxDaily = data ? Math.max(...data.daily.map((d) => d.views), 1) : 1;

  return (
    <div className="space-y-6">
      <button
        onClick={() => router.push("/")}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back to Dashboard
      </button>

      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-900">Site Analytics</h2>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="text-sm border border-gray-300 rounded-lg px-3 py-1.5"
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {loading ? (
        <p className="text-sm text-gray-500">Loading analytics...</p>
      ) : !data ? (
        <p className="text-sm text-red-500">Failed to load analytics.</p>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border p-5">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Total Page Views</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">{data.total_views.toLocaleString()}</p>
            </div>
            <div className="bg-white rounded-xl border p-5">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Unique Visitors</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">{data.unique_visitors.toLocaleString()}</p>
            </div>
          </div>

          {/* Daily chart */}
          {data.daily.length > 0 && (
            <div className="bg-white rounded-xl border p-5">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Daily Views</p>
              <div className="flex items-end gap-1 h-32">
                {data.daily.map((d) => (
                  <div key={d.day} className="flex-1 flex flex-col items-center group relative">
                    <div
                      className="w-full bg-blue-500 rounded-t hover:bg-blue-600 transition-colors"
                      style={{ height: `${(d.views / maxDaily) * 100}%`, minHeight: d.views > 0 ? 4 : 0 }}
                    />
                    <div className="absolute -top-8 bg-gray-800 text-white text-[10px] px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 whitespace-nowrap pointer-events-none">
                      {d.day}: {d.views}
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex justify-between mt-1">
                <span className="text-[10px] text-gray-400">{data.daily[0]?.day}</span>
                <span className="text-[10px] text-gray-400">{data.daily[data.daily.length - 1]?.day}</span>
              </div>
            </div>
          )}

          {/* Top pages + Top referrers */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border p-5">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Top Pages</p>
              {data.top_pages.length === 0 ? (
                <p className="text-xs text-gray-400 italic">No data yet</p>
              ) : (
                <ul className="space-y-2">
                  {data.top_pages.map((p) => (
                    <li key={p.path} className="flex justify-between text-sm">
                      <span className="text-gray-700 font-mono text-xs truncate">{p.path}</span>
                      <span className="text-gray-500 font-medium ml-2">{p.views}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="bg-white rounded-xl border p-5">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Top Referrers</p>
              {data.top_referrers.length === 0 ? (
                <p className="text-xs text-gray-400 italic">No data yet</p>
              ) : (
                <ul className="space-y-2">
                  {data.top_referrers.map((r) => (
                    <li key={r.referrer} className="flex justify-between text-sm">
                      <span className="text-gray-700 text-xs truncate">{r.referrer}</span>
                      <span className="text-gray-500 font-medium ml-2">{r.views}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Visitors by IP */}
          <div className="bg-white rounded-xl border p-5">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Visitors by IP</p>
            {data.visitors.length === 0 ? (
              <p className="text-xs text-gray-400 italic">No data yet</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-gray-500 border-b">
                      <th className="pb-2 font-semibold">IP Address</th>
                      <th className="pb-2 font-semibold">Views</th>
                      <th className="pb-2 font-semibold">Last Seen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.visitors.map((v) => (
                      <tr key={v.ip} className="border-b border-gray-50">
                        <td className="py-1.5 font-mono text-gray-700">{v.ip}</td>
                        <td className="py-1.5 text-gray-600">{v.views}</td>
                        <td className="py-1.5 text-gray-500">{new Date(v.last_seen).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Recent visits */}
          <div className="bg-white rounded-xl border p-5">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Recent Visits (Last 50)</p>
            {data.recent.length === 0 ? (
              <p className="text-xs text-gray-400 italic">No data yet</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-gray-500 border-b">
                      <th className="pb-2 font-semibold">Time</th>
                      <th className="pb-2 font-semibold">Path</th>
                      <th className="pb-2 font-semibold">IP</th>
                      <th className="pb-2 font-semibold">Referrer</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent.map((r, i) => (
                      <tr key={i} className="border-b border-gray-50">
                        <td className="py-1.5 text-gray-500 whitespace-nowrap">
                          {new Date(r.created_at).toLocaleString()}
                        </td>
                        <td className="py-1.5 font-mono text-gray-700">{r.path}</td>
                        <td className="py-1.5 font-mono text-gray-600">{r.ip || "-"}</td>
                        <td className="py-1.5 text-gray-500 truncate max-w-[200px]">{r.referrer || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
