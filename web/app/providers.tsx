"use client";

import { Sidebar } from "@/components/ui/sidebar";
import { ToastProvider } from "@/components/ui/toast";

export function ClientProviders({ children }: { children: React.ReactNode }) {
  return (
    <ToastProvider>
      <Sidebar />
      <main className="min-h-screen overflow-x-hidden lg:pl-64">
        <div className="mx-auto max-w-7xl px-4 py-8 pt-16 lg:pt-8">
          {children}
        </div>
      </main>
    </ToastProvider>
  );
}
