import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Auth middleware — redirects unauthenticated users to /login.
 *
 * Checks for the presence of the access_token cookie. If missing,
 * redirects to /login (unless the request is for a public route).
 */

const PUBLIC_PATHS = new Set([
  "/login",
  "/accept-invite",
  "/forgot-password",
  "/reset-password",
]);

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_PATHS.has(pathname)) return true;
  // Allow API routes and static assets to pass through
  if (pathname.startsWith("/api/")) return true;
  if (pathname.startsWith("/_next/")) return true;
  if (pathname.startsWith("/favicon")) return true;
  // Allow logo serving
  if (pathname.startsWith("/api/v1/branding/logo/")) return true;
  return false;
}

export function middleware(request: NextRequest): NextResponse | undefined {
  const { pathname } = request.nextUrl;

  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  const accessToken = request.cookies.get("access_token");
  if (!accessToken?.value) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  // Match all routes except static files and API
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
