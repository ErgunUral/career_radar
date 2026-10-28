"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  FileBadge2,
  LoaderCircle,
  Sparkles,
  Upload,
} from "lucide-react";

import { parseCv, updateProfile, uploadCv } from "@/app/lib/api";
import type { CandidateProfileRecord } from "@/app/lib/types";
import { useCareerRadarStore } from "@/app/stores/onboarding-store";

function arrayToText(items: string[]) {
  return items.join(", ");
}

function textToArray(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

interface ProfileFlowProps {
  onCompleted?: () => void;
}

export function ProfileFlow({ onCompleted }: ProfileFlowProps) {
  const { userId, setUserId, cvFile, setCvFile, profile, setProfile } =
    useCareerRadarStore();
  const [language, setLanguage] = useState("tr");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loadingState, setLoadingState] = useState<
    "idle" | "uploading" | "parsing" | "saving"
  >("idle");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [form, setForm] = useState({
    headline: "",
    summary: "",
    total_experience_years: "0",
    management_years: "0",
    team_size_managed: "0",
    skills: "",
    industries: "",
    languages: "",
    certifications: "",
    educations: "",
    preferred_locations: "",
  });

  useEffect(() => {
    if (!profile) return;
    setForm({
      headline: profile.profile.headline,
      summary: profile.profile.summary,
      total_experience_years: String(profile.profile.total_experience_years ?? 0),
      management_years: String(profile.profile.management_years ?? 0),
      team_size_managed: String(profile.profile.team_size_managed ?? 0),
      skills: arrayToText(profile.profile.skills),
      industries: arrayToText(profile.profile.industries),
      languages: arrayToText(profile.profile.languages),
      certifications: arrayToText(profile.profile.certifications),
      educations: arrayToText(profile.profile.educations),
      preferred_locations: arrayToText(profile.profile.preferred_locations),
    });
  }, [profile]);

  const metrics = useMemo(
    () => [
      {
        label: "Beceri",
        value: profile?.profile.skills.length ?? 0,
      },
      {
        label: "Sektör",
        value: profile?.profile.industries.length ?? 0,
      },
      {
        label: "Hedef Rol",
        value: profile?.target_positions.length ?? 0,
      },
    ],
    [profile],
  );

  async function handleUploadAndParse() {
    if (!selectedFile) {
      setError("Lütfen PDF veya DOCX formatında bir CV seç.");
      return;
    }

    try {
      setError(null);
      setSuccess(null);
      setLoadingState("uploading");
      const uploadResponse = await uploadCv({
        file: selectedFile,
        userId,
        language,
      });
      setCvFile(uploadResponse.file);

      setLoadingState("parsing");
      const parsedProfile = await parseCv(uploadResponse.file.id);
      setProfile(parsedProfile);
      setSuccess("CV yüklendi, ayrıştırıldı ve profil ön izlemesi hazırlandı.");
    } catch (uploadError) {
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "CV yükleme akışı tamamlanamadı.",
      );
    } finally {
      setLoadingState("idle");
    }
  }

  async function handleProfileSave() {
    if (!profile) return;
    try {
      setError(null);
      setSuccess(null);
      setLoadingState("saving");
      const updatedProfile: Partial<CandidateProfileRecord["profile"]> = {
        headline: form.headline,
        summary: form.summary,
        total_experience_years: Number(form.total_experience_years),
        management_years: Number(form.management_years),
        team_size_managed: Number(form.team_size_managed),
        skills: textToArray(form.skills),
        industries: textToArray(form.industries),
        languages: textToArray(form.languages),
        certifications: textToArray(form.certifications),
        educations: textToArray(form.educations),
        preferred_locations: textToArray(form.preferred_locations),
      };
      const response = await updateProfile(profile.id, updatedProfile);
      setProfile(response);
      setSuccess("Profil alanları kaydedildi ve watcher kullanımına hazır.");
      onCompleted?.();
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Profil güncellenemedi.",
      );
    } finally {
      setLoadingState("idle");
    }
  }

  return (
    <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
      <div className="rounded-[32px] border border-white/10 bg-[rgba(9,15,30,0.88)] p-6 shadow-[0_18px_60px_rgba(2,8,20,0.35)]">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-emerald-200/80">
              Adım 1
            </p>
            <h2 className="mt-3 font-display text-3xl text-white">
              CV yükle, ayrıştır, düzelt.
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
              Bu ekran backend&apos;de kurduğun CV parse akışına doğrudan bağlıdır.
              Yüklenen dosya kaydedilir, profil çıkarılır ve doğrulama için düzenlenebilir
              alanlara dönüştürülür.
            </p>
          </div>
          <div className="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-4 py-2 text-xs text-emerald-100">
            {cvFile?.parse_status === "parsed" ? "Ayrıştırıldı" : "Bekliyor"}
          </div>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          <label className="space-y-2">
            <span className="text-xs uppercase tracking-[0.24em] text-slate-400">
              Kullanıcı ID
            </span>
            <input
              className="h-12 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 text-sm text-white outline-none transition focus:border-emerald-300/50"
              onChange={(event) => setUserId(event.target.value)}
              value={userId}
            />
          </label>
          <label className="space-y-2">
            <span className="text-xs uppercase tracking-[0.24em] text-slate-400">
              Dil
            </span>
            <select
              className="h-12 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 text-sm text-white outline-none transition focus:border-emerald-300/50"
              onChange={(event) => setLanguage(event.target.value)}
              value={language}
            >
              <option value="tr">Türkçe</option>
              <option value="en">İngilizce</option>
            </select>
          </label>
          <label className="space-y-2">
            <span className="text-xs uppercase tracking-[0.24em] text-slate-400">
              CV Dosyası
            </span>
            <input
              accept=".pdf,.docx"
              className="block h-12 w-full rounded-2xl border border-dashed border-white/12 bg-slate-950/80 px-4 py-3 text-sm text-slate-300 file:mr-4 file:rounded-full file:border-0 file:bg-emerald-300/10 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-emerald-100"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              type="file"
            />
          </label>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button
            className="inline-flex h-12 items-center gap-2 rounded-full bg-emerald-300 px-5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
            disabled={loadingState !== "idle"}
            onClick={handleUploadAndParse}
            type="button"
          >
            {loadingState === "idle" ? (
              <Upload className="h-4 w-4" />
            ) : (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            )}
            CV Yükle ve Ayrıştır
          </button>
          {cvFile ? (
            <span className="inline-flex items-center gap-2 text-sm text-slate-300">
              <FileBadge2 className="h-4 w-4 text-emerald-200" />
              {cvFile.filename}
            </span>
          ) : null}
        </div>

        {error ? <p className="mt-4 text-sm text-rose-300">{error}</p> : null}
        {success ? <p className="mt-4 text-sm text-emerald-200">{success}</p> : null}

        <div className="mt-8 grid gap-4 md:grid-cols-2">
          {Object.entries(form).map(([key, value]) => {
            const isSummary = key === "summary";
            return (
              <label className={isSummary ? "md:col-span-2" : ""} key={key}>
                <span className="mb-2 block text-xs uppercase tracking-[0.24em] text-slate-500">
                  {key.replaceAll("_", " ")}
                </span>
                {isSummary ? (
                  <textarea
                    className="min-h-32 w-full rounded-[24px] border border-white/10 bg-slate-950/80 px-4 py-3 text-sm leading-6 text-white outline-none transition focus:border-emerald-300/50"
                    onChange={(event) =>
                      setForm((current) => ({ ...current, [key]: event.target.value }))
                    }
                    value={value}
                  />
                ) : (
                  <input
                    className="h-12 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 text-sm text-white outline-none transition focus:border-emerald-300/50"
                    onChange={(event) =>
                      setForm((current) => ({ ...current, [key]: event.target.value }))
                    }
                    value={value}
                  />
                )}
              </label>
            );
          })}
        </div>

        <button
          className="mt-6 inline-flex h-12 items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-5 text-sm font-semibold text-white transition hover:border-emerald-300/40 hover:bg-emerald-300/10 disabled:cursor-not-allowed disabled:text-slate-500"
          disabled={!profile || loadingState !== "idle"}
          onClick={handleProfileSave}
          type="button"
        >
          {loadingState === "saving" ? (
            <LoaderCircle className="h-4 w-4 animate-spin" />
          ) : (
            <CheckCircle2 className="h-4 w-4" />
          )}
          Profili Onayla ve Kaydet
        </button>
      </div>

      <div className="space-y-6">
        <div className="rounded-[32px] border border-white/10 bg-white/[0.04] p-6">
          <div className="flex items-center gap-3">
            <Sparkles className="h-5 w-5 text-emerald-200" />
            <h3 className="text-lg font-semibold text-white">Ayrıştırma Özeti</h3>
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-300">
            {profile?.professional_summary ??
              "Henüz parse edilmiş bir profil yok. CV yüklediğinde profesyonel özet burada görünecek."}
          </p>
          <div className="mt-6 grid grid-cols-3 gap-3">
            {metrics.map((metric) => (
              <div
                className="rounded-2xl border border-white/10 bg-slate-950/70 p-4"
                key={metric.label}
              >
                <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                  {metric.label}
                </p>
                <p className="mt-3 text-2xl font-semibold text-white">{metric.value}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-[32px] border border-white/10 bg-[linear-gradient(180deg,rgba(12,23,45,0.96),rgba(8,13,24,0.92))] p-6">
          <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Hedef Roller</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {(profile?.target_positions ?? []).map((position) => (
              <span
                className="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-2 text-xs text-emerald-100"
                key={position}
              >
                {position}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
