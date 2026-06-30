const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

  const response = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
    method,
    signal,
    headers: {
      "Content-Type": "application/json",
      ...configHeaders,
      ...(options?.headers as Record<string, string> | undefined),
    },
    body: data ? JSON.stringify(data) : undefined,
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(
      `API error ${response.status}: ${response.statusText}. Body: ${errorBody}`,
    );
  }

  return response.json() as Promise<T>;
};

export default customInstance;
