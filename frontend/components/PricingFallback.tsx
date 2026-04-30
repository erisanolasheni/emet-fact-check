"use client";

import Link from "next/link";
import { useClerk, UserButton } from "@clerk/nextjs";

/** Shown on `/check` when `GET /api/subscription` reports no active plan. */
export function PricingFallback() {
  const clerk = useClerk();

  return (
    <div className="mx-auto max-w-lg rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-lg">
      <h2 className="text-xl font-semibold text-slate-900">Emet Premium</h2>
      <p className="mt-2 text-sm leading-relaxed text-slate-600">
        Fact-checking with multi-source comparison and citations requires an active subscription in
        Clerk Billing.
      </p>
      <div className="mt-6 flex flex-col items-center gap-3">
        <Link
          href="/pricing"
          className="inline-flex w-full max-w-xs justify-center rounded-full bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white shadow-md transition hover:bg-blue-700"
        >
          View plans &amp; how to subscribe
        </Link>
        <div className="flex justify-center">
          <UserButton afterSignOutUrl="/" showName />
        </div>
        <button
          type="button"
          onClick={() => clerk.openUserProfile()}
          className="text-sm font-medium text-blue-600 hover:underline"
        >
          Open account & billing now
        </button>
      </div>
      <p className="mt-4 text-xs text-slate-500">
        After subscribing, use the account menu in Clerk or return here—this page will refresh access
        automatically.
      </p>
      <Link href="/" className="mt-6 inline-block text-sm text-blue-600 hover:underline">
        Back home
      </Link>
    </div>
  );
}
