export async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init.headers },
      signal: init.signal ?? AbortSignal.timeout(35000),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new Error(
      "Cannot reach the Python server. Start the workspace with python3 scripts/dev.py and retry.",
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    if (typeof body?.detail === "string") throw new Error(body.detail);
    if (Array.isArray(body?.detail)) {
      throw new Error(
        body.detail
          .map(
            (issue: { loc?: string[]; msg?: string }) =>
              `${issue.loc?.slice(1).join(".") || "Project"}: ${issue.msg || "Invalid value"}`,
          )
          .join("; "),
      );
    }
    throw new Error(
      `The server returned ${response.status}. Your changes have not been saved.`,
    );
  }
  return response.json() as Promise<T>;
}
