export type WorkMode = "remote" | "hybrid" | "onsite";

export type NotificationChannel = "in_app" | "email";

export type SectionKey =
  | "overview"
  | "profile"
  | "watchers"
  | "recommended"
  | "jobs"
  | "applications";

export interface CandidateProfileInput {
  candidate_id?: string | null;
  headline: string;
  summary: string;
  total_experience_years: number;
  management_years: number;
  team_size_managed: number;
  skills: string[];
  industries: string[];
  languages: string[];
  certifications: string[];
  educations: string[];
  preferred_locations: string[];
  work_modes: WorkMode[];
  salary_expectation?: number | null;
  raw_text?: string;
  metadata?: Record<string, unknown>;
}

export interface CandidateProfileRecord {
  id: string;
  user_id: string;
  cv_file_id?: string | null;
  professional_summary: string;
  target_positions: string[];
  profile: CandidateProfileInput;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
}

export interface CvFileRecord {
  id: string;
  user_id: string;
  filename: string;
  content_type: string;
  storage_path: string;
  language: string;
  parse_status: "uploaded" | "parsed" | "failed";
  extracted_text?: string | null;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
}

export interface WatcherRecord {
  id: string;
  user_id: string;
  query_name: string;
  source_platform: string;
  search_criteria?: SearchCriteria;
  candidate_profile?: CandidateProfileInput;
  minimum_match_score: number;
  sync_frequency_minutes: number;
  notification_channels: NotificationChannel[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_synced_at?: string | null;
  metadata?: Record<string, unknown>;
}

export interface ScoreBreakdown {
  title: number;
  experience: number;
  technical_skills: number;
  leadership: number;
  industry: number;
  location_and_work_mode: number;
  language: number;
  education_and_certificates: number;
  salary_and_benefits: number;
  semantic_alignment: number;
}

export interface MatchResult {
  job_id: string;
  total_score: number;
  recommendation: string;
  recommendation_reason: string;
  semantic_similarity: number;
  breakdown: ScoreBreakdown;
  strengths: string[];
  gaps: string[];
  matched_keywords: string[];
  missing_keywords: string[];
  privacy_notes: string[];
}

export interface ParsedJob {
  job_id: string;
  title: string;
  description: string;
  requirements: string;
  required_skills: string[];
  preferred_skills: string[];
  industries: string[];
  min_years_experience: number;
  management_years_required: number;
  location: string;
  work_mode: WorkMode;
  language_requirement: string;
  salary_max?: number | null;
  salary_min?: number | null;
  education_requirements: string[];
  certification_requirements: string[];
  raw_text: string;
  metadata?: Record<string, unknown>;
}

export interface SearchCriteria {
  keywords: string[];
  locations: string[];
  industries: string[];
  work_modes: WorkMode[];
  min_experience_years?: number | null;
  max_experience_years?: number | null;
  position_types: string[];
}

export interface JobRecord {
  id: string;
  user_id: string;
  profile_id?: string | null;
  title: string;
  company_name: string;
  source_platform: string;
  source_url?: string | null;
  location: string;
  work_mode: WorkMode;
  language: string;
  raw_text: string;
  parsed_job: ParsedJob;
  analysis_result?: MatchResult | null;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
}

export interface JobListFilters {
  activeOnly?: boolean;
  publishedWithinDays?: number;
  sourcePlatform?: string[];
  search?: string;
  sortBy?: "published_at" | "updated_at" | "score" | "company_name" | "title";
  sortOrder?: "asc" | "desc";
  dedupe?: boolean;
}

export interface ApplicationRecord {
  id: string;
  user_id: string;
  job_id: string;
  status: string;
  notes: string;
  contact_person: string;
  expected_salary?: number | null;
  offered_salary?: number | null;
  reminder_at?: string | null;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
}

export interface ArchiveRecord {
  user_id: string;
  watcher_id: string;
  job_id: string;
  title: string;
  company_name: string;
  location: string;
  source_platform: string;
  first_seen_at: string;
  last_seen_at: string;
  notification_sent: boolean;
  notifications_sent: number;
  last_match_score: number;
  last_recommendation: string;
  metadata?: Record<string, unknown>;
}

export interface NotificationRecord {
  id: string;
  user_id: string;
  watcher_id: string;
  job_id: string;
  channel: NotificationChannel;
  title: string;
  message: string;
  created_at: string;
  is_read: boolean;
  metadata?: Record<string, unknown>;
}

export interface SyncRunRecord {
  id: string;
  watcher_id: string;
  user_id: string;
  status: "queued" | "running" | "completed" | "failed";
  started_at: string;
  finished_at?: string | null;
  processed_jobs: number;
  matched_jobs: number;
  notifications_created: number;
  error_message?: string | null;
  metadata?: Record<string, unknown>;
}

export interface WatcherRunResponse {
  watcher: WatcherRecord;
  run: SyncRunRecord;
  archived_jobs: ArchiveRecord[];
  notifications: NotificationRecord[];
}

export interface DiscoverySourceReport {
  source_url: string;
  source_platform?: string | null;
  fetched_jobs: number;
  status: string;
  search_performed?: boolean;
  verification_note?: string | null;
  error_message?: string | null;
}

export interface WatcherDiscoverPayload {
  triggered_by?: string;
  source_urls?: string[];
  max_jobs?: number;
}

export interface WatcherDiscoverResponse {
  watcher: WatcherRecord;
  run: SyncRunRecord;
  archived_jobs: ArchiveRecord[];
  notifications: NotificationRecord[];
  imported_jobs: JobRecord[];
  source_reports: DiscoverySourceReport[];
}

export interface ArchiveJobDetailResponse {
  archive: ArchiveRecord;
  notifications: NotificationRecord[];
}

export interface JobDetailResponse {
  job: JobRecord;
}

export interface WatcherRunPayload {
  triggered_by?: string;
  jobs: ParsedJob[];
}

export interface WatcherCreatePayload {
  user_id: string;
  query_name: string;
  source_platform: "linkedin_search_url" | "linkedin_alert" | "email_forward" | "manual_import";
  profile_id?: string;
  search_criteria: {
    keywords: string[];
    locations: string[];
    industries: string[];
    work_modes: WorkMode[];
    min_experience_years?: number;
    max_experience_years?: number;
    position_types: string[];
  };
  minimum_match_score: number;
  sync_frequency_minutes: number;
  notification_channels: NotificationChannel[];
  metadata?: Record<string, unknown>;
}

export interface JobImportPayload {
  user_id: string;
  profile_id?: string;
  title: string;
  company_name: string;
  source_platform:
    | "linkedin"
    | "kariyernet"
    | "indeed"
    | "company_page"
    | "manual_import"
    | "email_alert";
  source_url?: string;
  location: string;
  work_mode?: WorkMode;
  language: string;
  raw_text: string;
  salary_min?: number;
  salary_max?: number;
}

export interface ApplicationCreatePayload {
  user_id: string;
  job_id: string;
  status: string;
  notes?: string;
  contact_person?: string;
  expected_salary?: number;
  offered_salary?: number;
}
