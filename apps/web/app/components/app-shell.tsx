"use client";

import {
  Blocks,
  BellRing,
  BriefcaseBusiness,
  ChartNoAxesCombined,
  FileUp,
  FolderKanban,
  LockKeyhole,
  Radar,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import type { SectionKey } from "@/app/lib/types";
import type { ProcessStepState } from "@/app/lib/workflow";

interface AppShellProps {
  activeSection: SectionKey;
  onSectionChange: (section: SectionKey) => void;
  onLockedSectionAttempt: (section: SectionKey) => void;
  accessibleSections: SectionKey[];
  processSteps: ProcessStepState[];
  workflowNotice?: string | null;
  toastMessage?: string | null;
  children: React.ReactNode;
}

const navItems: Array<{
  id: SectionKey;
  label: string;
  description: string;
  icon: typeof Radar;
}> = [
  {
    id: "overview",
    label: "Kontrol Merkezi",
    description: "Metrikler, durum ve yol haritası",
    icon: ChartNoAxesCombined,
  },
  {
    id: "profile",
    label: "CV ve Profil",
    description: "Dosya yükleme ve ayrıştırma doğrulaması",
    icon: FileUp,
  },
  {
    id: "watchers",
    label: "İzleme Profilleri",
    description: "Watcher oluşturma, bildirim ve arşiv görünümü",
    icon: BriefcaseBusiness,
  },
  {
    id: "recommended",
    label: "Önerilen İlanlar",
    description: "Yüksek uyumlu ve başvuruya yakın fırsatlar",
    icon: Sparkles,
  },
  {
    id: "jobs",
    label: "İş İlanları",
    description: "Manuel import, analiz ve eşleşme görünümü",
    icon: Blocks,
  },
  {
    id: "applications",
    label: "Başvurularım",
    description: "Pipeline, durum geçişleri ve takip görünümü",
    icon: FolderKanban,
  },
];

export function AppShell({
  activeSection,
  onSectionChange,
  onLockedSectionAttempt,
  accessibleSections,
  processSteps,
  workflowNotice,
  toastMessage,
  children,
}: AppShellProps) {
  const currentItem = navItems.find((item) => item.id === activeSection) ?? navItems[0];
  const activeProcess = processSteps.find((step) => step.status === "active") ?? processSteps.at(-1);

  function handleNavClick(section: SectionKey) {
    if (accessibleSections.includes(section)) {
      onSectionChange(section);
      return;
    }
    onLockedSectionAttempt(section);
  }

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-[1600px] gap-6 px-6 py-8 lg:px-10">
      {toastMessage ? (
        <div className="fixed right-4 top-4 z-50 max-w-md rounded-[22px] border border-amber-300/25 bg-[rgba(34,20,5,0.94)] px-5 py-4 text-sm text-amber-100 shadow-[0_18px_50px_rgba(0,0,0,0.35)] backdrop-blur">
          <p className="font-semibold text-white">Süreç kilidi aktif</p>
          <p className="mt-1 leading-6">{toastMessage}</p>
        </div>
      ) : null}
      <div className="fixed inset-x-0 top-0 z-40 border-b border-white/10 bg-[linear-gradient(180deg,rgba(7,13,27,0.96),rgba(7,13,27,0.84))] px-4 py-3 shadow-[0_12px_40px_rgba(2,8,20,0.35)] backdrop-blur xl:hidden">
        <div className="mx-auto max-w-[1600px]">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <p className="text-[10px] uppercase tracking-[0.28em] text-emerald-200/80">
                CareerRadar AI
              </p>
              <p className="mt-1 text-sm font-semibold text-white">{currentItem.label}</p>
              <p className="mt-1 text-xs leading-5 text-slate-400">{currentItem.description}</p>
            </div>
            <div className="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1.5 text-[11px] text-emerald-100">
              Mobil erişim
            </div>
          </div>

          <div className="-mx-1 flex items-center gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = item.id === activeSection;
              const isAccessible = accessibleSections.includes(item.id);
              return (
                <button
                  key={item.id}
                  className={`inline-flex shrink-0 items-center gap-2 rounded-full border px-4 py-2.5 text-sm transition ${
                    isActive
                      ? "border-emerald-300/40 bg-emerald-300/12 text-emerald-100 shadow-[0_10px_30px_rgba(16,185,129,0.12)]"
                      : isAccessible
                        ? "border-white/10 bg-white/[0.04] text-slate-300"
                        : "border-white/5 bg-white/[0.02] text-slate-500"
                  }`}
                  onClick={() => handleNavClick(item.id)}
                  type="button"
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                  {!isAccessible ? <LockKeyhole className="h-3.5 w-3.5" /> : null}
                </button>
              );
            })}
          </div>
        </div>
      </div>
      <aside className="hidden w-[320px] shrink-0 flex-col justify-between rounded-[32px] border border-white/10 bg-[rgba(7,13,27,0.88)] p-6 shadow-[0_20px_80px_rgba(2,8,20,0.55)] backdrop-blur xl:flex">
        <div className="space-y-8">
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-4 py-2 text-[11px] uppercase tracking-[0.32em] text-emerald-200">
              <Radar className="h-4 w-4" />
              CareerRadar AI
            </div>
            <div>
              <p className="font-display text-3xl text-white">
                Yönetici seviyesi iş takibi için tek merkez.
              </p>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                CV&apos;ni ayrıştır, profilini doğrula ve politika uyumlu watcher
                profilleriyle yüksek uyumlu ilanları sürekli izle.
              </p>
            </div>
          </div>

          <nav className="space-y-3">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = item.id === activeSection;
              const isAccessible = accessibleSections.includes(item.id);
              return (
                <button
                  key={item.id}
                  className={`w-full rounded-[24px] border p-4 text-left transition ${
                    isActive
                      ? "border-emerald-300/40 bg-emerald-300/10 shadow-[0_16px_40px_rgba(16,185,129,0.12)]"
                      : isAccessible
                        ? "border-white/8 bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.05]"
                        : "border-white/8 bg-white/[0.02] text-slate-500"
                  }`}
                  onClick={() => handleNavClick(item.id)}
                  type="button"
                >
                  <div className="flex items-start gap-3">
                    <div className="rounded-2xl border border-white/10 bg-slate-950/80 p-3 text-emerald-200">
                      <Icon className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-white">{item.label}</p>
                      <p className="mt-1 text-xs leading-5 text-slate-400">
                        {item.description}
                      </p>
                    </div>
                    {!isAccessible ? (
                      <div className="ml-auto rounded-full border border-white/10 px-3 py-1 text-[11px] text-slate-500">
                        Kilitli
                      </div>
                    ) : null}
                  </div>
                </button>
              );
            })}
          </nav>

          <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                  Süreç Akışı
                </p>
                <p className="mt-2 text-sm font-medium text-white">
                  {activeProcess?.label ?? "Workflow"}
                </p>
              </div>
              <div className="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1.5 text-[11px] text-emerald-100">
                {activeProcess?.status === "completed" ? "Tamamlandı" : "Aktif"}
              </div>
            </div>

            <div className="mt-5 grid gap-4">
              {processSteps.map((step, index) => (
                <div key={step.id}>
                  <div className="mb-2 flex items-center justify-between gap-3 text-xs">
                    <span
                      className={
                        step.status === "completed"
                          ? "text-emerald-200"
                          : step.status === "active"
                            ? "text-white"
                            : "text-slate-500"
                      }
                    >
                      {index + 1}. {step.label}
                    </span>
                    <span
                      className={
                        step.status === "completed"
                          ? "text-emerald-200"
                          : step.status === "active"
                            ? "text-amber-200"
                            : "text-slate-500"
                      }
                    >
                      {step.status === "completed"
                        ? "Tamamlandı"
                        : step.status === "active"
                          ? "Aktif"
                          : "Beklemede"}
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-white/5">
                    <div
                      className={`h-2 rounded-full ${
                        step.status === "completed"
                          ? "bg-emerald-300"
                          : step.status === "active"
                            ? "bg-amber-300"
                            : "bg-white/10"
                      }`}
                      style={{
                        width:
                          step.status === "completed"
                            ? "100%"
                            : step.status === "active"
                              ? `${Math.max(
                                  16,
                                  Math.round(
                                    (step.criteria.filter((criterion) => criterion.satisfied).length /
                                      step.criteria.length) *
                                      100,
                                  ),
                                )}%`
                              : "12%",
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(16,185,129,0.16),rgba(15,23,42,0.16))] p-5">
            <div className="flex items-center gap-3">
              <ShieldCheck className="h-5 w-5 text-emerald-200" />
              <p className="text-sm font-medium text-white">Politika uyumlu akış</p>
            </div>
            <p className="mt-3 text-xs leading-5 text-slate-300">
              LinkedIn scraping yerine kullanıcı tanımlı kriterler, izinli kaynaklar
              ve arşivlenebilir sync run yapısı kullanılır.
            </p>
          </div>
        </div>

        <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
          <div className="flex items-center gap-3 text-slate-200">
            <BellRing className="h-4 w-4 text-emerald-200" />
            <p className="text-sm font-medium">Hazır sonraki fazlar</p>
          </div>
          <p className="mt-3 text-xs leading-5 text-slate-400">
            Jobs ve applications ekranları aktif; sıradaki genişleme reports ve
            advisor katmanı olabilir.
          </p>
        </div>
      </aside>

      <div className="flex-1 pt-28 sm:pt-24 xl:pt-0">
        {workflowNotice ? (
          <div className="mb-6 rounded-[24px] border border-amber-300/20 bg-amber-300/10 px-5 py-4 text-sm text-amber-100">
            {workflowNotice}
          </div>
        ) : null}
        {children}
      </div>
    </div>
  );
}
