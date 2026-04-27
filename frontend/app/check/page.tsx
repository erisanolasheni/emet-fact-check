"use client";

import { SignedIn, SignedOut, SignInButton } from "@clerk/nextjs";
import { FactCheckSubscriptionGate } from "@/components/FactCheckSubscriptionGate";

export default function CheckPage() {
  return (
    <div className="min-h-screen bg-slate-100/80">
      <SignedIn>
        <FactCheckSubscriptionGate />
      </SignedIn>
      <SignedOut>
        <div className="mx-auto max-w-md space-y-4 px-6 py-20 text-center">
          <p className="text-slate-600">Sign in to run a fact-check.</p>
          <SignInButton mode="modal">
            <button
              type="button"
              className="rounded-full bg-slate-900 px-6 py-2.5 text-sm font-medium text-white hover:bg-slate-800"
            >
              Sign in
            </button>
          </SignInButton>
        </div>
      </SignedOut>
    </div>
  );
}
