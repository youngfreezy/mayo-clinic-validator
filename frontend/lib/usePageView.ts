"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

/** Stable session ID persisted in sessionStorage. */
function getSessionId(): string {
  if (typeof window === "undefined") return "";
  let sid = sessionStorage.getItem("_sid");
  if (!sid) {
    sid = crypto.randomUUID();
    sessionStorage.setItem("_sid", sid);
  }
  return sid;
}

/** Sends a pageview beacon on every route change. */
export function usePageView() {
  const pathname = usePathname();

  useEffect(() => {
    const base =
      process.env.NEXT_PUBLIC_API_URL ||
      (typeof window !== "undefined" && window.location.port === "3000"
        ? "http://localhost:8000"
        : "");

    fetch(`${base}/api/analytics/pageview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        path: pathname,
        referrer: document.referrer || "",
        session_id: getSessionId(),
      }),
    }).catch(() => {}); // fire-and-forget, never block UI
  }, [pathname]);
}
