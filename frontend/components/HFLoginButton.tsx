"use client";

import { useEffect, useState } from "react";

interface HFUser {
  username: string;
  name: string;
  picture: string;
}

export function HFLoginButton() {
  const [user, setUser] = useState<HFUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const base =
      process.env.NEXT_PUBLIC_API_URL ||
      (typeof window !== "undefined" && window.location.port === "3000"
        ? "http://localhost:8000"
        : "");
    fetch(`${base}/api/auth/me`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => { setUser(d.user); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return null;

  // Build OAuth login URL — works on HF Spaces where /oauth/huggingface/login exists
  const loginUrl =
    typeof window !== "undefined" && window.location.port !== "3000"
      ? "/oauth/huggingface/login"
      : "http://localhost:8000/oauth/huggingface/login";

  const logoutUrl =
    typeof window !== "undefined" && window.location.port !== "3000"
      ? "/oauth/huggingface/logout"
      : "http://localhost:8000/oauth/huggingface/logout";

  if (user) {
    return (
      <div className="flex items-center gap-3">
        <a
          href="/analytics"
          className="text-xs text-blue-200 hover:text-white transition-colors"
          title="Site Analytics"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
          </svg>
        </a>
        <div className="flex items-center gap-2">
          {user.picture && (
            <img
              src={user.picture}
              alt={user.name || user.username}
              className="w-6 h-6 rounded-full"
            />
          )}
          <span className="text-xs text-blue-200">{user.name || user.username}</span>
          <a
            href={logoutUrl}
            className="text-[10px] text-blue-300 hover:text-white underline ml-1"
          >
            logout
          </a>
        </div>
      </div>
    );
  }

  return (
    <a
      href={loginUrl}
      className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-white/10 hover:bg-white/20 text-xs text-blue-100 hover:text-white transition-colors"
    >
      <svg className="w-3.5 h-3.5" viewBox="0 0 95 88" fill="currentColor">
        <path d="M47.2 0C24.5 0 6.1 18.4 6.1 41.1c0 7.8 2.2 15.1 6 21.3L0 88l26.4-12.1c6.2 3.3 13.3 5.2 20.8 5.2 22.7 0 41.1-18.4 41.1-41.1S69.9 0 47.2 0z" />
      </svg>
      Sign in with HF
    </a>
  );
}
