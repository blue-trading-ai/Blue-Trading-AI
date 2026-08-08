"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { getAccessToken } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    const accessToken = getAccessToken();

    if (accessToken) {
      router.replace("/dashboard");
      return;
    }

    router.replace("/login");
  }, [router]);

  return (
    <main className="midnight-page flex min-h-screen items-center justify-center p-5 text-white">
      <section className="midnight-panel w-full max-w-md rounded-3xl p-8 text-center">
        <div className="midnight-pulse mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-300/20 bg-blue-500/[0.06] text-xl font-black text-cyan-200">
          B
        </div>

        <p className="mt-5 text-sm font-black text-white">
          Blue-Trading-AI
        </p>

        <p className="mt-2 text-xs leading-5 text-slate-600">
          Preparing your secure workspace...
        </p>
      </section>
    </main>
  );
}