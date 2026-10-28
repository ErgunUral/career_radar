"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CircleCheckBig,
  FolderKanban,
  LoaderCircle,
  SendHorizontal,
} from "lucide-react";

import {
  createApplication,
  listApplications,
  listJobs,
  updateApplication,
} from "@/app/lib/api";
import type { ApplicationRecord, JobRecord } from "@/app/lib/types";
import { useCareerRadarStore } from "@/app/stores/onboarding-store";

const PIPELINE_COLUMNS = [
  "Keşfedildi",
  "Başvurulacak",
  "Başvuruldu",
  "İnsan kaynakları görüşmesi",
  "Teknik görüşme",
  "Teklif alındı",
];

function isOverdue(reminderAt?: string | null) {
  if (!reminderAt) return false;
  return new Date(reminderAt).getTime() < Date.now();
}

function toDateTimeLocal(daysFromNow: number) {
  const date = new Date();
  date.setDate(date.getDate() + daysFromNow);
  date.setMinutes(0, 0, 0);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}

function isJobOpen(job: JobRecord) {
  const metadata = job.metadata ?? {};
  if (metadata.application_open === false) return false;
  if (metadata.accepting_applications === false) return false;
  if (typeof metadata.expires_at === "string") {
    const expiresAt = new Date(metadata.expires_at);
    if (!Number.isNaN(expiresAt.getTime()) && expiresAt.getTime() < Date.now()) {
      return false;
    }
  }
  if (typeof metadata.is_active === "boolean") {
    return metadata.is_active;
  }
  return true;
}

