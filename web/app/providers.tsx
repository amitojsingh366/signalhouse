"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Sidebar } from "@/components/ui/sidebar";
import { TopBar } from "@/components/ui/topbar";
import { ToastProvider } from "@/components/ui/toast";
import { CommandSearch } from "@/components/ui/command-search";
import { AuthGate } from "@/components/ui/auth-gate";
import { PrivacyProvider } from "@/lib/privacy";

export function ClientProviders({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 2 * 60 * 1000, // 2 min default
            gcTime: 10 * 60 * 1000,   // keep unused data 10 min
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <PrivacyProvider>
        <ToastProvider>
          <AuthGate>
            <div className="app-shell">
              <Sidebar />
              <div className="main-shell">
                <TopBar />
                <main className="content-shell">
                  {children}
                </main>
              </div>
            </div>
            <CommandSearch />
          </AuthGate>
        </ToastProvider>
      </PrivacyProvider>
    </QueryClientProvider>
  );
}
