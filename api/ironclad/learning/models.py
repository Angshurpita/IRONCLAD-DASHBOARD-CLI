"""Data models for the IRONCLAD AI Personalized Learning Engine.

Based on the research paper 'AI for Personalised Learning':
- Dynamic Student Learning Profile (mastery, weaknesses, pace, modalities, behavior flags)
- Knowledge & Concept Mastery Graph (prerequisites, difficulty, domains)
- Structured Pedagogical Sequences & Socratic Interactions
- Teacher Alerts & Explainable Interventions
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LearningModality(str, Enum):
    """Student agency interaction formats."""
    VISUAL = "visual"
    WORKED_EXAMPLES = "worked_examples"
    SIMULATION = "simulation"
    PRACTICE_QUESTIONS = "practice_questions"
    REAL_WORLD = "real_world"


class LearningPace(str, Enum):
    """Pace classification based on learner performance and latency."""
    FAST = "fast"
    MODERATE = "moderate"
    DELIBERATE = "deliberate"
    NEEDS_SCAFFOLDING = "needs_scaffolding"


class StruggleType(str, Enum):
    """Categorization of why a student struggles, as highlighted in research."""
    KNOWLEDGE_GAP = "knowledge_gap"  # Missing prerequisite
    ENGAGEMENT_ISSUE = "engagement_issue"  # Low response rate, rushing, low time-on-task
    LEARNING_BEHAVIOR = "learning_behavior"  # Repeated guess patterns
    NEED_HUMAN_SUPPORT = "need_human_support"  # Persistent plateau requiring teacher attention


class ConceptNode(BaseModel):
    """A node in the Concept Mastery Graph representing a knowledge unit."""
    id: str
    name: str
    domain: str  # e.g. "python_programming", "calculus"
    description: str
    prerequisites: List[str] = Field(default_factory=list)
    difficulty: int = 1  # Scale 1-5
    learning_objectives: List[str] = Field(default_factory=list)
    rag_search_query: str = ""  # Term used to retrieve grounded source passages from .ironclad
    real_world_context: Optional[str] = None


class Curriculum(BaseModel):
    """Collection of concepts forming a subject domain graph."""
    domain: str
    title: str
    description: str
    concepts: Dict[str, ConceptNode] = Field(default_factory=dict)


class AssessmentItem(BaseModel):
    """An individual question or challenge in a learning sequence."""
    id: str
    concept_id: str
    question: str
    options: Optional[List[str]] = None  # None for free-form / open-ended
    correct_answer: str
    explanation: str
    hint: str
    prerequisite_id: Optional[str] = None  # Targeted prerequisite tested by this item
    difficulty: int = 1


class AssessmentResult(BaseModel):
    """Outcome of a student's answer to an assessment item."""
    item_id: str
    concept_id: str
    student_answer: str
    is_correct: bool
    socratic_feedback: str
    prerequisite_gap_detected: Optional[str] = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class LearnerProfile(BaseModel):
    """
    Dynamic Student Learning Profile.
    Continuously evolves based on student interaction and assessment evidence.
    """
    student_id: str
    name: str
    domain: str = "python_programming"
    concept_mastery: Dict[str, float] = Field(default_factory=dict)  # concept_id -> score (0.0 to 1.0)
    conceptual_weaknesses: List[str] = Field(default_factory=list)  # concept_ids with root gaps
    learning_pace: LearningPace = LearningPace.MODERATE
    preferred_modality: LearningModality = LearningModality.WORKED_EXAMPLES
    modality_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            LearningModality.VISUAL.value: 1.0,
            LearningModality.WORKED_EXAMPLES.value: 1.2,
            LearningModality.SIMULATION.value: 1.0,
            LearningModality.PRACTICE_QUESTIONS.value: 1.0,
            LearningModality.REAL_WORLD.value: 1.1,
        }
    )
    total_sessions: int = 0
    total_assessments: int = 0
    correct_assessments: int = 0
    average_latency_sec: float = 0.0
    active_struggle: Optional[StruggleType] = None
    streak_correct: int = 0
    streak_incorrect: int = 0
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class PedagogicalStep(str, Enum):
    """Structured instructional sequence defined in research."""
    CONCEPT = "concept"
    EXPLANATION = "explanation"
    EXAMPLE = "example"
    GUIDED_PRACTICE = "guided_practice"
    INDEPENDENT_PRACTICE = "independent_practice"
    CONSOLIDATION = "consolidation"
    ASSESSMENT = "assessment"
    REMEDIATION = "remediation"


class LessonPlan(BaseModel):
    """A personalized lesson sequence synthesized for a specific learner."""
    concept_id: str
    concept_name: str
    student_id: str
    modality: LearningModality
    pedagogical_sequence: List[PedagogicalStep]
    grounded_context_excerpts: List[str] = Field(default_factory=list)
    explanation: str
    worked_example: str
    guided_exercise: str
    assessment_items: List[AssessmentItem] = Field(default_factory=list)
    socratic_scaffolding: str = ""
    citations: List[str] = Field(default_factory=list)


class InterventionExplanation(BaseModel):
    """Explainability record justifying why an intervention was recommended."""
    student_id: str
    student_name: str
    target_concept: str
    struggle_type: StruggleType
    recommended_action: str
    prerequisite_root_cause: Optional[str] = None
    evidence_points: List[str] = Field(default_factory=list)
    suggested_teaching_strategy: str


class TeacherAlert(BaseModel):
    """Classroom alert for teachers requiring human-in-the-loop oversight."""
    alert_id: str
    student_id: str
    student_name: str
    concept_id: str
    severity: str  # "high", "medium", "info"
    struggle_type: StruggleType
    message: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    explanation: Optional[InterventionExplanation] = None
