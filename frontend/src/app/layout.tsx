import "./globals.css";
import type { Metadata } from "next";
import Header from "@/components/Header";

export const metadata: Metadata = {
  title: "AI Agent",
  description: "Chat with Gmail/Calendar context",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 text-gray-900">
        <div className="mx-auto max-w-3xl mt-6">
          <Header />
          <div className="mx-auto max-w-xl p-4 sm:p-6">{children}</div>
        </div>
      </body>
    </html>
  );
}
