import type {
  ArchiveJobDetailResponse,
  ArchiveRecord,
  ApplicationCreatePayload,
  ApplicationRecord,
  CandidateProfileRecord,
  CvFileRecord,
  WatcherDiscoverPayload,
  WatcherDiscoverResponse,
  JobDetailResponse,
  JobImportPayload,
  JobListFilters,
  JobRecord,
  NotificationRecord,
  SyncRunRecord,
  WatcherCreatePayload,
  WatcherRecord,
  WatcherRunPayload,
  WatcherRunResponse,
} from "@/app/lib/types";

function formatApiErrorMessage(detail: string): string {
  try {
    const parsed = JSON.parse(detail) as {
      error?: { message?: string };
      detail?: string;
    };
    return parsed.error?.message ?? parsed.detail ?? detail;
  } catch {
    return detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(formatApiErrorMessage(detail || "API isteği başarısız oldu."));
  }

  return (await response.json()) as T;
}

export async function uploadCv(params: {
  file: File;
  userId: string;
  language: string;
}) {
  const formData = new FormData();
  formData.append("file", params.file);
  formData.append("user_id", params.userId);
  formData.append("language", params.language);
  return request<{ file: CvFileRecord }>("/api/v1/files/cv", {
    method: "POST",
    body: formData,
  });
}

export async function parseCv(fileId: string) {
  return request<CandidateProfileRecord>("/api/v1/cv/parse", {
    method: "POST",
    body: JSON.stringify({ file_id: fileId }),
  });
}

export async function getProfile(params: { profileId?: string; userId?: string }) {
  const query = new URLSearchParams();
  if (params.profileId) query.set("profile_id", params.profileId);
  if (params.userId) query.set("user_id", params.userId);
  return request<CandidateProfileRecord>(`/api/v1/profile?${query.toString()}`);
}

export async function updateProfile(
  profileId: string,
  payload: Record<string, unknown>,
) {
  return request<CandidateProfileRecord>(`/api/v1/profile/${profileId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function createWatcher(payload: WatcherCreatePayload) {
  return request<WatcherRecord>("/api/v1/watchers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listWatchers() {
  return request<WatcherRecord[]>("/api/v1/watchers");
}

export async function runWatcher(watcherId: string, payload: WatcherRunPayload) {
  return request<WatcherRunResponse>(`/api/v1/watchers/${watcherId}/run`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function discoverWatcher(watcherId: string, payload: WatcherDiscoverPayload) {
  return request<WatcherDiscoverResponse>(`/api/v1/watchers/${watcherId}/discover`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listWatcherRuns(watcherId: string) {
  return request<SyncRunRecord[]>(`/api/v1/watchers/${watcherId}/runs`);
}

export async function listNotifications(userId: string) {
  const query = new URLSearchParams({ user_id: userId });
  return request<NotificationRecord[]>(`/api/v1/notifications?${query.toString()}`);
}

export async function listArchive(userId: string) {
  const query = new URLSearchParams({ user_id: userId });
  return request<ArchiveRecord[]>(`/api/v1/archive/jobs?${query.toString()}`);
}

export async function getArchiveDetail(jobId: string, userId: string) {
  const query = new URLSearchParams({ user_id: userId });
  return request<ArchiveJobDetailResponse>(`/api/v1/archive/jobs/${jobId}?${query.toString()}`);
}

export async function importJob(payload: JobImportPayload) {
  return request<JobRecord>("/api/v1/jobs/import", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listJobs(userId: string, filters?: JobListFilters) {
  const query = new URLSearchParams({ user_id: userId });
  if (filters?.activeOnly) query.set("active_only", "true");
  if (filters?.publishedWithinDays) {
    query.set("published_within_days", String(filters.publishedWithinDays));
  }
  if (filters?.search?.trim()) query.set("search", filters.search.trim());
  if (filters?.sortBy) query.set("sort_by", filters.sortBy);
  if (filters?.sortOrder) query.set("sort_order", filters.sortOrder);
  if (filters?.dedupe) query.set("dedupe", "true");
  for (const platform of filters?.sourcePlatform ?? []) {
    query.append("source_platform", platform);
  }
  return request<JobRecord[]>(`/api/v1/jobs?${query.toString()}`);
}

export async function getJob(jobId: string) {
  return request<JobDetailResponse>(`/api/v1/jobs/${jobId}`);
}

export async function createApplication(payload: ApplicationCreatePayload) {
  return request<ApplicationRecord>("/api/v1/applications", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listApplications(userId: string) {
  const query = new URLSearchParams({ user_id: userId });
  return request<ApplicationRecord[]>(`/api/v1/applications?${query.toString()}`);
}

export async function updateApplication(
  applicationId: string,
  payload: Record<string, unknown>,
) {
  return request<ApplicationRecord>(`/api/v1/applications/${applicationId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
