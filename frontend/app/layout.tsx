import type { Metadata } from "next";
import "./globals.css";
import { Analytics } from "@/components/Analytics";
import { AuthGate } from "@/components/AuthGate";
import { HFLoginButton } from "@/components/HFLoginButton";

export const metadata: Metadata = {
  title: "Mayo Clinic Content Validator",
  description: "Multi-agent LangGraph content validation with HITL",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50">
        <header className="bg-mayo-blue text-white shadow-md">
          <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-white rounded-full flex items-center justify-center">
                <span className="text-mayo-blue font-bold text-sm">M</span>
              </div>
              <div>
                <h1 className="text-lg font-semibold tracking-tight">
                  Mayo Clinic Content Validator
                </h1>
                <p className="text-xs text-blue-200">
                  Multi-agent LangGraph validation pipeline
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <a
                href="/analytics"
                className="text-blue-200 hover:text-white transition-colors"
                title="Site Analytics"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
                </svg>
              </a>
              <HFLoginButton />
            </div>
          </div>
        </header>
        <Analytics />
        <main className="max-w-5xl mx-auto px-6 py-8">
          <AuthGate>{children}</AuthGate>
        </main>
      </body>
    </html>
  );
}
