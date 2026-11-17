import { getApiUrl } from "../config";
import { buildAuthHeaders } from "../authHeaders";

export interface StudentAccount {
  id: string;
  username: string;
  created_at: number;
}

export interface TutorMaterial {
  id: string;
  title: string;
  subject: string;
  grade: number;
  content?: string;
  created_at: number;
}

export interface TutorQuestion {
  prompt: string;
  options: string[];
}

export interface TutorQuiz {
  id: string;
  subject: string;
  topic: string;
  grade: number;
  difficulty: string;
  questions: TutorQuestion[];
}

export interface StudyTask {
  date: string;
  title: string;
  focus: string;
  activity: string;
  minutes: number;
  completed: boolean;
  completed_at: number | null;
}

export interface StudyPlan {
  id: string;
  subject: string;
  grade: number;
  goal: string;
  tasks: StudyTask[];
  created_at: number;
}

export interface StudyProgress {
  subject: string;
  topic: string;
  correct: number;
  total: number;
  attempts: number;
  accuracy: number;
  last_practiced: number;
}

export interface LearningHistoryItem {
  id: string;
  kind: string;
  subject: string;
  topic: string;
  prompt: string;
  response: string;
  created_at: number;
  sources: { title: string; excerpt: string }[];
}

async function call<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(buildAuthHeaders());
  new Headers(options.headers).forEach((value, key) =>
    headers.set(key, value),
  );
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(getApiUrl(path), { ...options, headers });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // Keep the HTTP status message when the response is not JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export const learningTutorApi = {
  me: () => call<StudentAccount>("/learning/auth/me"),
  ask: (input: {
    question: string;
    subject: string;
    grade: number;
    topic: string;
    mode: "question" | "explanation";
  }) =>
    call<{
      id: string;
      answer: string;
      sources: { title: string; excerpt: string }[];
    }>("/learning/ask", { method: "POST", body: JSON.stringify(input) }),
  history: () => call<LearningHistoryItem[]>("/learning/history"),
  materials: () => call<TutorMaterial[]>("/learning/materials"),
  addMaterial: (input: {
    subject: string;
    grade: number;
    title: string;
    content: string;
  }) =>
    call<TutorMaterial>("/learning/materials", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  deleteMaterial: (id: string) =>
    call<{ deleted: boolean }>(`/learning/materials/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
  createQuiz: (input: {
    subject: string;
    topic: string;
    grade: number;
    difficulty: "easy" | "medium" | "hard";
    count: number;
  }) =>
    call<TutorQuiz>("/learning/quizzes", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  submitQuiz: (id: string, answers: number[]) =>
    call<{
      score: number;
      total: number;
      feedback: {
        question_index: number;
        correct: boolean;
        correct_index: number;
        explanation: string;
      }[];
    }>(`/learning/quizzes/${encodeURIComponent(id)}/submit`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    }),
  plans: () => call<StudyPlan[]>("/learning/plans"),
  createPlan: (input: {
    subject: string;
    grade: number;
    goal: string;
    start_date: string;
    days: number;
    daily_minutes: number;
    weekdays: number[];
  }) =>
    call<StudyPlan>("/learning/plans", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  completeTask: (planId: string, taskIndex: number, completed: boolean) =>
    call<StudyPlan>(
      `/learning/plans/${encodeURIComponent(planId)}/tasks/${taskIndex}`,
      { method: "PATCH", body: JSON.stringify({ completed }) },
    ),
  progress: () =>
    call<{
      topics: StudyProgress[];
      recommendations: {
        subject: string;
        topic: string;
        accuracy: number;
        reason: string;
      }[];
    }>("/learning/progress"),
};
