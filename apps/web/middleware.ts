import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const protectedPaths = [
  "/dashboard",
  "/onboard",
  "/setup",
  "/organization",
  "/activity",
  "/storage",
  "/settings",
];
const authPaths = ["/login", "/signup"];

export function middleware(request: NextRequest) {
  const token = request.cookies.get("oh_token")?.value;
  const { pathname } = request.nextUrl;

  // Redirect authenticated users away from auth pages
  if (token && authPaths.includes(pathname)) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  // Redirect unauthenticated users away from protected pages
  if (!token && protectedPaths.some((p) => pathname.startsWith(p))) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/onboard",
    "/setup",
    "/organization",
    "/activity",
    "/storage",
    "/settings",
    "/login",
    "/signup",
  ],
};
