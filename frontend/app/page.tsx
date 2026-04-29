"use client";

import Link from "next/link";
import { SignedIn, SignedOut, UserButton } from "@clerk/nextjs";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-6 py-8">
        <span className="text-xl font-semibold tracking-tight text-slate-900">
          Emet <span className="text-blue-600">אמת</span>
        </span>
        <nav className="flex items-center gap-4">
          <Link
            href="/pricing"
            className="text-sm font-medium text-slate-600 transition hover:text-slate-900"
          >
            Pricing
          </Link>
          <SignedOut>
            <Link
              href="/sign-in"
              className="rounded-full bg-slate-900 px-5 py-2 text-sm font-medium text-white hover:bg-slate-800"
            >
              Sign in
            </Link>
          </SignedOut>
          <SignedIn>
            <UserButton afterSignOutUrl="/" showName />
          </SignedIn>
        </nav>
      </header>

      <main className="mx-auto max-w-3xl px-6 pb-24 pt-12 text-center">
        <p className="text-sm font-medium uppercase tracking-widest text-blue-600">Capstone</p>
        <h1 className="mt-4 text-4xl font-bold tracking-tight text-slate-900 md:text-5xl">
          Fact-checking with evidence you can inspect
        </h1>
        <p className="mt-6 text-lg leading-relaxed text-slate-600">
          Ask a question. Emet searches reputable sources, compares evidence, and returns cited facts
          with an honest confidence score.
        </p>
        <div className="mt-10 flex flex-wrap justify-center gap-4">
          <Link
            href="/check"
            className="rounded-full bg-blue-600 px-8 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 hover:bg-blue-700"
          >
            Start a check
          </Link>
          <SignedOut>
            <Link
              href="/sign-in"
              className="rounded-full border border-slate-200 px-8 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Sign in
            </Link>
          </SignedOut>
        </div>
      </main>
    </div>
  );
}
