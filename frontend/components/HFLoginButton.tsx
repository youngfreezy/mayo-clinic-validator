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
  const [isHFSpaces, setIsHFSpaces] = useState(false);

  useEffect(() => {
    const isLocal =
      typeof window !== "undefined" && window.location.port === "3000";
    setIsHFSpaces(!isLocal);

    const base =
      process.env.NEXT_PUBLIC_API_URL || (isLocal ? "http://localhost:8000" : "");
    fetch(`${base}/api/auth/me`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => { setUser(d.user); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return null;

  // Don't render anything on localhost — no OAuth available
  if (!isHFSpaces) return null;

  if (user) {
    return (
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
          href="/oauth/huggingface/logout"
          className="text-[10px] text-blue-300 hover:text-white underline ml-1"
        >
          logout
        </a>
      </div>
    );
  }

  return (
    <a
      href="/oauth/huggingface/login"
      className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-white/10 hover:bg-white/20 text-xs text-blue-100 hover:text-white transition-colors"
    >
      <svg className="w-3.5 h-3.5" viewBox="0 0 95 88" fill="currentColor">
        <path d="M47.2 0C24.5 0 6.1 18.4 6.1 41.1c0 7.8 2.2 15.1 6 21.3L0 88l26.4-12.1c6.2 3.3 13.3 5.2 20.8 5.2 22.7 0 41.1-18.4 41.1-41.1S69.9 0 47.2 0z" />
      </svg>
      Sign in with HF
    </a>
  );
}
