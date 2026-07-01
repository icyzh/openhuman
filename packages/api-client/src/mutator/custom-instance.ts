const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  body: string;

  constructor(status: number, statusText: string, body: string) {
    super(statusText);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export const customInstance = async <T>(
  config: {
    url: string;
    method: string;
    headers?: Record<string, string>;
    params?: unknown;
    data?: unknown;
    signal?: AbortSignal;
  },
  options?: RequestInit & {
    next?: { revalidate?: number; tags?: string[] };
  },
): Promise<T> => {
  const { url, method, headers: configHeaders, data, signal } = config;

  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("oh_token")
      : null;

  const response = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
    method,
    signal,
    headers: {
      ...(data instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...configHeaders,
      ...(options?.headers as Record<string, string> | undefined),
    },
    body: data instanceof FormData ? data : data ? JSON.stringify(data) : undefined,
  });

  if (response.status === 401 && !url.startsWith("/api/auth/")) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("oh_token");
      localStorage.removeItem("oh-auth");
      document.cookie = "oh_token=; path=/; max-age=0; SameSite=Lax";
      window.location.href = "/login";
    }
    throw new ApiError(401, "Unauthorized", "Session expired");
  }

  if (!response.ok) {
    const errorBody = await response.text();
    throw new ApiError(
      response.status,
      response.statusText,
      errorBody,
    );
  }

  return response.json() as Promise<T>;
};

export default customInstance;
