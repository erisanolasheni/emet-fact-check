"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { FactCheckShell } from "@/components/FactCheckShell";
import { PricingFallback } from "@/components/PricingFallback";
import { ApiError, getSubscriptionStatus } from "@/lib/api";

type GateState = "loading" | "premium" | "no";

export function FactCheckSubscriptionGate() {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const [status, setStatus] = useState<GateState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    if (!isLoaded || !isSignedIn) {
      return;
    }
    setError(null);
    let cancelled = false;
    (async () => {
      try {
        const token = await getToken();
        if (!token) {
          if (!cancelled) {
            setError("Could not get a session token. Refresh the page or sign in again.");
            setStatus("no");
          }
          return;
        }
        const data = await getSubscriptionStatus(token);
        if (!cancelled) {
          setStatus(data.has_premium ? "premium" : "no");
        }
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError) {
          setError(`${e.status}: ${e.message}`);
        } else if (e instanceof Error) {
          setError(e.message);
        } else {
          setError("Subscription check failed");
        }
        setStatus("no");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isLoaded, isSignedIn, getToken, retry]);

  if (!isLoaded) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-slate-500">
        <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
      </div>
    );
  }

  if (!isSignedIn) {
    return <PricingFallback />;
  }

  if (error) {
    return (
      <div className="mx-auto max-w-md rounded-2xl border border-red-200 bg-red-50/80 p-6 text-center">
        <p className="text-sm text-red-800">{error}</p>
        <button
          type="button"
          onClick={() => {
            setError(null);
            setStatus("loading");
            setRetry((n) => n + 1);
          }}
          className="mt-4 rounded-full border border-red-300 bg-white px-4 py-2 text-sm text-red-900 hover:bg-red-50"
        >
          Retry
        </button>
      </div>
    );
  }

  if (status === "loading") {
    return (
      <div className="flex min-h-[40vh] flex-col items-center justify-center gap-2 text-slate-500">
        <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
        <span className="text-sm">Checking subscription…</span>
      </div>
    );
  }

  if (status === "no") {
    return <PricingFallback />;
  }

  return <FactCheckShell />;
}
