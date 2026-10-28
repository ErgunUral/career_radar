"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

import type {
  ApplicationRecord,
  CandidateProfileRecord,
  CvFileRecord,
  JobRecord,
  SectionKey,
  WatcherRecord,
} from "@/app/lib/types";

interface CareerRadarState {
  activeSection: SectionKey;
  userId: string;
  cvFile: CvFileRecord | null;
  profile: CandidateProfileRecord | null;
  lastWatcher: WatcherRecord | null;
  lastJob: JobRecord | null;
  lastApplication: ApplicationRecord | null;
  setActiveSection: (section: SectionKey) => void;
  setUserId: (userId: string) => void;
  setCvFile: (cvFile: CvFileRecord | null) => void;
  setProfile: (profile: CandidateProfileRecord | null) => void;
  setLastWatcher: (watcher: WatcherRecord | null) => void;
  setLastJob: (job: JobRecord | null) => void;
  setLastApplication: (application: ApplicationRecord | null) => void;
}

export const useCareerRadarStore = create<CareerRadarState>()(
  persist(
    (set) => ({
      activeSection: "overview",
      userId: "user-1",
      cvFile: null,
      profile: null,
      lastWatcher: null,
      lastJob: null,
      lastApplication: null,
      setActiveSection: (section) => set({ activeSection: section }),
      setUserId: (userId) => set({ userId }),
      setCvFile: (cvFile) => set({ cvFile }),
      setProfile: (profile) => set({ profile }),
      setLastWatcher: (lastWatcher) => set({ lastWatcher }),
      setLastJob: (lastJob) => set({ lastJob }),
      setLastApplication: (lastApplication) => set({ lastApplication }),
    }),
    {
      name: "careerradar-onboarding-store",
      partialize: (state) => ({
        activeSection: state.activeSection,
        userId: state.userId,
        cvFile: state.cvFile,
        profile: state.profile,
        lastWatcher: state.lastWatcher,
        lastJob: state.lastJob,
        lastApplication: state.lastApplication,
      }),
    },
  ),
);
