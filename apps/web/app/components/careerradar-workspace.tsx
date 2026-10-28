"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  FolderKanban,
  ScanSearch,
  ShieldCheck,
  Sparkle,
} from "lucide-react";

import {
  getProfile,
  listApplications,
  listArchive,
  listJobs,
  listNotifications,
  listWatchers,
} from "@/app/lib/api";
import { ApplicationsConsole } from "@/app/components/applications-console";
import { AppShell } from "@/app/components/app-shell";
import { JobsConsole } from "@/app/components/jobs-console";
import { ProfileFlow } from "@/app/components/profile-flow";
import { RecommendedJobsConsole } from "@/app/components/recommended-jobs-console";
import { WatchersConsole } from "@/app/components/watchers-console";
import { WorkflowChecklist } from "@/app/components/workflow-checklist";
import type {
  ApplicationRecord,
  CandidateProfileRecord,
  JobRecord,
  WatcherRecord,
} from "@/app/lib/types";
import { resolveWorkflowSnapshot } from "@/app/lib/workflow";
import { useCareerRadarStore } from "@/app/stores/onboarding-store";

const overviewCards = [
  {
    title: "Gerçek CV akışı",
    description:
      "PDF veya DOCX yüklemesi backend parse servisine bağlanır, profil çıkarılır ve doğrulama ekranında düzenlenir.",
    icon: Sparkle,
  },
  {
    title: "Politika uyumlu izleme",
    description:
      "Watcher profilleri, profile_id ile yaratılır ve kullanıcı tanımlı kriterleri izinli kaynak akışı üzerinde çalıştırır.",
    icon: ShieldCheck,
  },
  {
    title: "Açıklanabilir eşleştirme",
    description:
      "Arşiv, bildirim ve eşik bazlı izleme yapısı mevcut matching engine ile aynı veri modeline oturur.",
    icon: ScanSearch,
  },
  {
    title: "Manuel ilan operasyonu",
    description:
      "Kullanıcı bağlantı/metin sağlar, sistem ilanı parse eder, eşleştirir ve başvuru pipeline’ına taşır.",
    icon: FolderKanban,
  },
];

function getLatestRecord<T extends { updated_at?: string; created_at?: string }>(items: T[]): T | null {
  if (!items.length) return null;
  return [...items].sort((left, right) => {
    const leftDate = left.updated_at ?? left.created_at ?? "";
    const rightDate = right.updated_at ?? right.created_at ?? "";
    return rightDate.localeCompare(leftDate);
  })[0];
}

function getTopEntries(values: string[], limit = 4) {
  const counts = values.reduce<Record<string, number>>((accumulator, value) => {
    if (!value) return accumulator;
    accumulator[value] = (accumulator[value] ?? 0) + 1;
    return accumulator;
  }, {});

  return Object.entries(counts)
    .sort((left, right) => right[1] - left[1])
    .slice(0, limit)
    .map(([label, value]) => ({ label, value }));
}

function toPercent(value: number, total: number) {
  if (!total) return 0;
  return Math.max(8, Math.round((value / total) * 100));
}

