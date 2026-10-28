"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CheckCheck,
  CircleGauge,
  LoaderCircle,
  SendHorizontal,
  Sparkles,
} from "lucide-react";

import { createApplication, listApplications, listJobs } from "@/app/lib/api";
import type { ApplicationRecord, JobRecord } from "@/app/lib/types";
import { useCareerRadarStore } from "@/app/stores/onboarding-store";

const PRIORITY_RECOMMENDATIONS = new Set([
  "Hemen başvur",
  "Yüksek öncelikli",
  "Değerlendirilebilir",
]);

function sortByScore(jobs: JobRecord[]) {
  return [...jobs].sort(
    (left, right) =>
      (right.analysis_result?.total_score ?? 0) - (left.analysis_result?.total_score ?? 0),
  );
}

export function RecommendedJobsConsole() {
  const { userId, setActiveSection, setLastApplication, setLastJob } = useCareerRadarStore();
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [applications, setApplications] = useState<ApplicationRecord[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const refreshData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [jobResponse, applicationResponse] = await Promise.all([
        listJobs(userId, {
          activeOnly: true,
          publishedWithinDays: 30,
          dedupe: true,
          sortBy: "score",
          sortOrder: "desc",
        }),
        listApplications(userId),
      ]);
      setJobs(jobResponse);
      setApplications(applicationResponse);
      const recommended = sortByScore(
        jobResponse.filter((job) => {
          const score = job.analysis_result?.total_score ?? 0;
          const recommendation = job.analysis_result?.recommendation ?? "";
          return score >= 70 || PRIORITY_RECOMMENDATIONS.has(recommendation);
        }),
      );
      setSelectedJobId((current) => current ?? recommended[0]?.id ?? null);
    } catch (refreshError) {
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : "Önerilen ilanlar alınamadı.",
      );
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    void refreshData();
  }, [refreshData]);

  const recommendedJobs = useMemo(
    () =>
      sortByScore(
        jobs.filter((job) => {
          const score = job.analysis_result?.total_score ?? 0;
          const recommendation = job.analysis_result?.recommendation ?? "";
          return score >= 70 || PRIORITY_RECOMMENDATIONS.has(recommendation);
        }),
      ),
    [jobs],
  );

  const selectedJob =
    recommendedJobs.find((job) => job.id === selectedJobId) ?? recommendedJobs[0] ?? null;

  const applicationsByJobId = useMemo(
    () => new Map(applications.map((application) => [application.job_id, application])),
    [applications],
  );

  const readyForApplicationCount = useMemo(
    () =>
      recommendedJobs.filter((job) => !applicationsByJobId.has(job.id)).length,
    [applicationsByJobId, recommendedJobs],
  );

  const averageScore = useMemo(() => {
    if (!recommendedJobs.length) return 0;
    const total = recommendedJobs.reduce(
      (sum, job) => sum + (job.analysis_result?.total_score ?? 0),
      0,
    );
    return total / recommendedJobs.length;
  }, [recommendedJobs]);

  async function handlePipelineAction(job: JobRecord) {
    try {
      setActionLoading(true);
      setError(null);
      setSuccess(null);
      setLastJob(job);
      const existingApplication = applicationsByJobId.get(job.id);
      if (existingApplication) {
        setLastApplication(existingApplication);
        setActiveSection("applications");
        setSuccess("İlan zaten pipeline içinde. Başvurularım ekranına yönlendiriliyorsun.");
        return;
      }

      const created = await createApplication({
        user_id: userId,
        job_id: job.id,
        status: "Başvurulacak",
        notes:
          job.analysis_result?.recommendation_reason ??
          "Önerilen ilanlar ekranından pipeline’a eklendi.",
        contact_person: "Hiring Team",
        expected_salary: job.parsed_job.salary_max ?? job.parsed_job.salary_min ?? undefined,
      });
      setLastApplication(created);
      setActiveSection("applications");
      setSuccess("İlan pipeline’a eklendi. Başvurularım ekranına yönlendiriliyorsun.");
      await refreshData();
    } catch (actionError) {
      setError(
        actionError instanceof Error
          ? actionError.message
          : "Önerilen ilan pipeline’a eklenemedi.",
      );
    } finally {
      setActionLoading(false);
    }
  }

  return (
    <section className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5">
          <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Önerilen İlan</p>
          <p className="mt-3 text-3xl font-semibold text-white">
            {loading ? "..." : recommendedJobs.length}
          </p>
        </div>
        <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5">
          <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Ortalama Skor</p>
          <p className="mt-3 text-3xl font-semibold text-white">
            {loading ? "..." : averageScore.toFixed(1)}
          </p>
        </div>
        <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5">
          <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Başvuruya Hazır</p>
          <p className="mt-3 text-3xl font-semibold text-white">
            {loading ? "..." : readyForApplicationCount}
          </p>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="rounded-[32px] border border-white/10 bg-[rgba(9,15,30,0.88)] p-6 shadow-[0_18px_60px_rgba(2,8,20,0.35)]">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <Sparkles className="h-5 w-5 text-emerald-200" />
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                  Öneri Motoru
                </p>
                <h2 className="mt-2 font-display text-3xl text-white">
                  Başvuruya en yakın ilanlar
                </h2>
              </div>
            </div>
            <button
              className="rounded-full border border-white/10 px-4 py-2 text-xs text-slate-300 transition hover:border-emerald-300/40 hover:text-white"
              onClick={() => setActiveSection("jobs")}
              type="button"
            >
              Tüm ilanlara git
            </button>
          </div>

          <p className="mt-4 text-sm leading-6 text-slate-300">
            Bu ekran yalnızca yüksek uyumlu veya sistemin doğrudan değerlendirmeye değer
            gördüğü ilanları ayırır. Böylece tüm job havuzu yerine aksiyona en yakın
            fırsatlara odaklanabilirsin.
          </p>

          <div className="mt-5 space-y-4">
            {loading ? (
              <article className="rounded-[24px] border border-white/10 bg-slate-950/70 p-5">
                <div className="h-4 w-40 animate-pulse rounded bg-white/10" />
                <div className="mt-3 h-3 w-28 animate-pulse rounded bg-white/10" />
                <div className="mt-5 h-24 animate-pulse rounded bg-white/5" />
              </article>
            ) : null}

            {recommendedJobs.map((job) => (
              <article
                className={`rounded-[24px] border p-5 transition ${
                  job.id === selectedJob?.id
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
                    <p className="mt-2 text-xs text-emerald-200">
                      {job.analysis_result?.recommendation ?? "Öneri bekleniyor"}
                    </p>
                  </div>
                  <div className="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1.5 text-xs text-emerald-100">
                    Skor {job.analysis_result?.total_score?.toFixed(2) ?? "Bekliyor"}
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  {(job.analysis_result?.matched_keywords ?? []).slice(0, 6).map((item) => (
                    <span
                      className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-slate-200"
                      key={item}
                    >
                      {item}
                    </span>
                  ))}
                </div>

                <div className="mt-4 flex flex-wrap gap-3">
                  <button
                    className="inline-flex items-center gap-2 rounded-full border border-white/10 px-4 py-2 text-xs text-slate-200 transition hover:border-emerald-300/40 hover:bg-emerald-300/10"
                    onClick={() => setSelectedJobId(job.id)}
                    type="button"
                  >
                    <CircleGauge className="h-3.5 w-3.5" />
                    Detayı İncele
                  </button>
                  <button
                    className="inline-flex items-center gap-2 rounded-full bg-emerald-300 px-4 py-2 text-xs font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
                    disabled={actionLoading}
                    onClick={() => void handlePipelineAction(job)}
                    type="button"
                  >
                    {actionLoading ? (
                      <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <SendHorizontal className="h-3.5 w-3.5" />
                    )}
                    {applicationsByJobId.get(job.id) ? "Başvuruya Git" : "Pipeline’a Ekle"}
                  </button>
                </div>
              </article>
            ))}

            {!loading && !recommendedJobs.length ? (
              <div className="rounded-[24px] border border-dashed border-white/10 bg-slate-950/60 p-5">
                <p className="text-sm font-medium text-white">
                  Şu anda başvuruya açık ve güncel öneri ilan görünmüyor.
                </p>
                <p className="mt-2 text-sm text-slate-400">
                  Süresi dolmuş veya başvuruya kapanmış ilanlar otomatik gizlenir. Yeni ilan
                  keşfi çalıştırabilir ya da tüm aktif ilanlara geçebilirsin.
                </p>
              </div>
            ) : null}
          </div>
        </div>

        <div className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
          <div className="flex items-center gap-3">
            <CheckCheck className="h-5 w-5 text-emerald-200" />
            <h3 className="text-lg font-semibold text-white">Öneri detay paneli</h3>
          </div>

          {selectedJob ? (
            <div className="mt-5 space-y-4">
              <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-5">
                <p className="text-xl font-semibold text-white">{selectedJob.title}</p>
                <p className="mt-2 text-sm text-slate-400">
                  {selectedJob.company_name} • {selectedJob.source_platform} •{" "}
                  {selectedJob.location}
                </p>
                <p className="mt-4 text-sm leading-6 text-slate-300">
                  {selectedJob.analysis_result?.recommendation_reason ??
                    "Detaylı öneri nedeni henüz oluşmadı."}
                </p>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-4">
                  <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                    Güçlü Eşleşmeler
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

                <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-4">
                  <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                    Kalan Riskler
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(selectedJob.analysis_result?.gaps ?? []).map((item) => (
                      <span
                        className="rounded-full border border-rose-300/20 bg-rose-300/10 px-3 py-2 text-xs text-rose-100"
                        key={item}
                      >
                        {item}
                      </span>
                    ))}
                    {!(selectedJob.analysis_result?.gaps ?? []).length ? (
                      <span className="text-sm text-slate-400">
                        Kritik risk görünmüyor.
                      </span>
                    ) : null}
                  </div>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-4">
                  <p className="text-xs text-slate-500">Toplam skor</p>
                  <p className="mt-2 text-2xl font-semibold text-white">
                    {selectedJob.analysis_result?.total_score?.toFixed(2) ?? "Bekliyor"}
                  </p>
                </div>
                <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-4">
                  <p className="text-xs text-slate-500">Semantic alignment</p>
                  <p className="mt-2 text-2xl font-semibold text-white">
                    {selectedJob.analysis_result?.breakdown.semantic_alignment?.toFixed(2) ??
                      "0.00"}
                  </p>
                </div>
                <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-4">
                  <p className="text-xs text-slate-500">Pipeline durumu</p>
                  <p className="mt-2 text-sm font-semibold text-white">
                    {applicationsByJobId.get(selectedJob.id)?.status ?? "Henüz oluşturulmadı"}
                  </p>
                </div>
              </div>

              <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-5">
                <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                  Öne çıkan yetkinlikler
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {(selectedJob.analysis_result?.matched_keywords ?? []).map((item) => (
                    <span
                      className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-slate-200"
                      key={item}
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ) : loading ? (
            <div className="mt-6 inline-flex items-center gap-2 text-sm text-slate-300">
              <LoaderCircle className="h-4 w-4 animate-spin" />
              Önerilen ilanlar yükleniyor...
            </div>
          ) : (
            <div className="mt-4 rounded-[24px] border border-dashed border-white/10 bg-slate-950/60 p-5">
              <p className="text-sm font-medium text-white">Gösterilecek aktif öneri yok.</p>
              <p className="mt-2 text-sm text-slate-400">
                Arka plandaki filtre kapanmış veya süresi dolmuş ilanları ayıklar. Yeni bir
                watcher keşfi sonrası detay paneli burada dolacaktır.
              </p>
            </div>
          )}

          {error ? <p className="mt-4 text-sm text-rose-300">{error}</p> : null}
          {success ? <p className="mt-4 text-sm text-emerald-200">{success}</p> : null}
        </div>
      </div>
    </section>
  );
}
