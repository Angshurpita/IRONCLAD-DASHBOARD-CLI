"""Unit tests for IRONCLAD Personalized Learning Engine."""

import pytest
from pathlib import Path
import tempfile

from ironclad.config import IroncladSettings
from ironclad.learning.engine import PersonalizedLearningEngine
from ironclad.learning.graph import (
    ConceptGraph,
    get_calculus_curriculum,
    get_python_curriculum,
)
from ironclad.learning.models import (
    AssessmentItem,
    ConceptNode,
    Curriculum,
    LearningModality,
    LearningPace,
    StruggleType,
)
from ironclad.learning.storage import LearningStorage
from ironclad.learning.teacher import TeacherDashboardService


def make_python_graph() -> ConceptGraph:
    return ConceptGraph(get_python_curriculum())


def make_calculus_graph() -> ConceptGraph:
    return ConceptGraph(get_calculus_curriculum())


def make_storage(db_path: Path) -> LearningStorage:
    return LearningStorage(db_path)


def make_engine(graph: ConceptGraph, storage: LearningStorage, root: Path) -> PersonalizedLearningEngine:
    settings = IroncladSettings(project_root=root)
    return PersonalizedLearningEngine(settings, storage, graph)


@pytest.fixture
def python_graph() -> ConceptGraph:
    return make_python_graph()


@pytest.fixture
def calculus_graph() -> ConceptGraph:
    return make_calculus_graph()


@pytest.fixture
def storage(tmp_path: Path) -> LearningStorage:
    return make_storage(tmp_path / "test_learning.db")


@pytest.fixture
def engine(python_graph: ConceptGraph, storage: LearningStorage, tmp_path: Path) -> PersonalizedLearningEngine:
    return make_engine(python_graph, storage, tmp_path)


class TestConceptGraph:
    def test_topological_ordering_python(self, python_graph: ConceptGraph):
        ordered = python_graph.topological_order()
        ids = [c.id for c in ordered]
        # Variables must precede conditionals, which precedes loops
        assert ids.index("py_variables") < ids.index("py_conditionals")
        assert ids.index("py_conditionals") < ids.index("py_loops")

    def test_topological_ordering_calculus(self, calculus_graph: ConceptGraph):
        ordered = calculus_graph.topological_order()
        ids = [c.id for c in ordered]
        assert ids.index("calc_functions") < ids.index("calc_limits")
        assert ids.index("calc_limits") < ids.index("calc_derivatives")
        assert ids.index("calc_derivatives") < ids.index("calc_integrals")

    def test_cycle_detection(self):
        curr = Curriculum(
            domain="test",
            title="Cyclic Test",
            description="Testing cycle validation",
            concepts={
                "A": ConceptNode(id="A", name="A", domain="test", description="A", prerequisites=["B"]),
                "B": ConceptNode(id="B", name="B", domain="test", description="B", prerequisites=["A"]),
            },
        )
        with pytest.raises(ValueError, match="Cycle detected"):
            ConceptGraph(curr)

    def test_root_cause_diagnosis_identifies_upstream_prerequisite(self, python_graph: ConceptGraph):
        # Student struggles with py_loops (score 0.3)
        # Because py_conditionals (score 0.25) is deficient
        mastery = {
            "py_variables": 0.90,
            "py_conditionals": 0.25,  # Root cause!
            "py_loops": 0.30,
        }
        diagnosis = python_graph.diagnose_root_cause("py_loops", mastery, mastery_threshold=0.65)
        assert diagnosis is not None
        root_node, score, explanation = diagnosis
        assert root_node.id == "py_conditionals"
        assert score == 0.25
        assert "prerequisite" in explanation.lower()

    def test_root_cause_diagnosis_none_when_prerequisites_met(self, python_graph: ConceptGraph):
        mastery = {
            "py_variables": 0.95,
            "py_conditionals": 0.85,
            "py_loops": 0.40,
        }
        # Upstream prerequisites are sound (>0.65)
        diagnosis = python_graph.diagnose_root_cause("py_loops", mastery, mastery_threshold=0.65)
        assert diagnosis is None


class TestLearningStorage:
    def test_create_and_load_student(self, storage: LearningStorage):
        student = storage.get_or_create_student("s_test", "Test Learner", "python_programming")
        assert student.student_id == "s_test"
        assert student.name == "Test Learner"
        assert student.learning_pace == LearningPace.MODERATE

        # Update mastery
        student.concept_mastery["py_variables"] = 0.85
        storage.save_student(student)

        reloaded = storage.get_student("s_test")
        assert reloaded is not None
        assert reloaded.concept_mastery.get("py_variables") == 0.85

    def test_record_assessment_updates_streaks_and_pace(self, storage: LearningStorage, engine: PersonalizedLearningEngine):
        student = storage.get_or_create_student("s_streak", "Streak Student")

        # Answer 3 correctly in a row
        for i in range(3):
            engine.evaluate_submission("s_streak", "py_variables", "q_py_var_1", "str")

        updated = storage.get_student("s_streak")
        assert updated.streak_correct == 3
        assert updated.learning_pace == LearningPace.FAST


