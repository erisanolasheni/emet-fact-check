import { NextResponse } from "next/server";

/** Fast probe for load balancers / App Runner — no Clerk, minimal work. */
export async function GET() {
  return NextResponse.json({ status: "ok" }, { status: 200 });
}
