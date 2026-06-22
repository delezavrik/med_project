import type { AnswerResponse, ChatAskRequest, TemplateExecuteRequest } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

async function postJson<TResponse>(path: string, body: unknown): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API error ${response.status}: ${text}`);
  }

  return response.json() as Promise<TResponse>;
}

export async function executeTemplate(
  templateId: string,
  request: TemplateExecuteRequest,
): Promise<AnswerResponse> {
  return postJson<AnswerResponse>(`/templates/${templateId}/execute`, request);
}

export async function askChat(request: ChatAskRequest): Promise<AnswerResponse> {
  return postJson<AnswerResponse>("/chat/ask", request);
}
