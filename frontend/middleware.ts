import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isPublic = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)"]);

export default clerkMiddleware((auth, req) => {
  if (!isPublic(req)) {
    auth().protect();
  }
});

export const config = {
  matcher: [
    "/((?!api/health|_next/static|_next/image|favicon.ico)(?!.+\\.[\\w]+$).+)",
  ],
};
