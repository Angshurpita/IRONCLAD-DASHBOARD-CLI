"""Teacher Intelligence & Explainable Intervention Dashboard.

Based on the research paper 'AI for Personalised Learning' (Section 14):
- Class-level analytics (average mastery, weak concepts, student counts)
- Proactive identification of students requiring intervention
- Explainability: 'Why was this intervention recommended?'
- Distinction between knowledge gaps, engagement issues, and need for human support
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from ironclad.learning.graph import ConceptGraph
from ironclad.learning.models import (
    InterventionExplanation,
    LearnerProfile,
    StruggleType,
    TeacherAlert,
)
from ironclad.learning.storage import LearningStorage


class ClassAnalyticsSummary(BaseModel):
    """Classroom-level performance and health metrics."""
    domain: str
    total_students: int
    average_mastery_pct: float
    students_requiring_intervention: int
    main_weak_concept_id: Optional[str] = None
    main_weak_concept_name: Optional[str] = None
    concept_mastery_breakdown: Dict[str, float] = Field(default_factory=dict)
    active_alerts: List[TeacherAlert] = Field(default_factory=list)
    top_recommended_intervention: str = ""


class TeacherDashboardService:
    """Provides teacher oversight, alert monitoring, and explainability reasoning."""

    def __init__(self, storage: LearningStorage, graph: ConceptGraph):
        self.storage = storage
        self.graph = graph

    def get_class_summary(self, domain: Optional[str] = None) -> ClassAnalyticsSummary:
        """Aggregates classroom-level metrics across registered students."""
        target_domain = domain or self.graph.domain
        students = self.storage.list_students(domain=target_domain)

        if not students:
            return ClassAnalyticsSummary(
                domain=target_domain,
                total_students=0,
                average_mastery_pct=0.0,
                students_requiring_intervention=0,
                main_weak_concept_id=None,
                main_weak_concept_name="N/A",
                top_recommended_intervention="No enrolled students yet.",
            )

        # Calculate average mastery
        all_masteries = []
        concept_scores: Dict[str, List[float]] = {cid: [] for cid in self.graph.concepts}

        intervention_count = 0
        for s in students:
            if s.active_struggle or s.streak_incorrect >= 2:
                intervention_count += 1

            for cid, score in s.concept_mastery.items():
                all_masteries.append(score)
                if cid in concept_scores:
                    concept_scores[cid].append(score)

        avg_mastery = (sum(all_masteries) / len(all_masteries)) * 100 if all_masteries else 0.0

        # Identify main weak concept
        concept_averages = {}
        for cid, scores in concept_scores.items():
            if scores:
                concept_averages[cid] = sum(scores) / len(scores)
            else:
                concept_averages[cid] = 0.0

        sorted_concepts = sorted(concept_averages.items(), key=lambda x: x[1])
        main_weak_id = sorted_concepts[0][0] if sorted_concepts else None
        main_weak_name = self.graph.concepts[main_weak_id].name if main_weak_id in self.graph.concepts else "None"

        # Active alerts
        alerts = self.storage.list_teacher_alerts(unresolved_only=True)
        domain_alerts = [a for a in alerts if a.concept_id in self.graph.concepts]

        # Formulate top recommended intervention
        if intervention_count > 0:
            top_rec = f"Schedule a 15-minute targeted remediation module on '{main_weak_name}' for struggling students."
        else:
            top_rec = "Class pacing is optimal. Encourage advanced independent practice."

        breakdown = {cid: round(avg * 100, 1) for cid, avg in concept_averages.items()}

        return ClassAnalyticsSummary(
            domain=target_domain,
            total_students=len(students),
            average_mastery_pct=round(avg_mastery, 1),
            students_requiring_intervention=intervention_count,
            main_weak_concept_id=main_weak_id,
            main_weak_concept_name=main_weak_name,
            concept_mastery_breakdown=breakdown,
            active_alerts=domain_alerts,
            top_recommended_intervention=top_rec,
        )

    def explain_intervention(
        self, student_id: str, concept_id: Optional[str] = None
    ) -> InterventionExplanation:
        """
        Synthesizes an evidence-backed rationale answering:
        'Why was this intervention recommended?'
        """
        student = self.storage.get_student(student_id)
        if not student:
            raise ValueError(f"Student '{student_id}' not found.")

        # If concept not provided, pick the student's lowest mastery concept
        if not concept_id:
            if student.concept_mastery:
                sorted_m = sorted(student.concept_mastery.items(), key=lambda x: x[1])
                target_cid = sorted_m[0][0]
            else:
                target_cid = list(self.graph.concepts.keys())[0]
        else:
            target_cid = concept_id

        target_node = self.graph.get_concept(target_cid)
        concept_name = target_node.name if target_node else target_cid

        # Check prerequisite diagnosis
        diag = self.graph.diagnose_root_cause(target_cid, student.concept_mastery)
        root_prereq_name = diag[0].name if diag else None

        # Build evidence points (Research Section 14)
        evidence = [
            f"Concept '{concept_name}' mastery currently at {student.concept_mastery.get(target_cid, 0.0) * 100:.1f}%.",
            f"Consecutive incorrect answer streak: {student.streak_incorrect}.",
            f"Total assessment questions attempted: {student.total_assessments} ({student.correct_assessments} correct).",
        ]

        if diag:
            evidence.append(
                f"Prerequisite analysis identified that '{root_prereq_name}' has low mastery ({diag[1] * 100:.0f}%), "
                f"which is the upstream root cause of comprehension errors in '{concept_name}'."
            )
        else:
            evidence.append(
                "Upstream prerequisites are nominally satisfied; difficulty indicates a cognitive leap in the current topic."
            )

        evidence.append(
            f"Learner response format preference is '{student.preferred_modality.value}'."
        )

        struggle = student.active_struggle or (
            StruggleType.KNOWLEDGE_GAP if diag else StruggleType.NEED_HUMAN_SUPPORT
        )

        return InterventionExplanation(
            student_id=student.student_id,
            student_name=student.name,
            target_concept=concept_name,
            struggle_type=struggle,
            recommended_action=(
                f"15-minute 1-on-1 review targeting {root_prereq_name or concept_name} with worked examples."
            ),
            prerequisite_root_cause=root_prereq_name,
            evidence_points=evidence,
            suggested_teaching_strategy=(
                f"Begin with a 5-minute refresher on '{root_prereq_name}', followed by a worked step-by-step example "
                f"connecting it directly to '{concept_name}'."
                if root_prereq_name
                else "Provide guided scaffolding and reduce cognitive load through worked examples."
            ),
        )
