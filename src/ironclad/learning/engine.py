"""Constructive Socratic Pedagogical Engine for Personalized Learning.

Implements the research-backed 6-phase learning cycle:
Diagnose → Personalise → Teach → Assess → Analyse → Adapt

Features:
- Structured pedagogical sequencing (Concept → Explanation → Example → Practice → Assessment)
- RAG grounding using IRONCLAD's hybrid retrieval (no hallucinations)
- Student agency with dynamic modality adaptation (Visual, Simulation, Worked Example, Real-World, Practice)
- Socratic, constructive feedback (reasoning diagnostic instead of transmissive 'wrong')
- Dynamic mastery updates (EWMA) and prerequisite gap propagation
- Automatic struggle classification and teacher alert triggers
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from ironclad.config import IroncladSettings
from ironclad.learning.graph import ConceptGraph
from ironclad.learning.models import (
    AssessmentItem,
    AssessmentResult,
    ConceptNode,
    InterventionExplanation,
    LearnerProfile,
    LearningModality,
    LearningPace,
    LessonPlan,
    PedagogicalStep,
    StruggleType,
    TeacherAlert,
)
from ironclad.learning.storage import LearningStorage

logger = logging.getLogger("ironclad.learning.engine")


class PersonalizedLearningEngine:
    """Orchestrates adaptive lesson synthesis, Socratic tutoring, and student evaluation."""

    def __init__(
        self,
        settings: IroncladSettings,
        storage: LearningStorage,
        graph: ConceptGraph,
    ):
        self.settings = settings
        self.storage = storage
        self.graph = graph

    def create_lesson_plan(
        self,
        student_id: str,
        concept_id: str,
        requested_modality: Optional[LearningModality] = None,
    ) -> LessonPlan:
        """
        Synthesizes an adaptive, grounded lesson plan for a student.

        Respects student agency by adopting requested_modality, or defaults to the learner's
        preferred interaction format.
        """
        student = self.storage.get_or_create_student(student_id, name=student_id)
        concept = self.graph.get_concept(concept_id)
        if not concept:
            raise ValueError(f"Concept '{concept_id}' not found in curriculum '{self.graph.title}'.")

        # Modality selection (Agency)
        modality = requested_modality or student.preferred_modality

        # Prerequisite check & root-cause diagnosis
        diagnosis = self.graph.diagnose_root_cause(concept_id, student.concept_mastery)
        scaffolding_note = ""
        if diagnosis:
            root_node, score, reason = diagnosis
            scaffolding_note = (
                f"Prerequisite Scaffolding Alert: Found lower mastery on '{root_node.name}' "
                f"({score * 100:.0f}%). Building foundational bridge before advancing."
            )

        # Retrieve grounded context from IRONCLAD knowledge base
        grounded_excerpts: List[str] = []
        citations: List[str] = []
        try:
            if self.settings.is_initialized():
                from ironclad.storage.metadata import MetadataStore
                from ironclad.retrieval.lexical import search_lexical
                meta = MetadataStore(self.settings.metadata_db_path)
                lex_results = search_lexical(meta, concept.rag_search_query or concept.name, limit=3)
                for r in lex_results:
                    clean_excerpt = r.content.strip().replace("\n\n", " ")[:200]
                    grounded_excerpts.append(f"{r.file_path}:{r.start_line}-{r.end_line}: {clean_excerpt}...")
                    citations.append(f"{r.file_path}:{r.start_line}-{r.end_line}")
        except Exception as e:
            logger.debug(f"Knowledge base retrieval omitted for lesson plan: {e}")

        # Synthesize instruction based on chosen modality
        explanation, worked_example, guided_exercise = self._generate_modality_content(
            concept=concept,
            modality=modality,
            scaffolding_note=scaffolding_note,
            grounded_excerpts=grounded_excerpts,
        )

        # Build assessment questions
        items = self._generate_assessment_items(concept)

        pedagogical_sequence = [
            PedagogicalStep.CONCEPT,
            PedagogicalStep.EXPLANATION,
            PedagogicalStep.EXAMPLE,
            PedagogicalStep.GUIDED_PRACTICE,
            PedagogicalStep.INDEPENDENT_PRACTICE,
            PedagogicalStep.CONSOLIDATION,
            PedagogicalStep.ASSESSMENT,
        ]
        if diagnosis:
            pedagogical_sequence.append(PedagogicalStep.REMEDIATION)

        return LessonPlan(
            concept_id=concept.id,
            concept_name=concept.name,
            student_id=student_id,
            modality=modality,
            pedagogical_sequence=pedagogical_sequence,
            grounded_context_excerpts=grounded_excerpts,
            explanation=explanation,
            worked_example=worked_example,
            guided_exercise=guided_exercise,
            assessment_items=items,
            socratic_scaffolding=scaffolding_note,
            citations=citations,
        )

    def evaluate_submission(
        self,
        student_id: str,
        concept_id: str,
        item_id: str,
        student_answer: str,
        latency_sec: float = 8.0,
    ) -> AssessmentResult:
        """
        Evaluates student answer with constructive Socratic guidance rather than transmissive rejection.
        Dynamically adjusts learner mastery score and flags struggle patterns.
        """
        student = self.storage.get_or_create_student(student_id, name=student_id)
        concept = self.graph.get_concept(concept_id)
        if not concept:
            raise ValueError(f"Concept '{concept_id}' not found.")

        # Find matching assessment item
        items = self._generate_assessment_items(concept)
        target_item = next((it for it in items if it.id == item_id), items[0] if items else None)

        if not target_item:
            # Fallback evaluation
            is_correct = True
            correct_val = "True"
            hint = "Focus on base definitions."
            prereq_id = None
        else:
            correct_val = target_item.correct_answer.strip().lower()
            clean_student = student_answer.strip().lower()
            is_correct = (clean_student == correct_val) or (clean_student in correct_val) or (correct_val in clean_student)
            hint = target_item.hint
            prereq_id = target_item.prerequisite_id

        # Generate constructive Socratic response
        if is_correct:
            feedback = (
                f"Excellent reasoning! You accurately applied the principles of {concept.name}. "
                f"Your derivation matches the expected target ({correct_val})."
            )
            prereq_gap = None
        else:
            # Constructive rather than directive guidance (from Research Section 7)
            feedback = (
                f"Your response '{student_answer}' is not quite right. "
                f"Let's trace where your reasoning changed direction. "
                f"Hint: {hint}. Would you like a worked example or another attempt?"
            )
            prereq_gap = prereq_id

        result = AssessmentResult(
            item_id=item_id,
            concept_id=concept_id,
            student_answer=student_answer,
            is_correct=is_correct,
            socratic_feedback=feedback,
            prerequisite_gap_detected=prereq_gap,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # Update mastery via Exponential Weighted Moving Average (EWMA)
        current_mastery = student.concept_mastery.get(concept_id, 0.4)
        if is_correct:
            new_mastery = min(1.0, current_mastery * 0.7 + 1.0 * 0.3)
        else:
            new_mastery = max(0.0, current_mastery * 0.7 + 0.0 * 0.3)

        student.concept_mastery[concept_id] = round(new_mastery, 3)

        # If a prerequisite gap was detected on this question, adjust prerequisite mastery too
        if prereq_gap and prereq_gap in student.concept_mastery:
            p_score = student.concept_mastery[prereq_gap]
            student.concept_mastery[prereq_gap] = round(max(0.0, p_score * 0.8 + 0.0 * 0.2), 3)

        # Update streak and assessment statistics
        student.total_assessments += 1
        if is_correct:
            student.correct_assessments += 1
            student.streak_correct += 1
            student.streak_incorrect = 0
            if student.streak_correct >= 3 and student.learning_pace != LearningPace.FAST:
                student.learning_pace = LearningPace.FAST
        else:
            student.streak_incorrect += 1
            student.streak_correct = 0
            if student.streak_incorrect >= 2 and student.learning_pace != LearningPace.NEEDS_SCAFFOLDING:
                student.learning_pace = LearningPace.NEEDS_SCAFFOLDING

        # Check struggle patterns (Research Section 5)
        self._analyze_and_record_struggle(student, concept, is_correct, latency_sec, prereq_gap)

        # Persist student profile & history
        self.storage.save_student(student)
        self.storage.record_assessment(student_id, result)

        return result

    def _analyze_and_record_struggle(
        self,
        student: LearnerProfile,
        concept: ConceptNode,
        is_correct: bool,
        latency_sec: float,
        prereq_gap: Optional[str],
    ) -> None:
        """Classifies student struggle into Knowledge Gap, Engagement, or Human Support."""
        if is_correct:
            student.active_struggle = None
            return

        # Classification heuristics
        if latency_sec < 2.0:
            # Rushing without reading
            student.active_struggle = StruggleType.ENGAGEMENT_ISSUE
        elif prereq_gap or (self.graph.diagnose_root_cause(concept.id, student.concept_mastery) is not None):
            student.active_struggle = StruggleType.KNOWLEDGE_GAP
        elif student.streak_incorrect >= 2:
            student.active_struggle = StruggleType.NEED_HUMAN_SUPPORT
        else:
            student.active_struggle = StruggleType.LEARNING_BEHAVIOR

        # Trigger Teacher Alert if severe
        if student.streak_incorrect >= 2 or student.active_struggle == StruggleType.NEED_HUMAN_SUPPORT:
            alert_id = f"alert-{uuid.uuid4().hex[:8]}"
            diag = self.graph.diagnose_root_cause(concept.id, student.concept_mastery)
            root_cause_name = diag[0].name if diag else None

            explanation = InterventionExplanation(
                student_id=student.student_id,
                student_name=student.name,
                target_concept=concept.name,
                struggle_type=student.active_struggle,
                recommended_action=f"15-minute 1-on-1 review targeting {root_cause_name or concept.name}",
                prerequisite_root_cause=root_cause_name,
                evidence_points=[
                    f"Student has {student.streak_incorrect} consecutive incorrect answers in {concept.name}.",
                    f"Current concept mastery dropped to {student.concept_mastery.get(concept.id, 0.0) * 100:.0f}%.",
                    (
                        f"Root cause: upstream prerequisite '{root_cause_name}' mastery is {diag[1] * 100:.0f}%."
                        if diag
                        else "No prerequisite gap; likely conceptual roadblock or fatigue."
                    ),
                    f"Preferred modality: {student.preferred_modality.value} (respond well to worked walkthroughs).",
                ],
                suggested_teaching_strategy=(
                    f"Provide step-by-step visual worked example bridging {root_cause_name} to {concept.name}."
                    if root_cause_name
                    else "Offer guided problem-solving with reduced scaffolding."
                ),
            )

            alert = TeacherAlert(
                alert_id=alert_id,
                student_id=student.student_id,
                student_name=student.name,
                concept_id=concept.id,
                severity="high" if student.streak_incorrect >= 3 else "medium",
                struggle_type=student.active_struggle,
                message=f"Student {student.name} needs assistance on {concept.name}.",
                explanation=explanation,
            )
            self.storage.save_teacher_alert(alert)

    def _generate_modality_content(
        self,
        concept: ConceptNode,
        modality: LearningModality,
        scaffolding_note: str,
        grounded_excerpts: List[str],
    ) -> tuple[str, str, str]:
        """Generates tailored content adapting to student agency modality."""
        rag_section = ""
        if grounded_excerpts:
            rag_section = "\n\n**Grounded Knowledge Base References:**\n" + "\n".join(
                f"- `{e}`" for e in grounded_excerpts[:2]
            )

        if modality == LearningModality.VISUAL:
            explanation = (
                f"### Visual Blueprint: {concept.name}\n"
                f"{scaffolding_note}\n\n"
                f"Think of **{concept.name}** as an interconnected structural flow:\n\n"
                f"```text\n"
                f"┌─────────────────────────┐\n"
                f"│   Input / Pre-condition │\n"
                f"└────────────┬────────────┘\n"
                f"             │  [Transformation Logic: {concept.name}]\n"
                f"             ▼\n"
                f"┌─────────────────────────┐\n"
                f"│   Output / Evaluation   │\n"
                f"└─────────────────────────┘\n"
                f"```\n"
                f"**Concept Summary**: {concept.description}{rag_section}"
            )
            worked_example = (
                f"### Visual State Walkthrough\n"
                f"**Step 1**: Identify input parameters.\n"
                f"**Step 2**: Observe state transition.\n"
                f"**Step 3**: Verify invariant boundaries."
            )
            guided_exercise = (
                f"Draw or trace the state diagram when applying {concept.name} to a base edge case."
            )

        elif modality == LearningModality.SIMULATION:
            explanation = (
                f"### Interactive Code Simulation: {concept.name}\n"
                f"{scaffolding_note}\n\n"
                f"**Operational Mechanism**: {concept.description}\n"
                f"Execute and observe behavior interactively:{rag_section}"
            )
            worked_example = (
                f"### Runnable Implementation\n"
                f"```python\n"
                f"# Demonstrating {concept.name}\n"
                f"def demonstrate_{concept.id}():\n"
                f"    print('Testing {concept.name} logic...')\n"
                f"    return True\n"
                f"\n"
                f"demonstrate_{concept.id}()\n"
                f"```"
            )
            guided_exercise = (
                f"Modify the simulation code above to handle boundary values and observe output changes."
            )

        elif modality == LearningModality.REAL_WORLD:
            explanation = (
                f"### Real-World Application: {concept.name}\n"
                f"{scaffolding_note}\n\n"
                f"**Real-World Analogy**: {concept.real_world_context or 'Everyday engineering systems.'}\n\n"
                f"**Why this matters**: Rather than abstract rules, **{concept.name}** enables real systems "
                f"to make decisions, scale operations, and verify constraints.{rag_section}"
            )
            worked_example = (
                f"### Real-World Case Study\n"
                f"Consider a sports analytics dashboard computing running player efficiency or an e-commerce "
                f"checkout validating coupon limits. {concept.name} governs how the system transitions from "
                f"raw data to reliable decisions."
            )
            guided_exercise = (
                f"How would you apply {concept.name} to improve reliability in the case study above?"
            )

        elif modality == LearningModality.PRACTICE_QUESTIONS:
            explanation = (
                f"### Challenge & Practice Drill: {concept.name}\n"
                f"{scaffolding_note}\n\n"
                f"**Core Principle**: {concept.description}\n"
                f"**Key Objective**: {concept.learning_objectives[0] if concept.learning_objectives else 'Apply rules accurately.'}{rag_section}"
            )
            worked_example = (
                f"### Rapid Problem Walkthrough\n"
                f"Problem: What is the primary output or rule governing {concept.name}?\n"
                f"Solution: Deconstruct the problem into prerequisites, apply the core transformation, and simplify."
            )
            guided_exercise = (
                f"Solve the practice challenge below without looking at the hints."
            )

        else:  # WORKED_EXAMPLES (Default)
            explanation = (
                f"### Step-by-Step Walkthrough: {concept.name}\n"
                f"{scaffolding_note}\n\n"
                f"**Definition**: {concept.description}\n\n"
                f"**Learning Objectives**:\n"
                + "\n".join(f"- {obj}" for obj in concept.learning_objectives)
                + rag_section
            )
            worked_example = (
                f"### Step-by-Step Worked Example\n"
                f"Let's solve a representative problem in {concept.name}:\n"
                f"1. **Analyze Requirements**: What are the given conditions?\n"
                f"2. **Select Method**: Apply the standard definition.\n"
                f"3. **Compute Result**: Step through line-by-line.\n"
                f"4. **Sanity Check**: Does the outcome align with known constraints?"
            )
            guided_exercise = (
                f"Now it's your turn: apply the same 4-step framework to solve a similar challenge."
            )

        return explanation, worked_example, guided_exercise

    def _generate_assessment_items(self, concept: ConceptNode) -> List[AssessmentItem]:
        """Generates domain-grounded assessment items for a concept and its prerequisites."""
        items: List[AssessmentItem] = []
        cid = concept.id
        prereq = concept.prerequisites[0] if concept.prerequisites else None

        if cid == "c10_real_numbers":
            items.append(
                AssessmentItem(
                    id="q_c10_real_1",
                    concept_id=cid,
                    question="If HCF(306, 657) = 9, what is the value of LCM(306, 657)?",
                    options=["22338", "21338", "24538", "18432"],
                    correct_answer="22338",
                    explanation="Using the theorem: HCF(a, b) * LCM(a, b) = a * b. LCM = (306 * 657) / 9 = 34 * 657 = 22338.",
                    hint="Remember the product relationship: HCF * LCM = Product of the two numbers.",
                    prerequisite_id=None,
                    difficulty=1,
                )
            )
        elif cid == "c10_polynomials":
            items.append(
                AssessmentItem(
                    id="q_c10_poly_1",
                    concept_id=cid,
                    question="If alpha and beta are the zeros of the quadratic polynomial p(x) = x^2 - 7x + 12, what is the value of alpha + beta?",
                    options=["7", "-7", "12", "-12"],
                    correct_answer="7",
                    explanation="For any quadratic polynomial ax^2 + bx + c, sum of zeros (alpha + beta) = -b/a = -(-7)/1 = 7.",
                    hint="Recall the relationship between zeros and coefficients: Sum of zeros = -b/a.",
                    prerequisite_id="c10_real_numbers",
                    difficulty=2,
                )
            )
        elif cid == "c10_quadratic_equations":
            items.append(
                AssessmentItem(
                    id="q_c10_quad_1",
                    concept_id=cid,
                    question="What is the nature of the roots of the quadratic equation 2x^2 - 4x + 3 = 0?",
                    options=["Two distinct real roots", "Two equal real roots", "No real roots (imaginary roots)", "One real and one imaginary"],
                    correct_answer="No real roots (imaginary roots)",
                    explanation="The discriminant D = b^2 - 4ac = (-4)^2 - 4(2)(3) = 16 - 24 = -8. Since D < 0, the equation has no real roots.",
                    hint="Compute the discriminant D = b^2 - 4ac and check its sign.",
                    prerequisite_id="c10_polynomials",
                    difficulty=3,
                )
            )
            items.append(
                AssessmentItem(
                    id="q_c10_quad_2",
                    concept_id=cid,
                    question="Find the roots of x^2 - 5x + 6 = 0 by factorisation.",
                    options=["2 and 3", "-2 and -3", "1 and 6", "-1 and 6"],
                    correct_answer="2 and 3",
                    explanation="Factorise by splitting middle term: x^2 - 2x - 3x + 6 = (x - 2)(x - 3) = 0, giving x = 2 and x = 3.",
                    hint="Find two numbers whose sum is -5 and product is +6.",
                    prerequisite_id="c10_polynomials",
                    difficulty=2,
                )
            )
        elif cid == "c10_linear_equations":
            items.append(
                AssessmentItem(
                    id="q_c10_lin_1",
                    concept_id=cid,
                    question="If the pair of equations 2x + 3y = 7 and 4x + ky = 14 has infinitely many solutions, what is the value of k?",
                    options=["6", "3", "4", "8"],
                    correct_answer="6",
                    explanation="For infinitely many solutions, a1/a2 = b1/b2 = c1/c2. Thus 2/4 = 3/k = 7/14. 1/2 = 3/k => k = 6.",
                    hint="Set the ratios of coefficients equal: a1/a2 = b1/b2 = c1/c2.",
                    prerequisite_id="c10_polynomials",
                    difficulty=2,
                )
            )
        elif cid == "c10_arithmetic_progressions":
            items.append(
                AssessmentItem(
                    id="q_c10_ap_1",
                    concept_id=cid,
                    question="In an Arithmetic Progression where first term a = 5 and common difference d = 3, what is the 10th term (a10)?",
                    options=["32", "35", "30", "29"],
                    correct_answer="32",
                    explanation="The n-th term formula is an = a + (n - 1)d. a10 = 5 + (10 - 1) * 3 = 5 + 27 = 32.",
                    hint="Use the formula: an = a + (n - 1)d with n = 10.",
                    prerequisite_id="c10_linear_equations",
                    difficulty=2,
                )
            )
        elif cid == "c10_triangles":
            items.append(
                AssessmentItem(
                    id="q_c10_tri_1",
                    concept_id=cid,
                    question="In triangle ABC, DE || BC intersecting AB at D and AC at E. If AD = 1.5 cm, DB = 3 cm, and AE = 1 cm, what is EC?",
                    options=["2 cm", "3 cm", "1.5 cm", "2.5 cm"],
                    correct_answer="2 cm",
                    explanation="By Basic Proportionality Theorem (Thales): AD/DB = AE/EC. 1.5/3 = 1/EC => 1/2 = 1/EC => EC = 2 cm.",
                    hint="Apply the Basic Proportionality Theorem: AD/DB = AE/EC.",
                    prerequisite_id="c10_real_numbers",
                    difficulty=2,
                )
            )
        elif cid == "c10_trigonometry":
            items.append(
                AssessmentItem(
                    id="q_c10_trig_1",
                    concept_id=cid,
                    question="What is the evaluated value of (sin 30° + tan 45°) - cosec 60° divided by (sec 30° + cos 60° + cot 45°)?",
                    options=["(43 - 24√3)/11", "(43 + 24√3)/11", "1", "0"],
                    correct_answer="(43 - 24√3)/11",
                    explanation="Substitute standard angle values: sin 30° = 1/2, tan 45° = 1, cosec 60° = 2/√3, sec 30° = 2/√3, cos 60° = 1/2, cot 45° = 1, then rationalize denominator.",
                    hint="Substitute standard values for 30°, 45°, and 60° and simplify the compound fraction.",
                    prerequisite_id="c10_triangles",
                    difficulty=3,
                )
            )
            items.append(
                AssessmentItem(
                    id="q_c10_trig_2",
                    concept_id=cid,
                    question="Simplify the expression: (1 + tan^2 theta) * (1 - sin theta) * (1 + sin theta).",
                    options=["1", "0", "tan^2 theta", "sec^2 theta"],
                    correct_answer="1",
                    explanation="(1 - sin theta)(1 + sin theta) = 1 - sin^2 theta = cos^2 theta. And (1 + tan^2 theta) = sec^2 theta. sec^2 theta * cos^2 theta = 1.",
                    hint="Use the difference of squares and standard identities: 1 - sin^2 = cos^2 and 1 + tan^2 = sec^2.",
                    prerequisite_id="c10_triangles",
                    difficulty=3,
                )
            )
        elif cid == "c10_applications_trig":
            items.append(
                AssessmentItem(
                    id="q_c10_app_trig_1",
                    concept_id=cid,
                    question="A vertical pole of length 6 m casts a shadow 2√3 m long on the ground. What is the sun's elevation angle?",
                    options=["60°", "30°", "45°", "90°"],
                    correct_answer="60°",
                    explanation="Let theta be the angle of elevation. tan(theta) = Height / Shadow = 6 / (2√3) = 3 / √3 = √3. Since tan 60° = √3, theta = 60°.",
                    hint="Set tan(theta) = Height of pole / Length of shadow, then find theta.",
                    prerequisite_id="c10_trigonometry",
                    difficulty=3,
                )
            )
        elif cid == "c10_coordinate_geometry":
            items.append(
                AssessmentItem(
                    id="q_c10_coord_1",
                    concept_id=cid,
                    question="Find the distance between the points P(2, 3) and Q(4, 1).",
                    options=["2√2", "4", "√8", "2"],
                    correct_answer="2√2",
                    explanation="Using distance formula: d = sqrt((4 - 2)^2 + (1 - 3)^2) = sqrt(2^2 + (-2)^2) = sqrt(4 + 4) = sqrt(8) = 2√2.",
                    hint="Apply d = sqrt((x2 - x1)^2 + (y2 - y1)^2).",
                    prerequisite_id="c10_real_numbers",
                    difficulty=2,
                )
            )
        elif cid == "c10_statistics":
            items.append(
                AssessmentItem(
                    id="q_c10_stat_1",
                    concept_id=cid,
                    question="If the Mode of a frequency distribution is 24 and the Mean is 24, what is the Median?",
                    options=["24", "12", "48", "36"],
                    correct_answer="24",
                    explanation="Using empirical formula: 3 Median = Mode + 2 Mean => 3 Median = 24 + 2(24) = 72 => Median = 72 / 3 = 24.",
                    hint="Use the empirical relationship: 3 Median = Mode + 2 Mean.",
                    prerequisite_id="c10_real_numbers",
                    difficulty=2,
                )
            )
        elif cid == "c10_probability":
            items.append(
                AssessmentItem(
                    id="q_c10_prob_1",
                    concept_id=cid,
                    question="A single balanced die is rolled once. What is the probability of obtaining a prime number?",
                    options=["1/2", "1/3", "1/6", "2/3"],
                    correct_answer="1/2",
                    explanation="Total outcomes S = {1, 2, 3, 4, 5, 6} (6 total). Prime numbers are {2, 3, 5} (3 primes). Probability = 3/6 = 1/2.",
                    hint="Prime numbers between 1 and 6 are 2, 3, and 5 (1 is neither prime nor composite).",
                    prerequisite_id="c10_real_numbers",
                    difficulty=2,
                )
            )
        elif cid == "py_variables":
            items.append(
                AssessmentItem(
                    id="q_py_var_1",
                    concept_id=cid,
                    question="In Python, if x = '10' and y = 5, what does type(x) evaluate to?",
                    options=["str", "int", "float", "list"],
                    correct_answer="str",
                    explanation="'10' is enclosed in quotes, making it a string type.",
                    hint="Look at the quotation marks around the digits.",
                    prerequisite_id=None,
                    difficulty=1,
                )
            )
            items.append(
                AssessmentItem(
                    id="q_py_var_2",
                    concept_id=cid,
                    question="What is the result of 7 // 2 in Python?",
                    options=["3.5", "3", "4", "1"],
                    correct_answer="3",
                    explanation="// performs floor division, rounding down to the nearest integer.",
                    hint="Floor division discards the fractional remainder.",
                    prerequisite_id=None,
                    difficulty=1,
                )
            )
        elif cid == "py_conditionals":
            items.append(
                AssessmentItem(
                    id="q_py_cond_1",
                    concept_id=cid,
                    question="What does (True or False) and not (False) evaluate to?",
                    options=["True", "False"],
                    correct_answer="True",
                    explanation="(True or False) is True, and not (False) is True. True and True is True.",
                    hint="Evaluate expressions inside parentheses first.",
                    prerequisite_id="py_variables",
                    difficulty=2,
                )
            )
        elif cid == "py_loops":
            items.append(
                AssessmentItem(
                    id="q_py_loop_1",
                    concept_id=cid,
                    question="How many times will 'for i in range(2, 6):' execute?",
                    options=["3", "4", "5", "6"],
                    correct_answer="4",
                    explanation="range(2, 6) generates numbers 2, 3, 4, 5 (4 iterations total).",
                    hint="range(start, stop) excludes the stop value.",
                    prerequisite_id="py_conditionals",
                    difficulty=2,
                )
            )
        elif cid == "py_functions":
            items.append(
                AssessmentItem(
                    id="q_py_func_1",
                    concept_id=cid,
                    question="What does a Python function return by default if no return statement is executed?",
                    options=["None", "0", "False", "Empty string"],
                    correct_answer="None",
                    explanation="Python functions implicitly return None when no explicit return statement is hit.",
                    hint="Think of the built-in null singleton object in Python.",
                    prerequisite_id="py_variables",
                    difficulty=2,
                )
            )
        elif cid == "calc_limits":
            items.append(
                AssessmentItem(
                    id="q_calc_lim_1",
                    concept_id=cid,
                    question="What is the limit of (x^2 - 4)/(x - 2) as x approaches 2?",
                    options=["0", "2", "4", "Undefined"],
                    correct_answer="4",
                    explanation="Factor the numerator: (x-2)(x+2)/(x-2) = x+2. As x -> 2, 2+2 = 4.",
                    hint="Direct substitution yields 0/0. Try factoring the numerator.",
                    prerequisite_id="calc_functions",
                    difficulty=2,
                )
            )
        elif cid == "calc_derivatives":
            items.append(
                AssessmentItem(
                    id="q_calc_der_1",
                    concept_id=cid,
                    question="Using the Power Rule, what is the derivative of f(x) = 3x^4?",
                    options=["12x^3", "7x^3", "12x^4", "4x^3"],
                    correct_answer="12x^3",
                    explanation="d/dx [c * x^n] = c * n * x^(n-1). 3 * 4 * x^3 = 12x^3.",
                    hint="Multiply coefficient by the exponent and subtract 1 from the power.",
                    prerequisite_id="calc_limits",
                    difficulty=3,
                )
            )
        elif cid == "calc_integrals":
            items.append(
                AssessmentItem(
                    id="q_calc_int_1",
                    concept_id=cid,
                    question="What is the definite integral ∫ from 0 to 2 of 2x dx?",
                    options=["2", "4", "6", "8"],
                    correct_answer="4",
                    explanation="The antiderivative is x^2. Evaluating [x^2] from 0 to 2 gives 2^2 - 0^2 = 4.",
                    hint="Find the antiderivative of 2x first, then evaluate at bounds 2 and 0.",
                    prerequisite_id="calc_derivatives",
                    difficulty=3,
                )
            )
        else:
            # Generic diagnostic item
            items.append(
                AssessmentItem(
                    id=f"q_{cid}_1",
                    concept_id=cid,
                    question=f"Which core property distinguishes {concept.name}?",
                    options=["A", "B", "C"],
                    correct_answer="A",
                    explanation=f"{concept.name} enforces fundamental rules in {concept.domain}.",
                    hint="Review the primary learning objective.",
                    prerequisite_id=prereq,
                    difficulty=concept.difficulty,
                )
            )

        return items
