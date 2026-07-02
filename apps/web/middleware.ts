import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isProtectedRoute = createRouteMatcher([
  "/dashboard/:path*",
  "/onboard",
  "/setup",
  "/organization/:path*",
  "/activity/:path*",
  "/storage/:path*",
  "/settings/:path*",
]);

const isLegacyAuthRoute = createRouteMatcher(["/login", "/signup"]);

export default clerkMiddleware(async (auth, req) => {
  // Redirect legacy auth routes to Clerk equivalents
  if (isLegacyAuthRoute(req)) {
    const { userId } = await auth();
    if (userId) {
      return NextResponse.redirect(new URL("/dashboard", req.url));
    }
    const clerkPath = req.nextUrl.pathname === "/login" ? "/sign-in" : "/sign-up";
    return NextResponse.redirect(new URL(clerkPath, req.url));
  }

  // Protect dashboard and app routes
  if (isProtectedRoute(req)) {
    await auth.protect();
  }
});

export const config = {
  matcher: [
    // Skip Next.js internals and static files
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // Always run for API routes
    "/(api|trpc)(.*)",
    // Include Clerk proxy path
    "/__clerk/:path*",
  ],
};
