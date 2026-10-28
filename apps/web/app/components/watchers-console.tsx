"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BellDot,
  BriefcaseBusiness,
  CheckCheck,
  Clock3,
  DatabaseBackup,
  ExternalLink,
  History,
  LoaderCircle,
  Play,
  Radar,
} from "lucide-react";

import {
  createWatcher,
  discoverWatcher,
  getArchiveDetail,
  getProfile,
  listArchive,
  listJobs,
  listNotifications,
  listWatcherRuns,
  listWatchers,
  runWatcher,
} from "@/app/lib/api";
import type {
  ArchiveJobDetailResponse,
  ArchiveRecord,
  DiscoverySourceReport,
  JobRecord,
  NotificationRecord,
  NotificationChannel,
  SyncRunRecord,
  WatcherRecord,
  WorkMode,
} from "@/app/lib/types";
import { useCareerRadarStore } from "@/app/stores/onboarding-store";

function splitText(value: string) {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

interface WatchersConsoleProps {
  onCompleted?: () => void;
}

export function WatchersConsole({ onCompleted }: WatchersConsoleProps) {
  const { profile, userId, setLastWatcher, setProfile } = useCareerRadarStore();
  const [watchers, setWatchers] = useState<WatcherRecord[]>([]);
  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);
  const [archive, setArchive] = useState<ArchiveRecord[]>([]);
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [runs, setRuns] = useState<SyncRunRecord[]>([]);
  const [selectedWatcherId, setSelectedWatcherId] = useState<string | null>(null);
  const [selectedArchiveJobId, setSelectedArchiveJobId] = useState<string | null>(null);
  const [archiveDetail, setArchiveDetail] = useState<ArchiveJobDetailResponse | null>(null);
  const [lastDiscoveryReports, setLastDiscoveryReports] = useState<DiscoverySourceReport[]>([]);
  const [runningWatcherId, setRunningWatcherId] = useState<string | null>(null);
  const [discoveringWatcherId, setDiscoveringWatcherId] = useState<string | null>(null);
  const [dataLoading, setDataLoading] = useState(true);
  const [runsLoading, setRunsLoading] = useState(true);
  const [archiveDetailLoading, setArchiveDetailLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [channels, setChannels] = useState<NotificationChannel[]>(["in_app", "email"]);
  const [form, setForm] = useState({
    query_name: "LinkedIn QA Leadership Watcher",
    source_platform: "linkedin_search_url" as const,
    keywords: "qa manager, test automation, quality engineering",
    locations: "remote, istanbul",
    industries: "fintech, e-commerce",
    work_modes: "remote, hybrid",
    min_experience_years: "8",
    position_types: "full-time",
    minimum_match_score: "72",
    sync_frequency_minutes: "60",
    source_urls: "",
  });

  const stats = useMemo(
    () => [
      { label: "Watcher", value: watchers.length },
      { label: "Run", value: runs.length },
      { label: "Bildirim", value: notifications.length },
      { label: "Arşiv", value: archive.length },
    ],
    [archive.length, notifications.length, runs.length, watchers.length],
  );

  const refreshData = useCallback(async () => {
    if (!userId) return;
    try {
      setDataLoading(true);
      setLoading(true);
      const [watcherData, notificationData, archiveData, jobData] = await Promise.all([
        listWatchers(),
        listNotifications(userId),
        listArchive(userId),
        listJobs(userId, {
          activeOnly: true,
          publishedWithinDays: 30,
          dedupe: true,
          sortBy: "published_at",
          sortOrder: "desc",
        }),
      ]);
      const filteredWatchers = watcherData.filter((item) => item.user_id === userId);
      setWatchers(filteredWatchers);
      setNotifications(notificationData);
      setArchive(archiveData);
      setJobs(jobData);
      setSelectedWatcherId((current) => current ?? filteredWatchers[0]?.id ?? null);
      setSelectedArchiveJobId((current) => current ?? archiveData[0]?.job_id ?? null);
    } catch (refreshError) {
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : "Watcher verileri alınamadı.",
      );
    } finally {
      setDataLoading(false);
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    void refreshData();
  }, [refreshData]);

  const refreshRuns = useCallback(async (watcherId: string) => {
    try {
      setRunsLoading(true);
      const runData = await listWatcherRuns(watcherId);
      setRuns(runData);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Watcher run geçmişi alınamadı.");
    } finally {
      setRunsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedWatcherId) {
      setRuns([]);
      if (!dataLoading) {
        setRunsLoading(false);
      }
      return;
    }
    void refreshRuns(selectedWatcherId);
  }, [dataLoading, refreshRuns, selectedWatcherId]);

  const refreshArchiveDetail = useCallback(
    async (jobId: string) => {
      try {
        setArchiveDetailLoading(true);
        const detail = await getArchiveDetail(jobId, userId);
        setArchiveDetail(detail);
      } catch (detailError) {
        setError(
          detailError instanceof Error ? detailError.message : "Arşiv detay bilgisi alınamadı.",
        );
      } finally {
        setArchiveDetailLoading(false);
      }
    },
    [userId],
  );

  useEffect(() => {
    if (!selectedArchiveJobId) {
      setArchiveDetail(null);
      return;
    }
    void refreshArchiveDetail(selectedArchiveJobId);
  }, [refreshArchiveDetail, selectedArchiveJobId]);

  async function handleWatcherCreate() {
    if (!profile) {
      setError("Önce CV ve profil akışını tamamla; watcher için profile_id gereklidir.");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setMessage(null);
      const freshProfile = await getProfile({ userId }).catch(() => profile);
      if (!freshProfile) {
        throw new Error("Profil doğrulanamadı. Lütfen önce CV ve profil akışını yeniden kaydet.");
      }
      setProfile(freshProfile);
      const watcher = await createWatcher({
        user_id: userId,
        profile_id: freshProfile.id,
        query_name: form.query_name,
        source_platform: form.source_platform,
        search_criteria: {
          keywords: splitText(form.keywords),
          locations: splitText(form.locations),
          industries: splitText(form.industries),
          work_modes: splitText(form.work_modes) as WorkMode[],
          min_experience_years: Number(form.min_experience_years),
          position_types: splitText(form.position_types),
        },
        minimum_match_score: Number(form.minimum_match_score),
        sync_frequency_minutes: Number(form.sync_frequency_minutes),
        notification_channels: channels,
        metadata: {
          source_urls: splitText(form.source_urls),
        },
      });
      setLastWatcher(watcher);
      setMessage("Watcher oluşturuldu. Artık sync run, bildirim ve arşiv akışına hazır.");
      await refreshData();
      setSelectedWatcherId(watcher.id);
      onCompleted?.();
    } catch (createError) {
      setError(
        createError instanceof Error
          ? createError.message
          : "Watcher oluşturulamadı.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleRunWatcher(watcher: WatcherRecord) {
    if (!jobs.length) {
      setError("Manual run için önce ilan operasyonundan en az bir ilan içe alınmalıdır.");
      return;
    }

    try {
      setRunningWatcherId(watcher.id);
      setError(null);
      setMessage(null);
      const response = await runWatcher(watcher.id, {
        triggered_by: "manual-ui",
        jobs: jobs.map((job) => ({
          ...job.parsed_job,
          metadata: {
            ...job.parsed_job.metadata,
            company_name: job.company_name,
            source_platform: job.source_platform,
            position_type: job.parsed_job.metadata?.position_type ?? "full-time",
          },
        })),
      });
      setMessage(
        `${response.run.processed_jobs} ilan tarandı, ${response.run.matched_jobs} ilan eşik değeri geçti.`,
      );
      await refreshData();
      await refreshRuns(watcher.id);
      if (response.archived_jobs[0]) {
        setSelectedArchiveJobId(response.archived_jobs[0].job_id);
      }
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Watcher run çalıştırılamadı.");
    } finally {
      setRunningWatcherId(null);
    }
  }

  async function handleDiscoverWatcher(watcher: WatcherRecord) {
    try {
      setDiscoveringWatcherId(watcher.id);
      setError(null);
      setMessage(null);
      const response = await discoverWatcher(watcher.id, {
        triggered_by: "live-ui",
        max_jobs: 10,
      });
      setLastDiscoveryReports(response.source_reports);
      const failedSources = response.source_reports.filter((report) => report.status !== "completed").length;
      setMessage(
        `${response.source_reports.length} kaynak tarandı, ${response.imported_jobs.length} canlı ilan bulundu, ${response.run.matched_jobs} ilan eşik değeri geçti${failedSources ? `, ${failedSources} kaynak hata verdi` : ""}.`,
      );
      await refreshData();
      await refreshRuns(watcher.id);
      setSelectedWatcherId(watcher.id);
      if (response.archived_jobs[0]) {
        setSelectedArchiveJobId(response.archived_jobs[0].job_id);
      }
    } catch (discoverError) {
      setError(
        discoverError instanceof Error ? discoverError.message : "Canlı keşif çalıştırılamadı.",
      );
    } finally {
      setDiscoveringWatcherId(null);
    }
  }

  const activeWatcher = useMemo(
    () => watchers.find((watcher) => watcher.id === selectedWatcherId) ?? null,
    [selectedWatcherId, watchers],
  );

  return (
    <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
      <div className="space-y-6">
        <div className="rounded-[32px] border border-white/10 bg-[rgba(9,15,30,0.88)] p-6 shadow-[0_18px_60px_rgba(2,8,20,0.35)]">
          <div className="flex items-center gap-3">
            <Radar className="h-5 w-5 text-emerald-200" />
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-slate-500">Adım 2</p>
              <h2 className="mt-2 font-display text-3xl text-white">
                İzleme profili oluştur.
              </h2>
            </div>
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-300">
            Bu form backend&apos;deki `profile_id` destekli watcher endpoint&apos;ine bağlıdır.
            CV&apos;den üretilen profil burada doğrudan kullanılır. Canlı keşif için izinli kaynak
            URL&apos;lerini `source urls` alanına satır satır veya virgülle girebilirsin.
          </p>

          <div className="mt-6 grid gap-4">
            {Object.entries(form).map(([key, value]) => (
              <label key={key}>
                <span className="mb-2 block text-xs uppercase tracking-[0.22em] text-slate-500">
                  {key.replaceAll("_", " ")}
                </span>
                <input
                  className="h-12 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 text-sm text-white outline-none transition focus:border-emerald-300/40"
                  onChange={(event) =>
                    setForm((current) => ({ ...current, [key]: event.target.value }))
                  }
                  value={value}
                />
              </label>
            ))}
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            {(["in_app", "email"] as NotificationChannel[]).map((channel) => {
              const active = channels.includes(channel);
              return (
                <button
                  className={`rounded-full border px-4 py-2 text-sm transition ${
                    active
                      ? "border-emerald-300/40 bg-emerald-300/10 text-emerald-100"
                      : "border-white/10 bg-white/[0.04] text-slate-300"
                  }`}
                  key={channel}
                  onClick={() =>
                    setChannels((current) =>
                      current.includes(channel)
                        ? current.filter((item) => item !== channel)
                        : [...current, channel],
                    )
                  }
                  type="button"
                >
                  {channel}
                </button>
              );
            })}
          </div>

          <button
            className="mt-6 inline-flex h-12 items-center gap-2 rounded-full bg-emerald-300 px-5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
            disabled={loading}
            onClick={handleWatcherCreate}
            type="button"
          >
            {loading ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <BriefcaseBusiness className="h-4 w-4" />
            )}
            Watcher Oluştur
          </button>

          {error ? <p className="mt-4 text-sm text-rose-300">{error}</p> : null}
          {message ? <p className="mt-4 text-sm text-emerald-200">{message}</p> : null}
          {lastDiscoveryReports.length ? (
            <div className="mt-4 rounded-[20px] border border-white/10 bg-slate-950/70 p-4">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                Kaynak doğrulama özeti
              </p>
              <div className="mt-3 space-y-2">
                {lastDiscoveryReports.map((report) => (
                  <div className="text-xs text-slate-300" key={report.source_url}>
                    <span className="font-semibold text-white">
                      {report.source_platform ?? "company_page"}
                    </span>
                    {" • "}
                    {report.status}
                    {" • "}
                    {report.fetched_jobs} ilan
                    {report.verification_note ? ` • ${report.verification_note}` : ""}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {stats.map((stat) => (
            <div
              className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5"
              key={stat.label}
            >
              <p className="text-xs uppercase tracking-[0.26em] text-slate-500">
                {stat.label}
              </p>
              <p className="mt-3 text-3xl font-semibold text-white">{stat.value}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-6">
        <div className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-white">Aktif watcher listesi</h3>
            <button
              className="rounded-full border border-white/10 px-4 py-2 text-xs text-slate-300 transition hover:border-emerald-300/40 hover:text-white"
              onClick={() => void refreshData()}
              type="button"
            >
              Yenile
            </button>
          </div>
          <div className="mt-4 space-y-3">
            {dataLoading ? (
              <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-4">
                <div className="h-4 w-40 animate-pulse rounded bg-white/10" />
                <div className="mt-3 h-3 w-28 animate-pulse rounded bg-white/10" />
              </div>
            ) : null}
            {watchers.map((watcher) => (
              <div
                className={`rounded-[24px] border p-4 transition ${
                  watcher.id === selectedWatcherId
                    ? "border-emerald-300/40 bg-emerald-300/[0.08]"
                    : "border-white/10 bg-slate-950/70"
                }`}
                key={watcher.id}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-white">{watcher.query_name}</p>
                    <p className="mt-1 text-xs text-slate-400">
                      Min skor {watcher.minimum_match_score} • {watcher.source_platform}
                    </p>
                    <p className="mt-2 text-xs leading-5 text-slate-500">
                      {watcher.search_criteria?.keywords?.join(", ") || "Anahtar kelime yok"} •{" "}
                      {watcher.search_criteria?.locations?.join(", ") || "Lokasyon yok"}
                    </p>
                  </div>
                  <div className="inline-flex items-center gap-2 rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-300">
                    <Clock3 className="h-3.5 w-3.5" />
                    {watcher.sync_frequency_minutes} dk
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    className="rounded-full border border-white/10 px-4 py-2 text-xs text-slate-200 transition hover:border-emerald-300/40 hover:bg-emerald-300/10"
                    onClick={() => setSelectedWatcherId(watcher.id)}
                    type="button"
                  >
                    Run Geçmişi
                  </button>
                  <button
                    className="inline-flex items-center gap-2 rounded-full border border-emerald-300/30 bg-emerald-300/10 px-4 py-2 text-xs text-emerald-100 transition hover:bg-emerald-300/15 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/[0.04] disabled:text-slate-500"
                    disabled={runningWatcherId === watcher.id}
                    onClick={() => void handleRunWatcher(watcher)}
                    type="button"
                  >
                    {runningWatcherId === watcher.id ? (
                      <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Play className="h-3.5 w-3.5" />
                    )}
                    Manual Run
                  </button>
                  <button
                    className="inline-flex items-center gap-2 rounded-full border border-sky-300/30 bg-sky-300/10 px-4 py-2 text-xs text-sky-100 transition hover:bg-sky-300/15 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/[0.04] disabled:text-slate-500"
                    disabled={discoveringWatcherId === watcher.id}
                    onClick={() => void handleDiscoverWatcher(watcher)}
                    type="button"
                  >
                    {discoveringWatcherId === watcher.id ? (
                      <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Radar className="h-3.5 w-3.5" />
                    )}
                    Canlı Keşif
                  </button>
                </div>
              </div>
            ))}
            {!dataLoading && !watchers.length ? (
              <p className="text-sm text-slate-400">Henüz watcher oluşturulmadı.</p>
            ) : null}
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
            <div className="flex items-center gap-3">
              <History className="h-5 w-5 text-emerald-200" />
              <div>
                <h3 className="text-lg font-semibold text-white">Run geçmişi</h3>
                <p className="mt-1 text-xs text-slate-500">
                  {activeWatcher?.query_name ?? "Watcher seçildiğinde geçmiş burada görünür."}
                </p>
              </div>
            </div>
            <div className="mt-4 space-y-3">
              {runsLoading ? (
                <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                  <div className="h-4 w-24 animate-pulse rounded bg-white/10" />
                  <div className="mt-3 h-12 animate-pulse rounded bg-white/5" />
                </div>
              ) : null}
              {runs.map((run) => (
                <div
                  className="rounded-2xl border border-white/10 bg-slate-950/70 p-4"
                  key={run.id}
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-white">{run.status}</p>
                    <span className="rounded-full border border-white/10 px-2.5 py-1 text-xs text-slate-300">
                      {run.matched_jobs} match
                    </span>
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-3 text-xs text-slate-400">
                    <div>
                      <p>İşlenen</p>
                      <p className="mt-1 text-sm text-white">{run.processed_jobs}</p>
                    </div>
                    <div>
                      <p>Bildirim</p>
                      <p className="mt-1 text-sm text-white">{run.notifications_created}</p>
                    </div>
                    <div>
                      <p>Tetikleyen</p>
                      <p className="mt-1 truncate text-sm text-white">
                        {String(run.metadata?.triggered_by ?? "manual")}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
              {!runsLoading && !runs.length ? (
                <p className="text-sm text-slate-400">
                  Bu watcher için henüz run kaydı oluşmadı.
                </p>
              ) : null}
            </div>
          </div>

          <div className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
            <div className="flex items-center gap-3">
              <BellDot className="h-5 w-5 text-emerald-200" />
              <h3 className="text-lg font-semibold text-white">Bildirimler</h3>
            </div>
            <div className="mt-4 space-y-3">
              {dataLoading ? (
                <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                  <div className="h-4 w-32 animate-pulse rounded bg-white/10" />
                  <div className="mt-3 h-10 animate-pulse rounded bg-white/5" />
                </div>
              ) : null}
              {notifications.slice(0, 4).map((notification) => (
                <div
                  className="rounded-2xl border border-white/10 bg-slate-950/70 p-4"
                  key={notification.id}
                >
                  <p className="text-sm font-medium text-white">{notification.title}</p>
                  <p className="mt-2 text-xs leading-5 text-slate-400">
                    {notification.message}
                  </p>
                </div>
              ))}
              {!dataLoading && !notifications.length ? (
                <p className="text-sm text-slate-400">Henüz bildirim oluşmadı.</p>
              ) : null}
            </div>
          </div>

          <div className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
            <div className="flex items-center gap-3">
              <DatabaseBackup className="h-5 w-5 text-emerald-200" />
              <h3 className="text-lg font-semibold text-white">Arşiv</h3>
            </div>
            <div className="mt-4 space-y-3">
              {dataLoading ? (
                <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                  <div className="h-4 w-32 animate-pulse rounded bg-white/10" />
                  <div className="mt-3 h-10 animate-pulse rounded bg-white/5" />
                </div>
              ) : null}
              {archive.slice(0, 4).map((item) => (
                <button
                  className={`block w-full rounded-2xl border p-4 text-left transition ${
                    item.job_id === selectedArchiveJobId
                      ? "border-emerald-300/40 bg-emerald-300/[0.08]"
                      : "border-white/10 bg-slate-950/70"
                  }`}
                  key={item.job_id}
                  onClick={() => setSelectedArchiveJobId(item.job_id)}
                  type="button"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-white">{item.title}</p>
                      <p className="mt-1 truncate text-xs text-slate-400">{item.company_name} • {item.location}</p>
                    </div>
                    {(item.source_url || item.apply_url) ? (
                      <a
                        className="shrink-0 rounded-full border border-emerald-300/30 bg-emerald-300/[0.08] p-1.5 text-emerald-200 hover:bg-emerald-300/[0.15]"
                        href={item.apply_url || item.source_url || undefined}
                        target="_blank"
                        rel="noreferrer noopener"
                        onClick={(e) => e.stopPropagation()}
                        title="Başvuru linkini aç"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    ) : null}
                  </div>
                  <p className="mt-2 text-xs text-emerald-200">
                    Son skor: {item.last_match_score.toFixed(2)}
                  </p>
                </button>
              ))}
              {!dataLoading && !archive.length ? (
                <p className="text-sm text-slate-400">Henüz arşiv kaydı oluşmadı.</p>
              ) : null}
            </div>
          </div>

          <div className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
            <div className="flex items-center gap-3">
              <CheckCheck className="h-5 w-5 text-emerald-200" />
              <h3 className="text-lg font-semibold text-white">Arşiv detay</h3>
            </div>
            {archiveDetailLoading ? (
              <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                <div className="h-4 w-32 animate-pulse rounded bg-white/10" />
                <div className="mt-3 h-24 animate-pulse rounded bg-white/5" />
              </div>
            ) : archiveDetail ? (
              <div className="mt-4 space-y-4">
                <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-white">
                        {archiveDetail.archive.title}
                      </p>
                      <p className="mt-1 text-xs text-slate-400">
                        {archiveDetail.archive.company_name} • {archiveDetail.archive.location}
                      </p>
                    </div>
                    {(archiveDetail.archive.source_url || archiveDetail.archive.apply_url) ? (
                      <a
                        className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-emerald-300/30 bg-emerald-300/[0.08] px-3 py-1.5 text-xs text-emerald-200 hover:bg-emerald-300/[0.15]"
                        href={archiveDetail.archive.apply_url || archiveDetail.archive.source_url || undefined}
                        target="_blank"
                        rel="noreferrer noopener"
                        title="İlanın bulunduğu sayfayı yeni sekmede aç"
                      >
                        Başvuru linki
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    ) : null}
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-3 text-xs text-slate-400">
                    <div>
                      <p>Kaynak</p>
                      <p className="mt-1 text-sm text-white">
                        {archiveDetail.archive.source_platform}
                      </p>
                    </div>
                    <div>
                      <p>Öneri</p>
                      <p className="mt-1 text-sm text-white">
                        {archiveDetail.archive.last_recommendation}
                      </p>
                    </div>
                    <div>
                      <p>Skor</p>
                      <p className="mt-1 text-sm text-white">
                        {archiveDetail.archive.last_match_score.toFixed(2)}
                      </p>
                    </div>
                    <div>
                      <p>Bildirim</p>
                      <p className="mt-1 text-sm text-white">
                        {archiveDetail.notifications.length}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                  <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                    Job metadata
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(
                      (archiveDetail.archive.metadata?.required_skills as string[] | undefined) ?? []
                    ).map((skill) => (
                      <span
                        className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-slate-200"
                        key={skill}
                      >
                        {skill}
                      </span>
                    ))}
                    {!((archiveDetail.archive.metadata?.required_skills as string[] | undefined) ?? [])
                      .length ? (
                      <span className="text-sm text-slate-400">
                        Bu arşiv kaydı için yetkinlik metadata bulunmuyor.
                      </span>
                    ) : null}
                  </div>
                </div>
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-400">
                Arşivden bir ilan seçildiğinde detay burada görünür.
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
