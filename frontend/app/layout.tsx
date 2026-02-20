import type { Metadata } from "next";
import "./globals.css";

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
          <div className="max-w-5xl mx-auto px-6 py-4 flex items-center gap-3">
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
        </header>
        <main className="max-w-5xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
