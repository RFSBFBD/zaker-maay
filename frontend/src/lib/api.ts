// Same-origin requests use the Next.js rewrite to reach FastAPI. Deployments
// can still set NEXT_PUBLIC_API_BASE_URL to an explicitly public API origin.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export async function apiRequest<T>(path: string, init?: RequestInit, timeoutMs?: number): Promise<T> {
  const isGenerationRequest = /\/(quizzes|study-artifacts|chat|assistant|images\/generate)(\/|$|\?)/.test(path);
  const effectiveTimeout = timeoutMs ?? (isGenerationRequest ? 75_000 : 20_000);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), effectiveTimeout);
  try {
    const response = await fetch(`${API_BASE_URL.replace(/\/$/, "")}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { Accept: "application/json", ...init?.headers },
    });
    if (!response.ok) {
      const fallback = `تعذر إكمال الطلب (${response.status}). حاول مرة أخرى.`;
      let message = fallback;
      if (response.status < 500 && response.headers.get("content-type")?.includes("application/json")) {
        try {
          const body: unknown = await response.json();
          if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
            message = body.detail;
          }
        } catch {
          // Keep the safe status-based message when the server error body is invalid.
        }
      }
      throw new Error(message);
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("انتهت مهلة الاتصال بالخادم.");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}
