"use client";

import { CheckCircle2, CircleDashed } from "lucide-react";

import type { ProcessStepState } from "@/app/lib/workflow";

interface WorkflowChecklistProps {
  step: ProcessStepState;
}

export function WorkflowChecklist({ step }: WorkflowChecklistProps) {
  const completedCount = step.criteria.filter((criterion) => criterion.satisfied).length;

  return (
    <section className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.26em] text-slate-500">Süreç Checklist</p>
          <h2 className="mt-2 text-xl font-semibold text-white">{step.label}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-300">{step.description}</p>
        </div>
        <div className="rounded-full border border-white/10 bg-slate-950/70 px-4 py-2 text-xs text-slate-200">
          {completedCount}/{step.criteria.length} tamamlandı
        </div>
      </div>

      <div className="mt-5 h-2.5 rounded-full bg-white/5">
        <div
          className={`h-2.5 rounded-full ${
            step.status === "completed" ? "bg-emerald-300" : "bg-amber-300"
          }`}
          style={{
            width: `${Math.max(12, Math.round((completedCount / step.criteria.length) * 100))}%`,
          }}
        />
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2">
        {step.criteria.map((criterion) => (
          <div
            className={`rounded-[20px] border px-4 py-3 ${
              criterion.satisfied
                ? "border-emerald-300/20 bg-emerald-300/10"
                : "border-white/10 bg-slate-950/70"
            }`}
            key={criterion.label}
          >
            <div className="flex items-center gap-3">
              {criterion.satisfied ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-200" />
              ) : (
                <CircleDashed className="h-4 w-4 text-amber-200" />
              )}
              <p className={criterion.satisfied ? "text-sm text-emerald-100" : "text-sm text-white"}>
                {criterion.label}
              </p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
