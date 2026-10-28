import type {
  ApplicationRecord,
  CandidateProfileRecord,
  JobRecord,
  SectionKey,
  WatcherRecord,
} from "@/app/lib/types";

export type ProcessStepKey = "profile" | "watchers" | "jobs" | "applications";
export type ProcessStepStatus = "active" | "completed" | "pending";

export interface ProcessCriterion {
  label: string;
  satisfied: boolean;
}

export interface ProcessStepState {
  id: ProcessStepKey;
  label: string;
  description: string;
  status: ProcessStepStatus;
  criteria: ProcessCriterion[];
  isComplete: boolean;
}

export interface WorkflowSnapshot {
  steps: ProcessStepState[];
  activeProcess: ProcessStepKey;
  accessibleSections: SectionKey[];
  blockingMessage: string;
}

interface ProcessStepDraft {
  id: ProcessStepKey;
  label: string;
  description: string;
  criteria: ProcessCriterion[];
  isComplete: boolean;
}

const PROCESS_ORDER: ProcessStepKey[] = ["profile", "watchers", "jobs", "applications"];
const ALL_ACCESSIBLE_SECTIONS: SectionKey[] = [
  "overview",
  "profile",
  "watchers",
  "recommended",
  "jobs",
  "applications",
];

function buildProfileCriteria(profile: CandidateProfileRecord | null): ProcessCriterion[] {
  return [
    {
      label: "CV kaydı ilişkilendirildi",
      satisfied: Boolean(profile?.cv_file_id),
    },
    {
      label: "Headline dolduruldu",
      satisfied: Boolean(profile?.profile.headline?.trim()),
    },
    {
      label: "Profesyonel özet hazır",
      satisfied: Boolean(profile?.profile.summary?.trim()),
    },
    {
      label: "En az 1 yetkinlik girildi",
      satisfied: (profile?.profile.skills.length ?? 0) > 0,
    },
    {
      label: "En az 1 lokasyon tercihi var",
      satisfied: (profile?.profile.preferred_locations.length ?? 0) > 0,
    },
  ];
}

function buildWatcherCriteria(watchers: WatcherRecord[]): ProcessCriterion[] {
  return [
    {
      label: "En az 1 watcher oluşturuldu",
      satisfied: watchers.length > 0,
    },
    {
      label: "Minimum skor tanımlandı",
      satisfied: watchers.some((watcher) => watcher.minimum_match_score > 0),
    },
    {
      label: "Bildirim kanalı seçildi",
      satisfied: watchers.some((watcher) => watcher.notification_channels.length > 0),
    },
  ];
}

function buildJobsCriteria(jobs: JobRecord[]): ProcessCriterion[] {
  return [
    {
      label: "En az 1 ilan içe alındı",
      satisfied: jobs.length > 0,
    },
    {
      label: "İlan analizi üretildi",
      satisfied: jobs.some((job) => job.analysis_result?.total_score != null),
    },
    {
      label: "Başvuru önerisi hazır",
      satisfied: jobs.some((job) => Boolean(job.analysis_result?.recommendation_reason)),
    },
  ];
}

function buildApplicationsCriteria(applications: ApplicationRecord[]): ProcessCriterion[] {
  return [
    {
      label: "En az 1 başvuru oluşturuldu",
      satisfied: applications.length > 0,
    },
    {
      label: "Pipeline durumu belirlendi",
      satisfied: applications.some((application) => Boolean(application.status)),
    },
    {
      label: "Takip verisi kaydedildi",
      satisfied: applications.some(
        (application) =>
          Boolean(application.notes?.trim()) ||
          Boolean(application.contact_person?.trim()) ||
          Boolean(application.reminder_at),
      ),
    },
  ];
}

function buildPendingMessage(step: ProcessStepState): string {
  const missingItems = step.criteria
    .filter((criterion) => !criterion.satisfied)
    .map((criterion) => criterion.label.toLocaleLowerCase("tr-TR"));

  if (missingItems.length === 0) {
    return `${step.label} tamamlandı.`;
  }

  return `${step.label} tamamlanmadan sonraki süreç açılmaz. Eksik koşullar: ${missingItems.join(", ")}.`;
}

export function resolveWorkflowSnapshot(input: {
  profile: CandidateProfileRecord | null;
  watchers: WatcherRecord[];
  jobs: JobRecord[];
  applications: ApplicationRecord[];
}): WorkflowSnapshot {
  const draftSteps: ProcessStepDraft[] = [
    {
      id: "profile" as const,
      label: "CV ve Profil",
      description: "CV yükleme, ayrıştırma ve profil onayı",
      criteria: buildProfileCriteria(input.profile),
      isComplete: false,
    },
    {
      id: "watchers" as const,
      label: "İzleme Profili",
      description: "Watcher oluşturma ve bildirim kanalı hazırlığı",
      criteria: buildWatcherCriteria(input.watchers),
      isComplete: false,
    },
    {
      id: "jobs" as const,
      label: "İlan Analizi",
      description: "İlan import, skor ve öneri üretimi",
      criteria: buildJobsCriteria(input.jobs),
      isComplete: false,
    },
    {
      id: "applications" as const,
      label: "Başvuru Pipeline",
      description: "Başvuru oluşturma ve takip verisi kaydı",
      criteria: buildApplicationsCriteria(input.applications),
      isComplete: false,
    },
  ].map((step) => ({
    ...step,
    isComplete: step.criteria.every((criterion) => criterion.satisfied),
  }));

  const firstIncompleteStep = draftSteps.find((step) => !step.isComplete);
  const activeProcess = firstIncompleteStep?.id ?? "applications";

  const steps: ProcessStepState[] = draftSteps.map((step) => {
    const stepIndex = PROCESS_ORDER.indexOf(step.id);
    const activeIndex = PROCESS_ORDER.indexOf(activeProcess);
    let status: ProcessStepStatus = "pending";

    if (stepIndex < activeIndex || (firstIncompleteStep == null && step.isComplete)) {
      status = "completed";
    } else if (step.id === activeProcess) {
      status = firstIncompleteStep == null && step.isComplete ? "completed" : "active";
    }

    return {
      ...step,
      status,
    };
  });

  const accessibleSections: SectionKey[] = ALL_ACCESSIBLE_SECTIONS;

  const activeStep = steps.find((step) => step.id === activeProcess) ?? steps[0];
  const allCompleted = steps.every((step) => step.isComplete);

  return {
    steps,
    activeProcess,
    accessibleSections,
    blockingMessage: allCompleted ? "Tüm süreçler tamamlandı." : buildPendingMessage(activeStep),
  };
}