export function ApplicationsConsole() {
  const { lastApplication, lastJob, userId, setLastApplication } = useCareerRadarStore();
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [applications, setApplications] = useState<ApplicationRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [selectedApplicationId, setSelectedApplicationId] = useState<string | null>(null);
  const [detailForm, setDetailForm] = useState({
    notes: "",
    contact_person: "",
    expected_salary: "",
    offered_salary: "",
    reminder_at: "",
  });
  const [form, setForm] = useState({
    job_id: "",
    status: "Başvurulacak",
    notes: "CV özeti role göre güncellenecek.",
    contact_person: "Hiring Team",
    expected_salary: "170000",
  });

  const refreshData = useCallback(async () => {
    try {
      setDataLoading(true);
      const [jobList, applicationList] = await Promise.all([
        listJobs(userId),
        listApplications(userId),
      ]);
      const openJobs = jobList.filter((job) => isJobOpen(job));
      setJobs(jobList);
      setApplications(applicationList);
      setSelectedApplicationId((current) => current ?? lastApplication?.id ?? applicationList[0]?.id ?? null);
      if (lastApplication?.job_id && openJobs.some((job) => job.id === lastApplication.job_id)) {
        setForm((current) => ({ ...current, job_id: lastApplication.job_id }));
      } else if (lastJob?.id && openJobs.some((job) => job.id === lastJob.id)) {
        setForm((current) => ({ ...current, job_id: lastJob.id }));
      } else if (!form.job_id && openJobs[0]) {
        setForm((current) => ({ ...current, job_id: openJobs[0].id }));
      } else if (!openJobs.some((job) => job.id === form.job_id)) {
        setForm((current) => ({ ...current, job_id: openJobs[0]?.id ?? "" }));
      }
    } catch (refreshError) {
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : "Başvuru verileri alınamadı.",
      );
    } finally {
      setDataLoading(false);
    }
  }, [form.job_id, lastApplication?.id, lastApplication?.job_id, lastJob?.id, userId]);

  useEffect(() => {
    void refreshData();
  }, [refreshData]);

  async function handleCreateApplication() {
    if (!form.job_id) {
      setError("Önce başvuruya dönüştürülecek bir ilan seç.");
      return;
    }
    try {
      setLoading(true);
      setError(null);
      setMessage(null);
      const created = await createApplication({
        user_id: userId,
        job_id: form.job_id,
        status: form.status,
        notes: form.notes,
        contact_person: form.contact_person,
        expected_salary: Number(form.expected_salary),
      });
      setLastApplication(created);
      setMessage("Başvuru kaydı pipeline’a eklendi.");
      await refreshData();
    } catch (createError) {
      setError(
        createError instanceof Error
          ? createError.message
          : "Başvuru kaydı oluşturulamadı.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function moveApplication(applicationId: string, status: string) {
    try {
      setLoading(true);
      const updated = await updateApplication(applicationId, { status });
      setLastApplication(updated);
      await refreshData();
    } catch (updateError) {
      setError(
        updateError instanceof Error
          ? updateError.message
          : "Başvuru durumu güncellenemedi.",
      );
    } finally {
      setLoading(false);
    }
  }

  const jobsById = useMemo(
    () => new Map(jobs.map((job) => [job.id, job])),
    [jobs],
  );

  const activeJobChoices = useMemo(
    () => jobs.filter((job) => isJobOpen(job)),
    [jobs],
  );

  const grouped = useMemo(
    () =>
      PIPELINE_COLUMNS.map((status) => ({
        status,
        items: applications.filter((application) => application.status === status),
      })),
    [applications],
  );

  const reminderSummary = useMemo(() => {
    const itemsWithReminder = applications.filter((item) => item.reminder_at);
    const overdue = itemsWithReminder.filter((item) => isOverdue(item.reminder_at));
    const upcoming = [...itemsWithReminder]
      .filter((item) => !isOverdue(item.reminder_at))
      .sort((left, right) =>
        new Date(left.reminder_at ?? "").getTime() - new Date(right.reminder_at ?? "").getTime(),
      )
      .slice(0, 4);

    return {
      total: itemsWithReminder.length,
      overdue: overdue.length,
      upcoming,
    };
  }, [applications]);

  const selectedApplication = useMemo(
    () =>
      applications.find((application) => application.id === selectedApplicationId) ??
      applications[0] ??
      null,
    [applications, selectedApplicationId],
  );

  useEffect(() => {
    if (!selectedApplication) return;
    setDetailForm({
      notes: selectedApplication.notes ?? "",
      contact_person: selectedApplication.contact_person ?? "",
      expected_salary: selectedApplication.expected_salary?.toString() ?? "",
      offered_salary: selectedApplication.offered_salary?.toString() ?? "",
      reminder_at: selectedApplication.reminder_at
        ? new Date(selectedApplication.reminder_at).toISOString().slice(0, 16)
        : "",
    });
  }, [selectedApplication]);

  async function handleDetailSave() {
    if (!selectedApplication) return;
    try {
      setLoading(true);
      setError(null);
      setMessage(null);
      const updated = await updateApplication(selectedApplication.id, {
        notes: detailForm.notes,
        contact_person: detailForm.contact_person,
        expected_salary: detailForm.expected_salary ? Number(detailForm.expected_salary) : null,
        offered_salary: detailForm.offered_salary ? Number(detailForm.offered_salary) : null,
        reminder_at: detailForm.reminder_at
          ? new Date(detailForm.reminder_at).toISOString()
          : null,
      });
      setLastApplication(updated);
      setMessage("Başvuru detayları güncellendi.");
      await refreshData();
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Başvuru detayları güncellenemedi.",
      );
    } finally {
      setLoading(false);
    }
  }

  function applyQuickReminder(daysFromNow: number) {
    setDetailForm((current) => ({
      ...current,
      reminder_at: toDateTimeLocal(daysFromNow),
    }));
  }

  return (
    <section className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[0.88fr_1.12fr]">
        <div className="rounded-[32px] border border-white/10 bg-[rgba(9,15,30,0.88)] p-6 shadow-[0_18px_60px_rgba(2,8,20,0.35)]">
          <div className="flex items-center gap-3">
            <FolderKanban className="h-5 w-5 text-emerald-200" />
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-slate-500">Adım 4</p>
              <h2 className="mt-2 font-display text-3xl text-white">
                Başvuru pipeline&apos;ını çalıştır.
              </h2>
            </div>
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-300">
            Analiz edilen ilanları tek tıkla başvuru sürecine taşıyabilir, durum
            geçişlerini yönetebilir ve mülakat hattını tek panelde izleyebilirsin.
          </p>

          <div className="mt-6 grid gap-4">
            <label>
              <span className="mb-2 block text-xs uppercase tracking-[0.22em] text-slate-500">
                İlan seç
              </span>
              <select
                className="h-12 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 text-sm text-white outline-none transition focus:border-emerald-300/40"
                onChange={(event) =>
                  setForm((current) => ({ ...current, job_id: event.target.value }))
                }
                value={form.job_id}
              >
                <option value="">İlan seç</option>
                {activeJobChoices.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title} - {job.company_name}
                  </option>
                ))}
              </select>
              {!activeJobChoices.length ? (
                <p className="mt-2 text-xs text-slate-400">
                  Başvuruya açık ilan kalmadığında kapanmış kayıtlar bu seçimden otomatik
                  çıkarılır.
                </p>
              ) : null}
            </label>

            {Object.entries(form)
              .filter(([key]) => key !== "job_id")
              .map(([key, value]) => (
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

          <button
            className="mt-6 inline-flex h-12 items-center gap-2 rounded-full bg-emerald-300 px-5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
            disabled={loading}
            onClick={handleCreateApplication}
            type="button"
          >
            {loading ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <SendHorizontal className="h-4 w-4" />
            )}
            Başvuru Kaydı Oluştur
          </button>

          {error ? <p className="mt-4 text-sm text-rose-300">{error}</p> : null}
          {message ? <p className="mt-4 text-sm text-emerald-200">{message}</p> : null}
        </div>

        <div className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
          <div className="flex items-center gap-3">
            <CircleCheckBig className="h-5 w-5 text-emerald-200" />
            <h3 className="text-lg font-semibold text-white">Başvuru özeti</h3>
          </div>
          <div className="mt-5 grid gap-4 md:grid-cols-3">
            <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-4">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Toplam</p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {dataLoading ? "..." : applications.length}
              </p>
            </div>
            <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-4">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                Görüşme Aşaması
              </p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {dataLoading
                  ? "..."
                  : (
                  applications.filter((item) =>
                    [
                      "İnsan kaynakları görüşmesi",
                      "Teknik görüşme",
                      "Yönetici görüşmesi",
                    ].includes(item.status),
                  ).length
                )}
              </p>
            </div>
            <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-4">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Teklif</p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {dataLoading
                  ? "..."
                  : applications.filter((item) => item.status === "Teklif alındı").length}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.78fr_1.22fr]">
        <div className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
          <div className="flex items-center gap-3">
            <CircleCheckBig className="h-5 w-5 text-emerald-200" />
            <div>
              <h3 className="text-lg font-semibold text-white">Reminder Takvimi</h3>
              <p className="mt-1 text-xs text-slate-500">
                Takip zamanı gelen veya yaklaşan başvuruları özetler.
              </p>
            </div>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-3">
            <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-4">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Reminder</p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {dataLoading ? "..." : reminderSummary.total}
              </p>
            </div>
            <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-4">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Geciken</p>
              <p className="mt-3 text-3xl font-semibold text-rose-200">
                {dataLoading ? "..." : reminderSummary.overdue}
              </p>
            </div>
            <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-4">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Yaklaşan</p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {dataLoading ? "..." : reminderSummary.upcoming.length}
              </p>
            </div>
          </div>

          <div className="mt-5 space-y-3">
            {dataLoading ? (
              <div className="rounded-[22px] border border-white/10 bg-slate-950/70 p-4">
                <div className="h-4 w-36 animate-pulse rounded bg-white/10" />
                <div className="mt-3 h-3 w-28 animate-pulse rounded bg-white/10" />
              </div>
            ) : null}
            {reminderSummary.upcoming.map((application) => {
              const job = jobsById.get(application.job_id);
              return (
                <button
                  className="block w-full rounded-[22px] border border-white/10 bg-slate-950/70 p-4 text-left transition hover:border-emerald-300/40 hover:bg-emerald-300/[0.06]"
                  key={application.id}
                  onClick={() => setSelectedApplicationId(application.id)}
                  type="button"
                >
                  <p className="text-sm font-semibold text-white">
                    {job?.title ?? application.job_id}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    {job?.company_name ?? "Şirket bilgisi yok"} •{" "}
                    {new Date(application.reminder_at ?? "").toLocaleString("tr-TR")}
                  </p>
                </button>
              );
            })}
            {!dataLoading && !reminderSummary.upcoming.length ? (
              <p className="text-sm text-slate-400">
                Yaklaşan reminder görünmüyor. Detay editöründen hızlı reminder ekleyebilirsin.
              </p>
            ) : null}
          </div>
        </div>

        <div className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
          <div className="flex items-center gap-3">
            <CircleCheckBig className="h-5 w-5 text-emerald-200" />
            <div>
              <h3 className="text-lg font-semibold text-white">Operasyon önerileri</h3>
              <p className="mt-1 text-xs text-slate-500">
                Başvuru hattında gecikme riskini azaltmak için sistemin önerdiği kısa aksiyonlar.
              </p>
            </div>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-3">
            <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-4">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Bugün</p>
              <p className="mt-2 text-sm text-white">
                {reminderSummary.overdue
                  ? `${reminderSummary.overdue} gecikmiş reminder önce ele alınmalı.`
                  : "Gecikmiş reminder görünmüyor."}
              </p>
            </div>
            <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-4">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Dönüşüm</p>
              <p className="mt-2 text-sm text-white">
                {applications.length
                  ? `${applications.length} başvuru için düzenli reminder akışı hazır.`
                  : "Önce en az bir başvuru oluşturulmalı."}
              </p>
            </div>
            <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-4">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Takvim</p>
              <p className="mt-2 text-sm text-white">
                Hızlı reminder butonları ile 1, 3 veya 7 gün sonrası için takip planlanabilir.
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 2xl:grid-cols-[1.25fr_0.75fr]">
        <div className="overflow-x-auto rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
          <div className="flex min-w-[1280px] gap-4">
          {grouped.map((column) => (
            <div
              className="min-h-[420px] w-[280px] shrink-0 rounded-[28px] border border-white/10 bg-slate-950/70 p-4"
              key={column.status}
            >
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-white">{column.status}</p>
                <span className="rounded-full border border-white/10 px-2.5 py-1 text-xs text-slate-400">
                  {column.items.length}
                </span>
              </div>

              <div className="mt-4 space-y-3">
                {dataLoading ? (
                  <div className="rounded-[22px] border border-white/10 bg-white/[0.04] p-4">
                    <div className="h-4 w-32 animate-pulse rounded bg-white/10" />
                    <div className="mt-3 h-3 w-24 animate-pulse rounded bg-white/10" />
                    <div className="mt-4 h-12 animate-pulse rounded bg-white/5" />
                  </div>
                ) : null}
                {column.items.map((application) => {
                  const nextStatus =
                    PIPELINE_COLUMNS[
                      Math.min(
                        PIPELINE_COLUMNS.indexOf(application.status) + 1,
                        PIPELINE_COLUMNS.length - 1,
                      )
                    ];
                  const job = jobsById.get(application.job_id);
                  return (
                    <article
                      className={`rounded-[22px] border p-4 transition ${
                        application.id === selectedApplicationId
                          ? "border-emerald-300/40 bg-emerald-300/[0.08]"
                          : "border-white/10 bg-white/[0.04]"
                      }`}
                      key={application.id}
                    >
                      <p className="text-sm font-semibold text-white">
                        {job?.title ?? application.job_id}
                      </p>
                      <p className="mt-1 text-xs text-slate-400">
                        {job?.company_name ?? "Şirket bilgisi yok"}
                      </p>
                      <p className="mt-3 text-xs leading-5 text-slate-400">
                        {application.notes || "Henüz not eklenmedi."}
                      </p>
                      <button
                        className="mt-4 inline-flex w-full items-center justify-center rounded-full border border-white/10 px-3 py-2 text-xs text-slate-200 transition hover:border-emerald-300/40 hover:bg-emerald-300/10"
                        onClick={() => setSelectedApplicationId(application.id)}
                        type="button"
                      >
                        Detayı Düzenle
                      </button>
                      <button
                        className="mt-3 inline-flex w-full items-center justify-center rounded-full border border-white/10 px-3 py-2 text-xs text-slate-200 transition hover:border-emerald-300/40 hover:bg-emerald-300/10"
                        onClick={() => void moveApplication(application.id, nextStatus)}
                        type="button"
                      >
                        Sonraki durum: {nextStatus}
                      </button>
                    </article>
                  );
                })}
                {!dataLoading && !column.items.length ? (
                  <p className="text-xs text-slate-500">Bu kolonda kayıt yok.</p>
                ) : null}
              </div>
            </div>
          ))}
          </div>
        </div>

        <div className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
          <div className="flex items-center gap-3">
            <CircleCheckBig className="h-5 w-5 text-emerald-200" />
            <div>
              <h3 className="text-lg font-semibold text-white">Başvuru detay editörü</h3>
              <p className="mt-1 text-xs text-slate-500">
                Not, reminder, maaş ve teklif alanlarını seçili kayıt üzerinden yönet.
              </p>
            </div>
          </div>

          {selectedApplication ? (
            <div className="mt-5 space-y-4">
              <div className="rounded-[24px] border border-white/10 bg-slate-950/70 p-4">
                <p className="text-sm font-semibold text-white">
                  {jobsById.get(selectedApplication.job_id)?.title ?? selectedApplication.job_id}
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  {jobsById.get(selectedApplication.job_id)?.company_name ?? "Şirket bilgisi yok"} •{" "}
                  {selectedApplication.status}
                </p>
              </div>

              {(
                [
                  ["notes", "Notlar", "text"],
                  ["contact_person", "İletişim Kişisi", "text"],
                  ["expected_salary", "Beklenen Maaş", "number"],
                  ["offered_salary", "Teklif Edilen Maaş", "number"],
                  ["reminder_at", "Hatırlatma Zamanı", "datetime-local"],
                ] as const
              ).map(([key, label, type]) => (
                <label key={key}>
                  <span className="mb-2 block text-xs uppercase tracking-[0.22em] text-slate-500">
                    {label}
                  </span>
                  {key === "notes" ? (
                    <textarea
                      className="min-h-28 w-full rounded-[24px] border border-white/10 bg-slate-950/80 px-4 py-3 text-sm leading-6 text-white outline-none transition focus:border-emerald-300/40"
                      onChange={(event) =>
                        setDetailForm((current) => ({ ...current, [key]: event.target.value }))
                      }
                      value={detailForm[key]}
                    />
                  ) : (
                    <input
                      className="h-12 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 text-sm text-white outline-none transition focus:border-emerald-300/40"
                      onChange={(event) =>
                        setDetailForm((current) => ({ ...current, [key]: event.target.value }))
                      }
                      type={type}
                      value={detailForm[key]}
                    />
                  )}
                </label>
              ))}

              <div>
                <span className="mb-2 block text-xs uppercase tracking-[0.22em] text-slate-500">
                  Hızlı Reminder
                </span>
                <div className="flex flex-wrap gap-2">
                  {[
                    { label: "Bugün", days: 0 },
                    { label: "+1 Gün", days: 1 },
                    { label: "+3 Gün", days: 3 },
                    { label: "+7 Gün", days: 7 },
                  ].map((item) => (
                    <button
                      className="rounded-full border border-white/10 px-3 py-2 text-xs text-slate-200 transition hover:border-emerald-300/40 hover:bg-emerald-300/10"
                      key={item.label}
                      onClick={() => applyQuickReminder(item.days)}
                      type="button"
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>

              <button
                className="inline-flex h-12 items-center gap-2 rounded-full bg-emerald-300 px-5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
                disabled={loading}
                onClick={handleDetailSave}
                type="button"
              >
                {loading ? (
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                ) : (
                  <SendHorizontal className="h-4 w-4" />
                )}
                Detayı Kaydet
              </button>
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-400">
              Bir başvuru seçildiğinde detay editörü burada görünür.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
