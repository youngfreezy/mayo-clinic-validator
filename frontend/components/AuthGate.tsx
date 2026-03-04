"use client";

import { useEffect, useState } from "react";

interface HFUser {
  username: string;
  name: string;
  picture: string;
}

/**
 * Blocks app access until the visitor signs in with Hugging Face.
 * Only enforced on HF Spaces (detects by checking if OAuth routes exist).
 * Locally (port 3000), the gate is skipped.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<HFUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [isHFSpaces, setIsHFSpaces] = useState(false);

  useEffect(() => {
    const isLocal =
      typeof window !== "undefined" && window.location.port === "3000";
    setIsHFSpaces(!isLocal);

    if (isLocal) {
      // Skip auth gate locally
      setLoading(false);
      return;
    }

    const base =
      process.env.NEXT_PUBLIC_API_URL ||
      (isLocal ? "http://localhost:8000" : "");

    fetch(`${base}/api/auth/me`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        setUser(d.user);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  // Local dev — no gate
  if (!isHFSpaces) return <>{children}</>;

  // Loading
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-pulse text-sm text-gray-400">Loading...</div>
      </div>
    );
  }

  // Not logged in — show login screen
  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="bg-white rounded-2xl shadow-lg border p-8 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"
              />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">
            Sign in to continue
          </h2>
          <p className="text-sm text-gray-500 mb-6">
            Sign in with your Hugging Face account to use the Mayo Clinic Content Validator.
          </p>
          <a
            href="/oauth/huggingface/login"
            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-mayo-blue text-white font-medium text-sm hover:bg-blue-800 transition-colors"
          >
            <svg className="w-4 h-4" viewBox="0 0 95 88" fill="currentColor">
              <path d="M47.2 0C24.5 0 6.1 18.4 6.1 41.1c0 7.8 2.2 15.1 6 21.3L0 88l26.4-12.1c6.2 3.3 13.3 5.2 20.8 5.2 22.7 0 41.1-18.4 41.1-41.1S69.9 0 47.2 0z" />
            </svg>
            Sign in with Hugging Face
          </a>
        </div>
      </div>
    );
  }

  // Authenticated — render app
  return <>{children}</>;
}
