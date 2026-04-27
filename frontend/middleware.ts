import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isPublic = createRouteMatcher(["/", "/sign-in(.*)", "/sign-up(.*)", "/api/health"]);

export default clerkMiddleware((auth, req) => {
  if (!isPublic(req)) {
    auth().protect();
  }
});

export const config = {
  // Exclude /api/health so probes skip Clerk entirely (faster for App Runner).
  matcher: ["/((?!api/health)(?!.+\\.[\\w]+$|_next).*)", "/"],
};
