const INTERNAL_ORIGIN = "http://next.local";

/** Accept only same-origin relative paths for post-authentication navigation. */
export function getSafeNextPath(candidate: string | null | undefined): string {
  if (
    !candidate ||
    !candidate.startsWith("/") ||
    candidate.startsWith("//") ||
    candidate.includes("\\") ||
    /[\u0000-\u001f]/.test(candidate)
  ) {
    return "/subjects";
  }

  try {
    const target = new URL(candidate, INTERNAL_ORIGIN);
    if (target.origin !== INTERNAL_ORIGIN || target.pathname === "/login") {
      return "/subjects";
    }
    return `${target.pathname}${target.search}${target.hash}`;
  } catch {
    return "/subjects";
  }
}
