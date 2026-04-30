"use client";

import Link from "next/link";
import {
  SignedIn,
  SignedOut,
  SignInButton,
  SignUpButton,
  useClerk,
  UserButton,
} from "@clerk/nextjs";
import { Check } from "lucide-react";

const FEATURES = [
  "Multi-source fact-checking with side-by-side evidence",
  "Inline citations, reference cards, and source quality signals",
  "Live job progress and structured reports with confidence scores",
];

/**
 * Marketing + upgrade path for Emet Premium.
 * (Clerk v5 has no <PricingTable />; users subscribe via Clerk Billing — User menu or Dashboard.)
 * Layout inspired by the course `product.tsx` + Alex landing (hero, feature grid, dual CTAs).
 */
export function PricingPageContent() {
  const clerk = useClerk();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/60">
      <header className="border-b border-slate-200/80 bg-white/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5">
          <Link
            href="/"
            className="text-lg font-semibold tracking-tight text-slate-900"
          >
            Emet <span className="text-blue-600">אמת</span>
          </Link>
          <div className="flex items-center gap-3">
            <SignedOut>
              <SignInButton mode="modal">
                <button
                  type="button"
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                >
                  Sign in
                </button>
              </SignInButton>
              <SignUpButton mode="modal">
                <button
                  type="button"
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700"
                >
                  Get started
                </button>
              </SignUpButton>
            </SignedOut>
            <SignedIn>
              <UserButton afterSignOutUrl="/" showName />
            </SignedIn>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 pb-24 pt-16">
        <p className="text-center text-sm font-medium uppercase tracking-widest text-blue-600">
          Plans
        </p>
        <h1 className="mt-3 text-center text-4xl font-bold tracking-tight text-slate-900 md:text-5xl">
          Choose <span className="text-blue-600">Emet Premium</span>
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-center text-lg text-slate-600">
          Subscribe in Clerk Billing to unlock the full fact-check workspace.
        </p>

        <div className="mt-12 rounded-2xl border border-slate-200 bg-white p-8 shadow-lg shadow-slate-200/50 md:p-10">
          <div className="flex flex-col gap-2 border-b border-slate-100 pb-8 text-center sm:text-left">
            <h2 className="text-2xl font-semibold text-slate-900">Premium</h2>
            <p className="text-slate-600">Everything in the public preview, plus the full pipeline.</p>
          </div>
          <ul className="mt-8 space-y-4">
            {FEATURES.map((f) => (
              <li key={f} className="flex gap-3 text-slate-700">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-600">
                  <Check className="h-3 w-3" strokeWidth={3} />
                </span>
                {f}
              </li>
            ))}
          </ul>

          <div className="mt-10 flex flex-col items-center gap-4 border-t border-slate-100 pt-8 sm:flex-row sm:justify-center">
            <SignedOut>
              <SignUpButton mode="modal">
                <button
                  type="button"
                  className="w-full min-w-[200px] rounded-full bg-blue-600 px-8 py-3.5 text-sm font-semibold text-white shadow-md shadow-blue-600/20 transition hover:bg-blue-700 sm:w-auto"
                >
                  Create account
                </button>
              </SignUpButton>
              <span className="text-sm text-slate-500">Already have an account?</span>
              <SignInButton mode="modal">
                <button type="button" className="text-sm font-medium text-blue-600 hover:underline">
                  Sign in
                </button>
              </SignInButton>
            </SignedOut>
            <SignedIn>
              <p className="max-w-md text-center text-sm text-slate-600">
                Open the account modal and complete checkout for the configured Billing plan, then
                return to the app.
              </p>
              <div className="flex w-full flex-col items-center gap-3 sm:w-auto">
                <button
                  type="button"
                  onClick={() => clerk.openUserProfile()}
                  className="inline-flex rounded-full bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white shadow-md transition hover:bg-blue-700"
                >
                  Open account & billing
                </button>
                <UserButton
                  afterSignOutUrl="/"
                  showName
                  appearance={{ elements: { userButtonBox: "scale-110" } }}
                />
                <Link
                  href="/check"
                  className="text-sm font-medium text-blue-600 hover:underline"
                >
                  Go to fact-check →
                </Link>
              </div>
            </SignedIn>
          </div>
        </div>
      </main>
    </div>
  );
}
