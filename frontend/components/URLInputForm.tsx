"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { startValidation } from "@/lib/api";

export function URLInputForm() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isValidMayoUrl =
    url.trim().startsWith("http") && url.includes("mayoclinic.org");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!isValidMayoUrl) return;
    setLoading(true);
    setError("");
    try {
      const { validation_id } = await startValidation(url.trim());
      router.push(`/results/${validation_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to start validation");
      setLoading(false);
    }
  }

  const exampleUrls = [
    "https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/syc-20371444",
    "https://www.mayoclinic.org/diseases-conditions/heart-disease/symptoms-causes/syc-20353118",
    "https://www.mayoclinic.org/diseases-conditions/high-blood-pressure/symptoms-causes/syc-20373410",
  ];

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-1">
          Validate Content
        </h2>
        <p className="text-sm text-gray-500">
          Enter a Mayo Clinic URL to run it through the 4-agent validation
          pipeline with human-in-the-loop review.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="url-input"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Mayo Clinic URL
          </label>
          <div className="flex gap-3">
            <input
              id="url-input"
              type="url"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                setError("");
              }}
              placeholder="https://www.mayoclinic.org/diseases-conditions/..."
              className="flex-1 rounded-lg border border-gray-300 px-4 py-3 text-sm
                         focus:outline-none focus:ring-2 focus:ring-mayo-blue focus:border-transparent
                         placeholder:text-gray-400"
              disabled={loading}
              autoComplete="off"
            />
            <button
              type="submit"
              disabled={!isValidMayoUrl || loading}
              className="px-6 py-3 bg-mayo-blue text-white rounded-lg font-medium text-sm
                         disabled:opacity-40 disabled:cursor-not-allowed
                         hover:bg-mayo-lightblue transition-colors"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Starting...
                </span>
              ) : (
                "Validate"
              )}
            </button>
          </div>
          {url && !isValidMayoUrl && (
            <p className="mt-1.5 text-xs text-red-500">
              URL must be from mayoclinic.org
            </p>
          )}
          {error && (
            <p className="mt-1.5 text-xs text-red-500">{error}</p>
          )}
        </div>
      </form>

      <div className="mt-5">
        <p className="text-xs text-gray-400 mb-2">Example URLs:</p>
        <div className="space-y-1.5">
          {exampleUrls.map((exUrl) => (
            <button
              key={exUrl}
              onClick={() => setUrl(exUrl)}
              className="block w-full text-left text-xs text-mayo-blue hover:underline truncate"
              disabled={loading}
            >
              {exUrl}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
