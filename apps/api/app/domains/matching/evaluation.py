from __future__ import annotations

from .schemas import EvaluationRecord, EvaluationSummary


def evaluate_predictions(records: list[EvaluationRecord]) -> EvaluationSummary:
    tp = sum(
        1 for record in records if record.predicted_positive and record.actual_positive
    )
    fp = sum(
        1
        for record in records
        if record.predicted_positive and not record.actual_positive
    )
    fn = sum(
        1
        for record in records
        if not record.predicted_positive and record.actual_positive
    )
    tn = sum(
        1
        for record in records
        if not record.predicted_positive and not record.actual_positive
    )

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1_score = (
        (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    )
    false_positive_rate = fp / (fp + tn) if (fp + tn) else 0.0
    false_negative_rate = fn / (fn + tp) if (fn + tp) else 0.0

    return EvaluationSummary(
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1_score=round(f1_score, 4),
        false_positive_rate=round(false_positive_rate, 4),
        false_negative_rate=round(false_negative_rate, 4),
    )