export function CareerRadarWorkspace() {
  const {
    activeSection,
    setActiveSection,
    userId,
    profile,
    setProfile,
    lastWatcher,
    lastJob,
    lastApplication,
  } =
    useCareerRadarStore();
  const [liveProfile, setLiveProfile] = useState<CandidateProfileRecord | null>(null);
  const [workflowNotice, setWorkflowNotice] = useState<string | null>(null);
  const [workflowToast, setWorkflowToast] = useState<string | null>(null);
  const [workflowResources, setWorkflowResources] = useState<{
    watchers: WatcherRecord[];
    jobs: JobRecord[];
    applications: ApplicationRecord[];
  }>({
    watchers: [],
    jobs: [],
    applications: [],
  });
  const [dashboard, setDashboard] = useState({
    watchers: 0,
    jobs: 0,
    highMatchJobs: 0,
    applications: 0,
    interviews: 0,
    offers: 0,
    notifications: 0,
    archive: 0,
    averageScore: 0,
    latestWatcherName: "",
    latestJobTitle: "",
    latestApplicationStatus: "",
    topCompanies: [] as Array<{ label: string; value: number }>,
    topPlatforms: [] as Array<{ label: string; value: number }>,
    topMissingSkills: [] as Array<{ label: string; value: number }>,
    recommendationMix: [] as Array<{ label: string; value: number }>,
    workModeMix: [] as Array<{ label: string; value: number }>,
  });
  const [dashboardLoading, setDashboardLoading] = useState(true);

  useEffect(() => {
    async function loadDashboard() {
      try {
        setDashboardLoading(true);
        const [profileRecord, watchers, jobs, applications, notifications, archive] = await Promise.all([
          getProfile({ userId }).catch(() => null),
          listWatchers(),
          listJobs(userId, {
            activeOnly: true,
            publishedWithinDays: 30,
            dedupe: true,
            sortBy: "published_at",
            sortOrder: "desc",
          }),
          listApplications(userId),
          listNotifications(userId),
          listArchive(userId),
        ]);
        setLiveProfile(profileRecord);
        if (profileRecord) setProfile(profileRecord);
        const filteredWatchers = watchers.filter((watcher) => watcher.user_id === userId);
        setWorkflowResources({
          watchers: filteredWatchers,
          jobs,
          applications,
        });
        const latestWatcher = getLatestRecord(filteredWatchers);
        const latestJob = getLatestRecord(jobs);
        const latestApplication = getLatestRecord(applications);
        const scoredJobs = jobs.filter((job) => job.analysis_result?.total_score != null);
        const averageScore =
          scoredJobs.reduce((sum, job) => sum + (job.analysis_result?.total_score ?? 0), 0) /
          (scoredJobs.length || 1);
        const topCompanies = getTopEntries(jobs.map((job) => job.company_name));
        const topPlatforms = getTopEntries(jobs.map((job) => job.source_platform));
        const topMissingSkills = getTopEntries(
          jobs.flatMap((job) => job.analysis_result?.missing_keywords ?? []),
        );
        const recommendationMix = getTopEntries(
          jobs.map((job) => job.analysis_result?.recommendation ?? "Analiz bekleniyor"),
        );
        const workModeMix = getTopEntries(jobs.map((job) => job.work_mode));
        setDashboard({
          watchers: filteredWatchers.length,
          jobs: jobs.length,
          highMatchJobs: jobs.filter((job) => (job.analysis_result?.total_score ?? 0) >= 70)
            .length,
          applications: applications.length,
          interviews: applications.filter((application) =>
            [
              "İnsan kaynakları görüşmesi",
              "Teknik görüşme",
              "Yönetici görüşmesi",
            ].includes(application.status),
          ).length,
          offers: applications.filter((application) => application.status === "Teklif alındı")
            .length,
          notifications: notifications.length,
          archive: archive.length,
          averageScore,
          latestWatcherName: latestWatcher?.query_name ?? "",
          latestJobTitle: latestJob?.title ?? "",
          latestApplicationStatus: latestApplication?.status ?? "",
          topCompanies,
          topPlatforms,
          topMissingSkills,
          recommendationMix,
          workModeMix,
        });
      } catch {
        setLiveProfile(null);
        setDashboard((current) => current);
      } finally {
        setDashboardLoading(false);
      }
    }

    void loadDashboard();
  }, [userId, setProfile, lastWatcher, lastJob, lastApplication, activeSection]);

  const resolvedProfile = liveProfile ?? profile;
  const workflow = useMemo(
    () =>
      resolveWorkflowSnapshot({
        profile: resolvedProfile,
        watchers: workflowResources.watchers,
        jobs: workflowResources.jobs,
        applications: workflowResources.applications,
      }),
    [resolvedProfile, workflowResources],
  );

  useEffect(() => {
    if (activeSection === "overview") return;
    if (workflow.accessibleSections.includes(activeSection)) return;
    setWorkflowNotice(workflow.blockingMessage);
    setActiveSection(workflow.activeProcess === "jobs" ? "jobs" : workflow.activeProcess);
  }, [activeSection, setActiveSection, workflow]);

  useEffect(() => {
    if (workflow.steps.every((step) => step.isComplete)) {
      setWorkflowNotice(null);
    }
  }, [workflow.steps]);

  useEffect(() => {
    if (!workflowToast) return;
    const timeout = window.setTimeout(() => setWorkflowToast(null), 3200);
    return () => window.clearTimeout(timeout);
  }, [workflowToast]);

  function handleSectionChange(section: typeof activeSection) {
    if (workflow.accessibleSections.includes(section)) {
      setWorkflowNotice(null);
      setWorkflowToast(null);
      setActiveSection(section);
      return;
    }
    setWorkflowNotice(workflow.blockingMessage);
    setWorkflowToast(workflow.blockingMessage);
  }

  function goToSection(section: typeof activeSection) {
    handleSectionChange(section);
  }

  const overviewMetrics = useMemo(
    () => [
      { title: "Aktif watcher", value: dashboard.watchers, caption: "İzleme profili" },
      { title: "Toplam ilan", value: dashboard.jobs, caption: "Kaydedilen ilan" },
      { title: "Yüksek uyum", value: dashboard.highMatchJobs, caption: "70+ skor" },
      { title: "Ortalama skor", value: dashboard.averageScore.toFixed(1), caption: "Analiz ort." },
      { title: "Başvurular", value: dashboard.applications, caption: "Pipeline kaydı" },
      { title: "Görüşme", value: dashboard.interviews, caption: "Aktif süreç" },
      { title: "Teklif", value: dashboard.offers, caption: "Sonuçlanan" },
      { title: "Bildirim", value: dashboard.notifications, caption: "Watcher uyarısı" },
    ],
    [dashboard],
  );

  const performancePulse = useMemo(
    () => ({
      interviewRate: dashboard.applications
        ? Math.round((dashboard.interviews / dashboard.applications) * 100)
        : 0,
      offerRate: dashboard.applications
        ? Math.round((dashboard.offers / dashboard.applications) * 100)
        : 0,
      archiveCoverage: dashboard.jobs
        ? Math.round((dashboard.archive / dashboard.jobs) * 100)
        : 0,
      notificationDensity: dashboard.jobs
        ? Math.round((dashboard.notifications / dashboard.jobs) * 100)
        : 0,
    }),
    [dashboard],
  );

  const activeChecklistStep = useMemo(() => {
    if (activeSection === "recommended") {
      return workflow.steps.find((step) => step.id === "jobs") ?? null;
    }
    if (activeSection === "overview") return null;
    return workflow.steps.find((step) => step.id === activeSection) ?? null;
  }, [activeSection, workflow.steps]);

  return (
    <AppShell
      activeSection={activeSection}
      accessibleSections={workflow.accessibleSections}
      onLockedSectionAttempt={handleSectionChange}
      onSectionChange={handleSectionChange}
      processSteps={workflow.steps}
      workflowNotice={workflowNotice}
      toastMessage={workflowToast}
    >
      <main className="space-y-6">
        <section className="overflow-hidden rounded-[36px] border border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.18),transparent_30%),linear-gradient(135deg,rgba(8,14,28,0.96),rgba(4,9,20,0.96))] p-8 shadow-[0_24px_120px_rgba(2,8,20,0.45)]">
          <div className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
            <div>
              <p className="text-xs uppercase tracking-[0.34em] text-emerald-200/80">
                CareerRadar AI Pro
              </p>
              <h1 className="mt-4 max-w-3xl font-display text-5xl leading-tight text-white">
                CV&apos;ni operasyona çeviren, job search odaklı yönetici paneli.
              </h1>
              <p className="mt-5 max-w-2xl text-sm leading-7 text-slate-300">
                Bu arayüz, backend&apos;de tamamlanan CV parse, profil güncelleme ve
                watcher oluşturma akışlarını tek panelde birleştirir. Overview alanı artık
                gerçek ilan, başvuru, bildirim ve arşiv verilerini özetleyerek operasyonel
                durum ekranı gibi çalışır.
              </p>
              <div className="mt-6 flex flex-wrap gap-3">
                <button
                  className="inline-flex h-12 items-center gap-2 rounded-full bg-emerald-300 px-5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200"
                  onClick={() => goToSection("profile")}
                  type="button"
                >
                  CV Akışına Git
                  <ArrowRight className="h-4 w-4" />
                </button>
                <button
                  className="inline-flex h-12 items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-5 text-sm font-semibold text-white transition hover:border-emerald-300/40 hover:bg-emerald-300/10"
                  onClick={() => goToSection("watchers")}
                  type="button"
                >
                  Watcher Kurulumuna Git
                </button>
                <button
                  className="inline-flex h-12 items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-5 text-sm font-semibold text-white transition hover:border-emerald-300/40 hover:bg-emerald-300/10"
                  onClick={() => goToSection("recommended")}
                  type="button"
                >
                  Önerilen İlanlara Git
                </button>
                <button
                  className="inline-flex h-12 items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-5 text-sm font-semibold text-white transition hover:border-emerald-300/40 hover:bg-emerald-300/10"
                  onClick={() => goToSection("jobs")}
                  type="button"
                >
                  İlan Operasyonuna Git
                </button>
              </div>
            </div>

            <div className="grid gap-4">
              <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5">
                <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                  Profil Durumu
                </p>
                <p className="mt-4 text-2xl font-semibold text-white">
                  {resolvedProfile?.profile.headline ?? "Henüz doğrulanmış profil yok"}
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  {resolvedProfile?.professional_summary ??
                    "CV yükleme ve parse tamamlandığında profesyonel özet burada görünür."}
                </p>
              </div>
              <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5">
                <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                  Son Watcher
                </p>
                <p className="mt-4 text-2xl font-semibold text-white">
                  {dashboard.latestWatcherName || lastWatcher?.query_name || "Henüz watcher üretilmedi"}
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  {dashboard.latestWatcherName || lastWatcher
                    ? `${
                        lastWatcher?.minimum_match_score ?? "Canlı"
                      } minimum skor ve ${lastWatcher?.sync_frequency_minutes ?? "aktif"} dk frekans ile hazır.`
                    : "Profil onaylandıktan sonra watcher ekranından ilk izleme profilini oluştur."}
                </p>
              </div>
              <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5">
                <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                  Son İlan / Başvuru
                </p>
                <p className="mt-4 text-2xl font-semibold text-white">
                  {dashboard.latestJobTitle || lastJob?.title || "Henüz ilan analiz edilmedi"}
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  {dashboard.latestApplicationStatus || lastApplication
                    ? `${
                        dashboard.latestApplicationStatus || lastApplication?.status
                      } aşamasında aktif başvuru kaydı var.`
                    : "İlan import sonrası başvuru panelinden pipeline kaydı açabilirsin."}
                </p>
              </div>
              <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5">
                <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                  Süreç Kilidi
                </p>
                <p className="mt-4 text-2xl font-semibold text-white">
                  {workflow.steps.find((step) => step.status === "active")?.label ?? "Akış tamamlandı"}
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  {workflow.steps.every((step) => step.isComplete)
                    ? "Tüm süreçler tamamlandı. İstersen mevcut kayıtları gözden geçirip yeni gerçek verilerle yeniden test edebilirsin."
                    : workflow.blockingMessage}
                </p>
              </div>
            </div>
          </div>
        </section>

        {activeChecklistStep ? <WorkflowChecklist step={activeChecklistStep} /> : null}

        {activeSection === "overview" ? (
          <section className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
              {overviewMetrics.map((metric) => (
                <article
                  className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5"
                  key={metric.title}
                >
                  <p className="text-xs uppercase tracking-[0.24em] text-slate-500">
                    {metric.title}
                  </p>
                  <p className="mt-3 text-3xl font-semibold text-white">{metric.value}</p>
                  <p className="mt-2 text-sm text-slate-400">{metric.caption}</p>
                </article>
              ))}
            </div>

            <div className="grid gap-6 lg:grid-cols-2 2xl:grid-cols-4">
              {overviewCards.map((card) => {
                const Icon = card.icon;
                return (
                  <article
                    className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6"
                    key={card.title}
                  >
                    <div className="inline-flex rounded-2xl border border-white/10 bg-slate-950/70 p-3 text-emerald-200">
                      <Icon className="h-5 w-5" />
                    </div>
                    <h2 className="mt-5 text-xl font-semibold text-white">{card.title}</h2>
                    <p className="mt-3 text-sm leading-6 text-slate-300">
                      {card.description}
                    </p>
                  </article>
                );
              })}
            </div>

            <div className="grid gap-6 xl:grid-cols-3">
              <article className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
                <h2 className="text-xl font-semibold text-white">Operasyon özeti</h2>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                  Watcher, job import ve application pipeline aynı veri havuzunda çalıştığı
                  için dashboard kartları gerçek operasyon yoğunluğunu yansıtır.
                </p>
                <div className="mt-5 space-y-3">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                      Öncelik
                    </p>
                    <p className="mt-2 text-sm text-white">
                      {dashboard.highMatchJobs
                        ? `${dashboard.highMatchJobs} ilan hemen değerlendirme için hazır.`
                        : "Önce watcher run veya job import ile veri havuzunu büyüt."}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                      Dönüşüm
                    </p>
                    <p className="mt-2 text-sm text-white">
                      {dashboard.applications
                        ? `%${Math.round((dashboard.interviews / dashboard.applications) * 100)} görüşme dönüşümü`
                        : "Başvuru oluşturulduğunda dönüşüm metriği hesaplanır."}
                    </p>
                  </div>
                </div>
              </article>
              <article className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
                <h2 className="text-xl font-semibold text-white">Profil kapsaması</h2>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                  Profil parse akışı tamamlandığında headline, özet ve hedef roller tüm
                  operasyon modüllerine ortak giriş verisi olur.
                </p>
                <div className="mt-5 rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                  <p className="text-sm font-semibold text-white">
                    {resolvedProfile?.profile.headline ?? "Henüz onaylı profil yok"}
                  </p>
                  <p className="mt-2 text-sm text-slate-400">
                    {resolvedProfile?.target_positions?.join(", ") ||
                      "CV yükleyip profili kaydettiğinde hedef roller görünür."}
                  </p>
                </div>
              </article>
              <article className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
                <h2 className="text-xl font-semibold text-white">Arşiv sağlığı</h2>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                  Bildirim ve arşiv birlikte izlenir; aynı yüksek uyumlu ilanın tekrar
                  bildirimi yerine sürdürülebilir takip akışı hedeflenir.
                </p>
                <div className="mt-5 rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                  <p className="text-sm text-white">
                    {dashboard.archive} arşiv kaydı ve {dashboard.notifications} bildirim aktif.
                  </p>
                </div>
              </article>
            </div>

            <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
              <article className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
                <h2 className="text-xl font-semibold text-white">Trend Pulse</h2>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                  Başvuru dönüşümü, teklif oranı ve watcher etkisini tek bakışta gösterir.
                </p>
                <div className="mt-5 space-y-4">
                  {[
                    {
                      label: "Görüşme dönüşümü",
                      value: performancePulse.interviewRate,
                      tone: "bg-emerald-300",
                    },
                    {
                      label: "Teklif oranı",
                      value: performancePulse.offerRate,
                      tone: "bg-sky-300",
                    },
                    {
                      label: "Arşiv kapsaması",
                      value: performancePulse.archiveCoverage,
                      tone: "bg-amber-300",
                    },
                    {
                      label: "Bildirim yoğunluğu",
                      value: performancePulse.notificationDensity,
                      tone: "bg-fuchsia-300",
                    },
                  ].map((item) => (
                    <div key={item.label}>
                      <div className="mb-2 flex items-center justify-between text-sm">
                        <span className="text-slate-300">{item.label}</span>
                        <span className="font-semibold text-white">%{item.value}</span>
                      </div>
                      <div className="h-2.5 rounded-full bg-white/5">
                        <div
                          className={`h-2.5 rounded-full ${item.tone}`}
                          style={{ width: `${toPercent(item.value, 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </article>

              <article className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
                <h2 className="text-xl font-semibold text-white">Pipeline Nabzı</h2>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                  İş akışının nerede yoğunlaştığını ve sonraki hamleyi gösteren kısa özet.
                </p>
                <div className="mt-5 grid gap-4 md:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                      Sonraki Odak
                    </p>
                    <p className="mt-2 text-sm text-white">
                      {dashboard.highMatchJobs > dashboard.applications
                        ? "Yüksek uyumlu ilanlar başvuruya dönüştürülmeli."
                        : "Mevcut başvurular mülakat ve teklif evresine taşınmalı."}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                      Veri Yoğunluğu
                    </p>
                    <p className="mt-2 text-sm text-white">
                      {dashboard.jobs
                        ? `${dashboard.jobs} ilan, ${dashboard.archive} arşiv ve ${dashboard.notifications} bildirim aynı havuzu besliyor.`
                        : "Henüz operasyonel veri havuzu oluşmadı."}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                      Profil Gücü
                    </p>
                    <p className="mt-2 text-sm text-white">
                      {resolvedProfile?.target_positions?.length
                        ? `${resolvedProfile.target_positions.length} hedef rol aktif takipte.`
                        : "Profil hedef rolleri henüz netleşmedi."}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                      Sağlık İşareti
                    </p>
                    <p className="mt-2 text-sm text-white">
                      {dashboard.watchers
                        ? `${dashboard.watchers} watcher ile izleme hattı aktif.`
                        : "Sürekli izleme için en az bir watcher önerilir."}
                    </p>
                  </div>
                </div>
              </article>
            </div>

            <div className="grid gap-6 xl:grid-cols-2 2xl:grid-cols-4">
              <article className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
                <h2 className="text-xl font-semibold text-white">Kaynak Dağılımı</h2>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                  Hangi platformlardan daha fazla ilan biriktiğini gösterir.
                </p>
                <div className="mt-5 space-y-3">
                  {dashboard.topPlatforms.map((item) => (
                    <div
                      className="rounded-2xl border border-white/10 bg-slate-950/70 p-4"
                      key={item.label}
                    >
                      <div className="flex items-center justify-between gap-4">
                        <p className="text-sm text-white">{item.label}</p>
                        <span className="text-sm font-semibold text-emerald-200">{item.value}</span>
                      </div>
                      <div className="mt-3 h-2 rounded-full bg-white/5">
                        <div
                          className="h-2 rounded-full bg-emerald-300"
                          style={{ width: `${toPercent(item.value, dashboard.jobs)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                  {!dashboardLoading && !dashboard.topPlatforms.length ? (
                    <p className="text-sm text-slate-400">Henüz kaynak verisi oluşmadı.</p>
                  ) : null}
                </div>
              </article>

              <article className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
                <h2 className="text-xl font-semibold text-white">Şirket Yoğunluğu</h2>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                  Pipeline ve job havuzunda en çok geçen şirketleri özetler.
                </p>
                <div className="mt-5 space-y-3">
                  {dashboard.topCompanies.map((item) => (
                    <div
                      className="rounded-2xl border border-white/10 bg-slate-950/70 p-4"
                      key={item.label}
                    >
                      <div className="flex items-center justify-between gap-4">
                        <p className="text-sm text-white">{item.label}</p>
                        <span className="text-sm font-semibold text-emerald-200">{item.value}</span>
                      </div>
                      <div className="mt-3 h-2 rounded-full bg-white/5">
                        <div
                          className="h-2 rounded-full bg-sky-300"
                          style={{ width: `${toPercent(item.value, dashboard.jobs)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                  {!dashboardLoading && !dashboard.topCompanies.length ? (
                    <p className="text-sm text-slate-400">Henüz şirket dağılımı oluşmadı.</p>
                  ) : null}
                </div>
              </article>

              <article className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
                <h2 className="text-xl font-semibold text-white">Skill Gap Radarı</h2>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                  Analiz edilen ilanlarda en sık eksik görünen yetkinlikleri listeler.
                </p>
                <div className="mt-5 flex flex-wrap gap-2">
                  {dashboard.topMissingSkills.map((item) => (
                    <span
                      className="rounded-full border border-rose-300/20 bg-rose-300/10 px-3 py-2 text-xs text-rose-100"
                      key={item.label}
                    >
                      {item.label} • {item.value}
                    </span>
                  ))}
                  {!dashboardLoading && !dashboard.topMissingSkills.length ? (
                    <p className="text-sm text-slate-400">Şu an kritik skill gap görünmüyor.</p>
                  ) : null}
                </div>
              </article>

              <article className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
                <h2 className="text-xl font-semibold text-white">Öneri Karması</h2>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                  Matching motorunun ilanlara verdiği aksiyon önerilerini özetler.
                </p>
                <div className="mt-5 space-y-3">
                  {dashboard.recommendationMix.map((item) => (
                    <div
                      className="rounded-2xl border border-white/10 bg-slate-950/70 p-4"
                      key={item.label}
                    >
                      <div className="flex items-center justify-between gap-4">
                        <p className="text-sm text-white">{item.label}</p>
                        <span className="text-sm font-semibold text-emerald-200">{item.value}</span>
                      </div>
                      <div className="mt-3 h-2 rounded-full bg-white/5">
                        <div
                          className="h-2 rounded-full bg-fuchsia-300"
                          style={{ width: `${toPercent(item.value, dashboard.jobs)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                  {!dashboardLoading && !dashboard.recommendationMix.length ? (
                    <p className="text-sm text-slate-400">Henüz öneri verisi oluşmadı.</p>
                  ) : null}
                </div>
              </article>
            </div>

            <div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
              <article className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
                <h2 className="text-xl font-semibold text-white">Çalışma Modeli</h2>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                  Remote, hybrid ve onsite ilanların güncel dağılımı.
                </p>
                <div className="mt-5 space-y-3">
                  {dashboard.workModeMix.map((item) => (
                    <div
                      className="rounded-2xl border border-white/10 bg-slate-950/70 p-4"
                      key={item.label}
                    >
                      <div className="flex items-center justify-between gap-4">
                        <p className="text-sm text-white">{item.label}</p>
                        <span className="text-sm font-semibold text-emerald-200">{item.value}</span>
                      </div>
                      <div className="mt-3 h-2 rounded-full bg-white/5">
                        <div
                          className="h-2 rounded-full bg-amber-300"
                          style={{ width: `${toPercent(item.value, dashboard.jobs)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </article>

              <article className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
                <h2 className="text-xl font-semibold text-white">Aksiyon Önerileri</h2>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                  Sistemin mevcut veri havuzuna göre bir sonraki odak alanlarını çıkarır.
                </p>
                <div className="mt-5 grid gap-4 md:grid-cols-3">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                      Başvuru Odağı
                    </p>
                    <p className="mt-2 text-sm text-white">
                      {dashboard.highMatchJobs
                        ? `${dashboard.highMatchJobs} yüksek uyumlu ilan için CV ve ön yazı özelleştirmesi yapılmalı.`
                        : "Önce watcher run veya job import ile yüksek uyumlu ilan havuzu büyütülmeli."}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                      Skill Gelişimi
                    </p>
                    <p className="mt-2 text-sm text-white">
                      {dashboard.topMissingSkills[0]
                        ? `İlk odak alanı: ${dashboard.topMissingSkills[0].label}.`
                        : "Eksik skill sinyali oluşmadı; mevcut profil güçlü görünüyor."}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                      Operasyon Sağlığı
                    </p>
                    <p className="mt-2 text-sm text-white">
                      {dashboard.notifications
                        ? `${dashboard.notifications} bildirim aktif; arşiv kayıtlarıyla birlikte takip hattı çalışıyor.`
                        : "Watcher bildirim üretmiyor; yeni manual run ile veri tazelenebilir."}
                    </p>
                  </div>
                </div>
              </article>
            </div>
          </section>
        ) : null}

        {activeSection === "profile" ? <ProfileFlow onCompleted={() => setActiveSection("watchers")} /> : null}
        {activeSection === "watchers" ? <WatchersConsole /> : null}
        {activeSection === "recommended" ? <RecommendedJobsConsole /> : null}
        {activeSection === "jobs" ? <JobsConsole /> : null}
        {activeSection === "applications" ? <ApplicationsConsole /> : null}
      </main>
    </AppShell>
  );
}