class TestPedagogicalEngine:
    def test_create_lesson_plan_respects_agency_modality(self, engine: PersonalizedLearningEngine):
        plan_visual = engine.create_lesson_plan("s_alex", "py_variables", requested_modality=LearningModality.VISUAL)
        assert plan_visual.modality == LearningModality.VISUAL
        assert "Visual Blueprint" in plan_visual.explanation

        plan_sim = engine.create_lesson_plan("s_alex", "py_variables", requested_modality=LearningModality.SIMULATION)
        assert plan_sim.modality == LearningModality.SIMULATION
        assert "Interactive Code Simulation" in plan_sim.explanation

    def test_constructive_socratic_feedback_on_incorrect(self, engine: PersonalizedLearningEngine):
        res = engine.evaluate_submission("s_alex", "py_variables", "q_py_var_1", "int")
        assert res.is_correct is False
        # Socratic, constructive prompt (not transmissive 'Wrong. The answer is str.')
        assert "let's trace where your reasoning changed direction" in res.socratic_feedback.lower()
        assert "hint" in res.socratic_feedback.lower()

    def test_constructive_feedback_on_correct(self, engine: PersonalizedLearningEngine):
        res = engine.evaluate_submission("s_alex", "py_variables", "q_py_var_1", "str")
        assert res.is_correct is True
        assert "excellent reasoning" in res.socratic_feedback.lower()


class TestTeacherDashboard:
    def test_class_summary_and_explainability(
        self, storage: LearningStorage, python_graph: ConceptGraph, engine: PersonalizedLearningEngine
    ):
        s1 = storage.get_or_create_student("s_sarah", "Sarah Chen", domain=python_graph.domain)
        s1.concept_mastery = {"py_variables": 0.90, "py_conditionals": 0.35, "py_loops": 0.30}
        s1.streak_incorrect = 3
        s1.active_struggle = StruggleType.KNOWLEDGE_GAP
        storage.save_student(s1)

        service = TeacherDashboardService(storage, python_graph)
        summary = service.get_class_summary()

        assert summary.total_students >= 1
        assert summary.students_requiring_intervention >= 1

        # Test Explainability: Why was this intervention recommended?
        expl = service.explain_intervention("s_sarah", "py_loops")
        assert expl.student_id == "s_sarah"
        assert expl.struggle_type == StruggleType.KNOWLEDGE_GAP
        assert expl.prerequisite_root_cause == "Conditional Branching & Boolean Logic"
        assert len(expl.evidence_points) >= 3
        assert any("Conditional Branching" in pt for pt in expl.evidence_points)


class TestClass10MathematicsCurriculum:
    def test_class10_curriculum_structure(self):
        from ironclad.learning.graph import get_class10_maths_curriculum
        curr = get_class10_maths_curriculum()
        graph = ConceptGraph(curr)
        
        # Must have all 13 core NCERT/CBSE units
        assert len(graph.concepts) >= 13
        assert "c10_real_numbers" in graph.concepts
        assert "c10_polynomials" in graph.concepts
        assert "c10_quadratic_equations" in graph.concepts
        assert "c10_triangles" in graph.concepts
        assert "c10_trigonometry" in graph.concepts
        assert "c10_applications_trig" in graph.concepts
        assert "c10_statistics" in graph.concepts
        assert "c10_probability" in graph.concepts

        # Prerequisite verification
        quad = graph.get_concept("c10_quadratic_equations")
        assert "c10_polynomials" in quad.prerequisites

        poly = graph.get_concept("c10_polynomials")
        assert "c10_real_numbers" in poly.prerequisites

        trig_app = graph.get_concept("c10_applications_trig")
        assert "c10_trigonometry" in trig_app.prerequisites

    def test_priya_sharma_case_study_prerequisite_diagnosis(self):
        """Simulates Section 14 (page 6) case study: Priya Sharma failing Quadratics due to Polynomials."""
        from ironclad.learning.graph import get_class10_maths_curriculum
        curr = get_class10_maths_curriculum()
        graph = ConceptGraph(curr)

        # Priya has sound Real Numbers (88%), but weak Polynomials (42%)
        priya_mastery = {
            "c10_real_numbers": 0.88,
            "c10_polynomials": 0.42,
            "c10_quadratic_equations": 0.35,
        }

        # Diagnose why Priya is failing Quadratic Equations
        diag = graph.diagnose_root_cause("c10_quadratic_equations", priya_mastery)
        assert diag is not None
        root_node, score, reason = diag
        assert root_node.id == "c10_polynomials"
        assert score == 0.42
        assert "Polynomials" in root_node.name


class TestAuthenticationAndRoles:
    def test_user_creation_and_authentication(self, storage: LearningStorage):
        # Create Teacher
        t = storage.create_user(
            username="sunita@school.edu",
            password_clear="securepass123",
            role="teacher",
            name="Dr. Sunita Sharma",
        )
        assert t["role"] == "teacher"
        assert t["name"] == "Dr. Sunita Sharma"

        # Valid auth
        auth_ok = storage.authenticate_user("sunita@school.edu", "securepass123")
        assert auth_ok is not None
        assert auth_ok["username"] == "sunita@school.edu"
        assert auth_ok["role"] == "teacher"

        # Invalid password
        auth_bad = storage.authenticate_user("sunita@school.edu", "wrongpassword")
        assert auth_bad is None

        # Session lifecycle
        token = storage.create_session("sunita@school.edu", "teacher")
        assert token.startswith("sess_")

        user_by_token = storage.get_user_by_token(token)
        assert user_by_token is not None
        assert user_by_token["username"] == "sunita@school.edu"

        storage.delete_session(token)
        assert storage.get_user_by_token(token) is None
