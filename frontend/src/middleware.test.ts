import { describe, it, expect, vi, beforeEach } from "vitest";

// We need to mock next/server before importing the middleware
vi.mock("next/server", () => {
  class MockNextResponse {
    status: number;
    headers: Map<string, string>;
    _type: string;
    _url?: string;

    constructor(body: BodyInit | null = null, init?: ResponseInit) {
      this.status = init?.status ?? 200;
      this.headers = new Map();
      this._type = "next";
    }

    static next() {
      const res = new MockNextResponse();
      res._type = "next";
      return res;
    }

    static redirect(url: URL | string) {
      const res = new MockNextResponse();
      res._type = "redirect";
      res.status = 307;
      res._url = typeof url === "string" ? url : url.toString();
      return res;
    }
  }

  return { NextResponse: MockNextResponse };
});

// Helper to create a mock NextRequest
function createMockRequest(
  pathname: string,
  cookies: Record<string, string> = {},
): {
  nextUrl: { pathname: string };
  url: string;
  cookies: { get: (name: string) => { value: string } | undefined };
} {
  return {
    nextUrl: { pathname },
    url: `http://localhost:3000${pathname}`,
    cookies: {
      get(name: string) {
        return cookies[name] ? { value: cookies[name] } : undefined;
      },
    },
  };
}

// We import the middleware after mocking next/server
let middleware: (
  request: ReturnType<typeof createMockRequest>,
) => { _type: string; _url?: string; status: number } | undefined;

beforeEach(async () => {
  vi.resetModules();
  const mod = await import("./middleware");
  middleware = mod.middleware as typeof middleware;
});

describe("Auth middleware", () => {
  it("/login is public and passes through without redirect", () => {
    const req = createMockRequest("/login");
    const res = middleware(req);
    // NextResponse.next() returns an object with _type "next"
    expect(res).toBeDefined();
    expect((res as { _type: string })._type).toBe("next");
  });

  it("/accept-invite is public and passes through", () => {
    const req = createMockRequest("/accept-invite");
    const res = middleware(req);
    expect(res).toBeDefined();
    expect((res as { _type: string })._type).toBe("next");
  });

  it("/dashboard without access_token cookie redirects to /login", () => {
    const req = createMockRequest("/dashboard");
    const res = middleware(req);
    expect(res).toBeDefined();
    expect((res as { _type: string })._type).toBe("redirect");
    expect((res as { _url: string })._url).toContain("/login");
    expect((res as { _url: string })._url).toContain("redirect=%2Fdashboard");
  });

  it("/dashboard with access_token cookie passes through", () => {
    const req = createMockRequest("/dashboard", { access_token: "valid-jwt" });
    const res = middleware(req);
    expect(res).toBeDefined();
    expect((res as { _type: string })._type).toBe("next");
  });

  it("/api/* routes pass through (public path)", () => {
    const req = createMockRequest("/api/v1/findings");
    const res = middleware(req);
    expect(res).toBeDefined();
    expect((res as { _type: string })._type).toBe("next");
  });

  it("/_next/* routes pass through (static assets)", () => {
    const req = createMockRequest("/_next/static/chunks/main.js");
    const res = middleware(req);
    expect(res).toBeDefined();
    expect((res as { _type: string })._type).toBe("next");
  });

  it("/findings without cookie redirects to /login with redirect param", () => {
    const req = createMockRequest("/findings");
    const res = middleware(req);
    expect(res).toBeDefined();
    expect((res as { _type: string })._type).toBe("redirect");
    expect((res as { _url: string })._url).toContain("/login");
    expect((res as { _url: string })._url).toContain("redirect=%2Ffindings");
  });

  it("/forgot-password is public and passes through", () => {
    const req = createMockRequest("/forgot-password");
    const res = middleware(req);
    expect(res).toBeDefined();
    expect((res as { _type: string })._type).toBe("next");
  });

  it("/settings with cookie passes through", () => {
    const req = createMockRequest("/settings", { access_token: "my-token" });
    const res = middleware(req);
    expect(res).toBeDefined();
    expect((res as { _type: string })._type).toBe("next");
  });

  it("empty access_token value triggers redirect", () => {
    const req = createMockRequest("/dashboard", { access_token: "" });
    // The middleware checks `!accessToken?.value`, and our mock returns
    // { value: "" } which is falsy, so it should redirect.
    const res = middleware(req);
    expect(res).toBeDefined();
    expect((res as { _type: string })._type).toBe("redirect");
  });
});
