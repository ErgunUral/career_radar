"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowUpDown,
  BriefcaseBusiness,
  CalendarDays,
  CheckCheck,
  CircleGauge,
  ExternalLink,
  FileSearch,
  LoaderCircle,
  ScanSearch,
  SendHorizontal,
  Sparkles,
} from "lucide-react";

import {
  createApplication,
  getJob,
  getProfile,
  importJob,
  listApplications,
  listJobs,
} from "@/app/lib/api";
import type { ApplicationRecord, JobRecord, WorkMode } from "@/app/lib/types";
import { useCareerRadarStore } from "@/app/stores/onboarding-store";

function readMetadataString(job: JobRecord, key: string) {
  const value = job.metadata?.[key];
  return typeof value === "string" ? value : null;
}

function formatPublishedAt(job: JobRecord) {
  const publishedAt = readMetadataString(job, "published_at") ?? job.created_at;
  const date = new Date(publishedAt);
  if (Number.isNaN(date.getTime())) return "Tarih bilinmiyor";
  return new Intl.DateTimeFormat("tr-TR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

interface JobsConsoleProps {
  onCompleted?: () => void;
}

export function JobsConsole({ onCompleted }: JobsConsoleProps) {
  const {
    userId,
    profile,
    setActiveSection,
    setLastApplication,
    setLastJob,
    setProfile,
  } = useCareerRadarStore();
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [applications, setApplications] = useState<ApplicationRecord[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<JobRecord | null>(null);
  const [dataLoading, setDataLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [applicationLoading, setApplicationLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    search: "",
    sourcePlatform: "all",
    sortBy: "published_at" as "published_at" | "updated_at" | "score" | "company_name" | "title",
    sortOrder: "desc" as "asc" | "desc",
    activeOnly: true,
    publishedWithinDays: "30",
  });
  const [form, setForm] = useState({
    title: "QA Automation Manager",
    company_name: "Radar Fintech",
    source_platform: "manual_import" as
      | "linkedin"
      | "kariyernet"
      | "indeed"
      | "company_page"
      | "manual_import"
      | "email_alert",
    source_url: "https://example.com/jobs/qa-automation-manager",
    location: "Remote",
    work_mode: "remote" as WorkMode,
    language: "İngilizce",
    salary_min: "150000",
    salary_max: "180000",
    raw_text:
      "Fintech şirketi için QA Automation Manager aranıyor. 8 yıl deneyim, 4 yıl liderlik, Python, Jira, Xray, CI/CD, Selenium, Agile ve Scrum deneyimi beklenir.",
  });

  const refreshJobs = useCallback(async () => {
    if (!userId) return;
    try {
      setDataLoading(true);
      const [jobResponse, applicationResponse] = await Promise.all([
        listJobs(userId, {
          activeOnly: filters.activeOnly,
          publishedWithinDays: Number(filters.publishedWithinDays) || undefined,
          sourcePlatform:
            filters.sourcePlatform === "all" ? [] : [filters.sourcePlatform],
          search: filters.search,
          sortBy: filters.sortBy,
          sortOrder: filters.sortOrder,
          dedupe: true,
        }),
        listApplications(userId),
      ]);
      setJobs(jobResponse);
      setApplications(applicationResponse);
      setSelectedJobId((current) => current ?? jobResponse[0]?.id ?? null);
    } catch (refreshError) {
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : "İlan listesi alınamadı.",
      );
    } finally {
      setDataLoading(false);
    }
  }, [filters, userId]);

  useEffect(() => {
    void refreshJobs();
  }, [refreshJobs]);

  const refreshJobDetail = useCallback(async (jobId: string) => {
    try {
      setDetailLoading(true);
      const detail = await getJob(jobId);
      setSelectedJob(detail.job);
    } catch (detailError) {
      setError(
        detailError instanceof Error ? detailError.message : "İlan detay bilgisi alınamadı.",
      );
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedJobId) {
      setSelectedJob(null);
      return;
    }
    void refreshJobDetail(selectedJobId);
  }, [refreshJobDetail, selectedJobId]);

  async function handleImportJob() {
    if (!profile) {
      setError("Önce profili doğrula; ilan analizi için profile_id gereklidir.");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setSuccess(null);
      const freshProfile = await getProfile({ userId }).catch(() => profile);
      if (!freshProfile) {
        throw new Error("Profil doğrulanamadı. Lütfen önce CV ve profil akışını yeniden kaydet.");
      }
      setProfile(freshProfile);
      const created = await importJob({
        user_id: userId,
        profile_id: freshProfile.id,
        title: form.title,
        company_name: form.company_name,
        source_platform: form.source_platform,
        source_url: form.source_url,
        location: form.location,
        work_mode: form.work_mode,
        language: form.language,
        salary_min: Number(form.salary_min),
        salary_max: Number(form.salary_max),
        raw_text: form.raw_text,
      });
      setLastJob(created);
      setSelectedJobId(created.id);
      setSuccess("İlan içe alındı ve profile göre analiz edildi.");
      await refreshJobs();
      onCompleted?.();
    } catch (importError) {
      setError(
        importError instanceof Error
          ? importError.message
          : "İlan import akışı tamamlanamadı.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateApplicationFromJob(job: JobRecord) {
    try {
      setApplicationLoading(true);
      setError(null);
      setSuccess(null);
      const existingApplication = applications.find((application) => application.job_id === job.id);
      if (existingApplication) {
        setLastApplication(existingApplication);
        setActiveSection("applications");
        setSuccess("Bu ilan zaten pipeline içinde. Başvuru ekranına yönlendiriliyorsun.");
        return;
      }

      const created = await createApplication({
        user_id: userId,
        job_id: job.id,
        status: "Başvurulacak",
        notes:
          job.analysis_result?.recommendation_reason ??
          "İlan detay panelinden oluşturuldu. CV özeti role göre güncellenecek.",
        contact_person: "Hiring Team",
        expected_salary: job.parsed_job.salary_max ?? job.parsed_job.salary_min ?? undefined,
      });
      setLastApplication(created);
      setActiveSection("applications");
      setSuccess("İlan başvuru pipeline’ına eklendi. Başvuru ekranına yönlendiriliyorsun.");
      await refreshJobs();
    } catch (applicationError) {
      setError(
        applicationError instanceof Error
          ? applicationError.message
          : "İlan başvuru pipeline’ına eklenemedi.",
      );
    } finally {
      setApplicationLoading(false);
    }
  }

  const highMatchJobs = useMemo(
    () => jobs.filter((job) => (job.analysis_result?.total_score ?? 0) >= 70),
    [jobs],
  );

  const averageScore = useMemo(() => {
    const scoredJobs = jobs.filter((job) => job.analysis_result?.total_score != null);
    if (!scoredJobs.length) return 0;
    const total = scoredJobs.reduce(
      (sum, job) => sum + (job.analysis_result?.total_score ?? 0),
      0,
    );
    return total / scoredJobs.length;
  }, [jobs]);

  const applicationsByJobId = useMemo(
    () => new Map(applications.map((application) => [application.job_id, application])),
    [applications],
  );

  return (
    <section className="grid gap-6 xl:grid-cols-[0.88fr_1.12fr]">
      <div className="rounded-[32px] border border-white/10 bg-[rgba(9,15,30,0.88)] p-6 shadow-[0_18px_60px_rgba(2,8,20,0.35)]">
        <div className="flex items-center gap-3">
          <BriefcaseBusiness className="h-5 w-5 text-emerald-200" />
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-slate-500">Adım 3</p>
            <h2 className="mt-2 font-display text-3xl text-white">
              İlan içe al ve analiz et.
            </h2>
          </div>
        </div>
        <p className="mt-4 text-sm leading-6 text-slate-300">
          Kullanıcı tarafından sağlanan ilan metni veya bağlantısı buradan sisteme alınır.
          Backend, ilanın yapısal alanlarını çıkarır ve seçili profil ile eşleştirme
          skorunu üretir.
        </p>

        <div className="mt-6 grid gap-4">
          {Object.entries(form).map(([key, value]) => (
            <label key={key}>
              <span className="mb-2 block text-xs uppercase tracking-[0.22em] text-slate-500">
                {key.replaceAll("_", " ")}
              </span>
              {key === "raw_text" ? (
                <textarea
                  className="min-h-32 w-full rounded-[24px] border border-white/10 bg-slate-950/80 px-4 py-3 text-sm leading-6 text-white outline-none transition focus:border-emerald-300/40"
                  onChange={(event) =>
                    setForm((current) => ({ ...current, [key]: event.target.value }))
                  }
                  value={value}
                />
              ) : (
                <input
                  className="h-12 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 text-sm text-white outline-none transition focus:border-emerald-300/40"
                  onChange={(event) =>
                    setForm((current) => ({ ...current, [key]: event.target.value }))
                  }
                  value={value}
                />
              )}
            </label>
          ))}
        </div>

        <button
          className="mt-6 inline-flex h-12 items-center gap-2 rounded-full bg-emerald-300 px-5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
          disabled={loading}
          onClick={handleImportJob}
          type="button"
        >
          {loading ? (
            <LoaderCircle className="h-4 w-4 animate-spin" />
          ) : (
            <ScanSearch className="h-4 w-4" />
          )}
          İlanı İçe Al ve Analiz Et
        </button>

        {error ? <p className="mt-4 text-sm text-rose-300">{error}</p> : null}
        {success ? <p className="mt-4 text-sm text-emerald-200">{success}</p> : null}
      </div>

      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5">
            <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Toplam İlan</p>
            <p className="mt-3 text-3xl font-semibold text-white">{dataLoading ? "..." : jobs.length}</p>
          </div>
          <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5">
            <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Yüksek Uyum</p>
            <p className="mt-3 text-3xl font-semibold text-white">
              {dataLoading ? "..." : highMatchJobs.length}
            </p>
          </div>
          <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5">
            <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Hazır Profil</p>
            <p className="mt-3 text-3xl font-semibold text-white">{profile ? "1" : "0"}</p>
          </div>
          <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5">
            <p className="text-xs uppercase tracking-[0.24em] text-slate-500">
              Ortalama Skor
            </p>
            <p className="mt-3 text-3xl font-semibold text-white">
              {dataLoading ? "..." : averageScore ? averageScore.toFixed(1) : "0.0"}
            </p>
          </div>
        </div>

        <div className="grid gap-6 2xl:grid-cols-[1.05fr_0.95fr]">
          <div className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <Sparkles className="h-5 w-5 text-emerald-200" />
                <h3 className="text-lg font-semibold text-white">Aktif ve yeni ilanlar</h3>
              </div>
              <button
                className="rounded-full border border-white/10 px-4 py-2 text-xs text-slate-300 transition hover:border-emerald-300/40 hover:text-white"
                onClick={() => void refreshJobs()}
                type="button"
              >
                Yenile
              </button>
            </div>

            <div className="mt-5 grid gap-3 lg:grid-cols-2">
              <input
                className="h-11 rounded-2xl border border-white/10 bg-slate-950/80 px-4 text-sm text-white outline-none transition focus:border-emerald-300/40"
                onChange={(event) =>
                  setFilters((current) => ({ ...current, search: event.target.value }))
                }
                placeholder="Pozisyon, şirket veya yetkinlik ara"
                value={filters.search}
              />
              <div className="grid gap-3 md:grid-cols-2">
                <select
                  className="h-11 rounded-2xl border border-white/10 bg-slate-950/80 px-4 text-sm text-white outline-none transition focus:border-emerald-300/40"
                  onChange={(event) =>
                    setFilters((current) => ({ ...current, sourcePlatform: event.target.value }))
                  }
                  value={filters.sourcePlatform}
                >
                  <option value="all">Tüm kaynaklar</option>
                  <option value="linkedin">LinkedIn</option>
                  <option value="kariyernet">Kariyer.net</option>
                  <option value="indeed">Indeed</option>
                  <option value="company_page">Şirket kariyer sayfası</option>
                  <option value="manual_import">Manuel</option>
                </select>
                <select
                  className="h-11 rounded-2xl border border-white/10 bg-slate-950/80 px-4 text-sm text-white outline-none transition focus:border-emerald-300/40"
                  onChange={(event) =>
                    setFilters((current) => ({
                      ...current,
                      sortBy: event.target.value as typeof current.sortBy,
                    }))
                  }
                  value={filters.sortBy}
                >
                  <option value="published_at">Yayın tarihi</option>
                  <option value="score">Uyum skoru</option>
                  <option value="updated_at">Güncellenme</option>
                  <option value="company_name">Şirket</option>
                  <option value="title">Pozisyon</option>
                </select>
              </div>
              <div className="grid gap-3 md:grid-cols-[1fr_1fr]">
                <select
                  className="h-11 rounded-2xl border border-white/10 bg-slate-950/80 px-4 text-sm text-white outline-none transition focus:border-emerald-300/40"
                  onChange={(event) =>
                    setFilters((current) => ({
                      ...current,
                      sortOrder: event.target.value as typeof current.sortOrder,
                    }))
                  }
                  value={filters.sortOrder}
                >
                  <option value="desc">Azalan</option>
                  <option value="asc">Artan</option>
                </select>
                <input
                  className="h-11 rounded-2xl border border-white/10 bg-slate-950/80 px-4 text-sm text-white outline-none transition focus:border-emerald-300/40"
                  onChange={(event) =>
                    setFilters((current) => ({
                      ...current,
                      publishedWithinDays: event.target.value,
                    }))
                  }
                  placeholder="Gün"
                  value={filters.publishedWithinDays}
                />
              </div>
              <button
                className={`inline-flex h-11 items-center justify-center gap-2 rounded-2xl border px-4 text-sm transition ${
                  filters.activeOnly
                    ? "border-emerald-300/40 bg-emerald-300/10 text-emerald-100"
                    : "border-white/10 bg-slate-950/70 text-slate-300"
                }`}
                onClick={() =>
                  setFilters((current) => ({ ...current, activeOnly: !current.activeOnly }))
                }
                type="button"
              >
                <ArrowUpDown className="h-4 w-4" />
                Yalnız aktif ilanlar
              </button>
            </div>

            <div className="mt-5 space-y-4">
              {dataLoading ? (
                <article className="rounded-[24px] border border-white/10 bg-slate-950/70 p-5">
                  <div className="h-4 w-40 animate-pulse rounded bg-white/10" />
                  <div className="mt-3 h-3 w-28 animate-pulse rounded bg-white/10" />
                  <div className="mt-5 h-20 animate-pulse rounded bg-white/5" />
                </article>
              ) : null}
              {jobs.map((job) => (
                <article
                  className={`rounded-[24px] border p-5 transition ${
                    job.id === selectedJobId
                      ? "border-emerald-300/40 bg-emerald-300/[0.08]"
                      : "border-white/10 bg-slate-950/70"
                  }`}
                  key={job.id}
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <p className="text-sm font-semibold text-white">{job.title}</p>
                      <p className="mt-1 text-xs text-slate-400">
                        {job.company_name} • {job.location} • {job.work_mode}
                      </p>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
                        <span className="inline-flex items-center gap-1">
                          <CalendarDays className="h-3.5 w-3.5" />
                          {formatPublishedAt(job)}
                        </span>
                        <span>•</span>
                        <span>{job.source_platform}</span>
                        {job.source_url ? (
                          <>
                            <span>•</span>
                            <a
                              className="inline-flex items-center gap-1 text-emerald-200 hover:text-emerald-100"
                              href={job.source_url}
                              rel="noreferrer"
                              target="_blank"
                            >
                              Başvuru Linki
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          </>
                        ) : null}
                      </div>
                      {applicationsByJobId.get(job.id) ? (
                        <p className="mt-2 text-xs text-emerald-200">
                          Pipeline durumu: {applicationsByJobId.get(job.id)?.status}
                        </p>
                      ) : null}
                    </div>
                    <div className="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1.5 text-xs text-emerald-100">
                      Skor {job.analysis_result?.total_score?.toFixed(2) ?? "Bekliyor"}
                    </div>
                  </div>

                  <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_0.9fr]">
                    <div>
                      <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                        Eşleşen Yetkinlikler
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {(job.analysis_result?.matched_keywords ?? job.parsed_job.required_skills).map(
                          (item) => (
                            <span
                              className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-slate-200"
                              key={item}
                            >
                              {item}
                            </span>
                          ),
                        )}
                      </div>
                    </div>

                    <div>
                      <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                        Başvuru Önerisi
                      </p>
                      <div className="mt-3 rounded-[20px] border border-white/10 bg-white/[0.03] p-4">
                        <div className="flex items-center gap-2 text-emerald-200">
                          <CheckCheck className="h-4 w-4" />
                          <span className="text-sm font-medium text-white">
                            {job.analysis_result?.recommendation ?? "Analiz bekleniyor"}
                          </span>
                        </div>
                        <p className="mt-3 text-xs leading-5 text-slate-400">
                          {job.analysis_result?.recommendation_reason ??
                            "İlan parse edildiğinde öneri nedeni burada görünür."}
                        </p>
                      </div>
                    </div>
                  </div>

                  <button
                    className="mt-4 inline-flex items-center gap-2 rounded-full border border-white/10 px-4 py-2 text-xs text-slate-200 transition hover:border-emerald-300/40 hover:bg-emerald-300/10"
                    onClick={() => setSelectedJobId(job.id)}
                    type="button"
                  >
                    <FileSearch className="h-3.5 w-3.5" />
                    Detayı Aç
                  </button>
                </article>
              ))}
              {!dataLoading && !jobs.length ? (
                <div className="rounded-[24px] border border-dashed border-white/10 bg-slate-950/60 p-5">
                  <p className="text-sm font-medium text-white">
                    Filtreye uygun aktif ilan bulunmuyor.
                  </p>
                  <p className="mt-2 text-sm text-slate-400">
                    Süresi dolmuş veya başvuruya kapanmış ilanlar otomatik gizlenir. Yeni canlı
                    keşif çalıştırabilir ya da filtreyi genişletebilirsin.
                  </p>
                </div>
              ) : null}
            </div>
          </div>

          <div className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
            <div className="flex items-center gap-3">
              <CircleGauge className="h-5 w-5 text-emerald-200" />
              <h3 className="text-lg font-semibold text-white">İlan detay paneli</h3>
            </div>
            {dataLoading || detailLoading ? (
              <div className="mt-6 inline-flex items-center gap-2 text-sm text-slate-300">
                <LoaderCircle className="h-4 w-4 animate-spin" />
                {dataLoading ? "İlanlar yükleniyor..." : "Detay yükleniyor..."}
              </div>
            ) : selectedJob ? (
              <div className="mt-5 space-y-4">
                <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-5">
                  <p className="text-xl font-semibold text-white">{selectedJob.title}</p>
                  <p className="mt-2 text-sm text-slate-400">
                    {selectedJob.company_name} • {selectedJob.location} • {selectedJob.source_platform}
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-400">
                    <span>Yayın tarihi: {formatPublishedAt(selectedJob)}</span>
                    {selectedJob.source_url ? (
                      <a
                        className="inline-flex items-center gap-1 text-emerald-200 hover:text-emerald-100"
                        href={selectedJob.source_url}
                        rel="noreferrer"
                        target="_blank"
                      >
                        Başvuru linkini aç
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    ) : null}
                  </div>
                  {applicationsByJobId.get(selectedJob.id) ? (
                    <div className="mt-4 inline-flex rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1.5 text-xs text-emerald-100">
                      Pipeline: {applicationsByJobId.get(selectedJob.id)?.status}
                    </div>
                  ) : null}
                  <p className="mt-4 text-sm leading-6 text-slate-300">
                    {selectedJob.parsed_job.description || selectedJob.raw_text}
                  </p>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                      Zorunlu Yetkinlikler
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {selectedJob.parsed_job.required_skills.map((skill) => (
                        <span
                          className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-slate-200"
                          key={skill}
                        >
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                      Eksik Yetkinlikler
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {(selectedJob.analysis_result?.missing_keywords ?? []).map((skill) => (
                        <span
                          className="rounded-full border border-rose-300/20 bg-rose-300/10 px-3 py-2 text-xs text-rose-100"
                          key={skill}
                        >
                          {skill}
                        </span>
                      ))}
                      {!(selectedJob.analysis_result?.missing_keywords ?? []).length ? (
                        <span className="text-sm text-slate-400">
                          Kritik açık görünmüyor veya detay analiz henüz yok.
                        </span>
                      ) : null}
                    </div>
                  </div>
                </div>

                <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-5">
                  <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                    Analiz özeti
                  </p>
                  <div className="mt-4 grid gap-4 md:grid-cols-3">
                    <div>
                      <p className="text-xs text-slate-500">Toplam skor</p>
                      <p className="mt-1 text-2xl font-semibold text-white">
                        {selectedJob.analysis_result?.total_score?.toFixed(2) ?? "Bekliyor"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Semantic alignment</p>
                      <p className="mt-1 text-2xl font-semibold text-white">
                        {selectedJob.analysis_result?.breakdown.semantic_alignment?.toFixed(2) ??
                          "0.00"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Öneri</p>
                      <p className="mt-1 text-sm font-semibold text-white">
                        {selectedJob.analysis_result?.recommendation ?? "Analiz bekleniyor"}
                      </p>
                    </div>
                  </div>
                  <div className="mt-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                      Güçlü yönler
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {(selectedJob.analysis_result?.strengths ?? []).map((item) => (
                        <span
                          className="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-2 text-xs text-emerald-100"
                          key={item}
                        >
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-5">
                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div>
                      <p className="text-sm font-semibold text-white">Pipeline aksiyonu</p>
                      <p className="mt-2 text-sm text-slate-400">
                        Seçili ilanı doğrudan başvuru operasyon hattına taşı.
                      </p>
                    </div>
                    <button
                      className="inline-flex h-11 items-center gap-2 rounded-full bg-emerald-300 px-5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
                      disabled={applicationLoading}
                      onClick={() => void handleCreateApplicationFromJob(selectedJob)}
                      type="button"
                    >
                      {applicationLoading ? (
                        <LoaderCircle className="h-4 w-4 animate-spin" />
                      ) : (
                        <SendHorizontal className="h-4 w-4" />
                      )}
                      {applicationsByJobId.get(selectedJob.id)
                        ? "Başvuruya Git"
                        : "Pipeline’a Ekle"}
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-400">
                Listeden bir ilan seçildiğinde detay paneli burada görünür.
              </p>
            )}
            </div>
        </div>
      </div>
    </section>
  );
}
