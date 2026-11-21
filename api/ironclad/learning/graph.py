"""Knowledge & Concept Mastery Graph representing curriculum dependencies.

Implements:
- Directed Acyclic Graph (DAG) for prerequisite relationships
- Topological ordering of learning paths
- Upstream root-cause prerequisite diagnoser
- Pre-seeded multi-subject curricula (Python Programming & Calculus)
"""

from typing import Dict, List, Optional, Set, Tuple
from ironclad.learning.models import ConceptNode, Curriculum


class ConceptGraph:
    """Manages concepts, prerequisites, and diagnosis in a curriculum DAG."""

    def __init__(self, curriculum: Curriculum):
        self.curriculum = curriculum
        self._validate_dag()

    @property
    def domain(self) -> str:
        return self.curriculum.domain

    @property
    def title(self) -> str:
        return self.curriculum.title

    @property
    def concepts(self) -> Dict[str, ConceptNode]:
        return self.curriculum.concepts

    def get_concept(self, concept_id: str) -> Optional[ConceptNode]:
        return self.curriculum.concepts.get(concept_id)

    def add_concept(self, concept: ConceptNode) -> None:
        self.curriculum.concepts[concept.id] = concept
        self._validate_dag()

    def get_direct_prerequisites(self, concept_id: str) -> List[ConceptNode]:
        """Returns direct prerequisites for the given concept."""
        concept = self.get_concept(concept_id)
        if not concept:
            return []
        return [
            self.curriculum.concepts[pid]
            for pid in concept.prerequisites
            if pid in self.curriculum.concepts
        ]

    def get_all_prerequisites(self, concept_id: str) -> List[ConceptNode]:
        """Returns all transitive upstream prerequisites in topological dependency order."""
        visited: Set[str] = set()
        ordered: List[str] = []

        def dfs(curr_id: str):
            curr = self.get_concept(curr_id)
            if not curr:
                return
            for pid in curr.prerequisites:
                if pid not in visited:
                    visited.add(pid)
                    dfs(pid)
                    ordered.append(pid)

        dfs(concept_id)
        return [self.curriculum.concepts[pid] for pid in ordered if pid in self.curriculum.concepts]

    def get_direct_dependents(self, concept_id: str) -> List[ConceptNode]:
        """Returns concepts that directly depend on the given concept."""
        dependents = []
        for c in self.curriculum.concepts.values():
            if concept_id in c.prerequisites:
                dependents.append(c)
        return dependents

    def topological_order(self) -> List[ConceptNode]:
        """Returns all concepts ordered so prerequisites precede dependents."""
        in_degree: Dict[str, int] = {cid: 0 for cid in self.curriculum.concepts}
        for c in self.curriculum.concepts.values():
            for pid in c.prerequisites:
                if pid in self.curriculum.concepts:
                    pass  # c depends on pid

        # Calculate in-degrees (number of prerequisites)
        for cid, c in self.curriculum.concepts.items():
            in_degree[cid] = len([p for p in c.prerequisites if p in self.curriculum.concepts])

        queue = [cid for cid, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            # Sort queue for deterministic ordering
            queue.sort(key=lambda x: (self.curriculum.concepts[x].difficulty, x))
            curr_id = queue.pop(0)
            result.append(self.curriculum.concepts[curr_id])

            for dep in self.get_direct_dependents(curr_id):
                in_degree[dep.id] -= 1
                if in_degree[dep.id] == 0:
                    queue.append(dep.id)

        if len(result) != len(self.curriculum.concepts):
            # Fallback if any disconnected or cyclic remnants exist
            for c in self.curriculum.concepts.values():
                if c not in result:
                    result.append(c)

        return result

    def diagnose_root_cause(
        self,
        concept_id: str,
        student_mastery: Dict[str, float],
        mastery_threshold: float = 0.65,
    ) -> Optional[Tuple[ConceptNode, float, str]]:
        """
        Diagnoses why a student is struggling with a concept by inspecting upstream prerequisites.

        Returns (root_prerequisite_node, current_mastery, explanation) or None if prerequisites are sound.
        """
        concept = self.get_concept(concept_id)
        if not concept:
            return None

        prereqs = self.get_all_prerequisites(concept_id)
        if not prereqs:
            return None

        # Identify prerequisites below threshold
        deficient_prereqs = []
        for p in prereqs:
            score = student_mastery.get(p.id, 0.0)
            if score < mastery_threshold:
                deficient_prereqs.append((p, score))

        if not deficient_prereqs:
            return None

        # Sort by score ascending (lowest mastery first)
        deficient_prereqs.sort(key=lambda x: x[1])
        root_cause_node, lowest_score = deficient_prereqs[0]

        reason = (
            f"Student struggles with '{concept.name}' primarily because the foundational "
            f"prerequisite '{root_cause_node.name}' has low mastery ({lowest_score * 100:.1f}% vs "
            f"{mastery_threshold * 100:.0f}% threshold)."
        )
        return (root_cause_node, lowest_score, reason)

    def _validate_dag(self) -> None:
        """Verifies graph has no cycles and prerequisites exist."""
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def is_cyclic(cid: str) -> bool:
            visited.add(cid)
            rec_stack.add(cid)
            node = self.curriculum.concepts.get(cid)
            if node:
                for pid in node.prerequisites:
                    if pid in self.curriculum.concepts:
                        if pid not in visited:
                            if is_cyclic(pid):
                                return True
                        elif pid in rec_stack:
                            return True
            rec_stack.remove(cid)
            return False

        for cid in self.curriculum.concepts:
            if cid not in visited:
                if is_cyclic(cid):
                    raise ValueError(f"Cycle detected in concept mastery graph at '{cid}'")


# ============================================================================
# Pre-seeded Standard Curricula
# ============================================================================

def get_python_curriculum() -> Curriculum:
    """Pre-seeded curriculum for Python Programming & Computer Science."""
    concepts = {
        "py_variables": ConceptNode(
            id="py_variables",
            name="Variables, Data Types, & Expressions",
            domain="python_programming",
            description="Fundamental data types (int, float, str, bool), variable assignment, and arithmetic expressions.",
            prerequisites=[],
            difficulty=1,
            learning_objectives=[
                "Declare variables and assign values",
                "Perform arithmetic operations and type conversions",
                "Evaluate string expressions and formatting",
            ],
            rag_search_query="python variable assignment data types expressions",
            real_world_context="Used in calculating shopping cart totals, currency conversions, and user profile data.",
        ),
        "py_conditionals": ConceptNode(
            id="py_conditionals",
            name="Conditional Branching & Boolean Logic",
            domain="python_programming",
            description="if, elif, else logic blocks, comparison operators, and boolean truth tables.",
            prerequisites=["py_variables"],
            difficulty=2,
            learning_objectives=[
                "Write if/elif/else decision structures",
                "Combine boolean expressions using and, or, and not",
                "Handle boundary conditions",
            ],
            rag_search_query="python conditional statements if elif else boolean logic",
            real_world_context="Used in user authentication, access control gates, and pricing discount rules.",
        ),
        "py_loops": ConceptNode(
            id="py_loops",
            name="Iteration with While & For Loops",
            domain="python_programming",
            description="Repetitive execution, range() generator, break/continue controls, and loop accumulators.",
            prerequisites=["py_conditionals"],
            difficulty=2,
            learning_objectives=[
                "Iterate over sequences using for loops",
                "Execute condition-controlled while loops",
                "Implement accumulators and counters",
            ],
            rag_search_query="python for while loops iteration range break continue",
            real_world_context="Processing rows in a spreadsheet, reading stream packets, or searching logs.",
        ),
        "py_functions": ConceptNode(
            id="py_functions",
            name="Functions, Arguments, & Return Values",
            domain="python_programming",
            description="Modularity, parameter passing, return values, variable scope, and pure functions.",
            prerequisites=["py_variables"],
            difficulty=2,
            learning_objectives=[
                "Define and invoke functions with def",
                "Differentiate between parameters and arguments",
                "Understand local vs global variable scope",
            ],
            rag_search_query="python function definition parameters return scope",
            real_world_context="Modularizing microservices, writing reusable utility libraries, and math calculation helpers.",
        ),
        "py_lists_dicts": ConceptNode(
            id="py_lists_dicts",
            name="Lists, Tuples, & Dictionaries",
            domain="python_programming",
            description="Sequential collections, list slicing, key-value mappings with dicts, and nested structures.",
            prerequisites=["py_loops", "py_functions"],
            difficulty=3,
            learning_objectives=[
                "Create, index, slice, and mutate lists",
                "Store and query key-value pairs using dictionaries",
                "Iterate over dictionary keys, values, and items",
            ],
            rag_search_query="python list dictionary tuple data structures methods",
            real_world_context="Managing database records, parsing JSON API payloads, and aggregating inventory data.",
        ),
        "py_recursion": ConceptNode(
            id="py_recursion",
            name="Recursive Functions & Base Cases",
            domain="python_programming",
            description="Self-referential functions, recursive call stacks, base cases, and divide-and-conquer strategy.",
            prerequisites=["py_functions", "py_conditionals"],
            difficulty=4,
            learning_objectives=[
                "Identify and implement the base case",
                "Trace execution call stack during recursive descent",
                "Formulate recursive relations for factorial and Fibonacci",
            ],
            rag_search_query="python recursion base case recursive call stack",
            real_world_context="Traversing nested file directory trees, parsing JSON DOM trees, and backtracking algorithms.",
        ),
        "py_oop": ConceptNode(
            id="py_oop",
            name="Object-Oriented Programming (Classes & Objects)",
            domain="python_programming",
            description="Class definitions, __init__ constructor, instance attributes, methods, and encapsulation.",
            prerequisites=["py_functions", "py_lists_dicts"],
            difficulty=3,
            learning_objectives=[
                "Define classes with __init__ and self",
                "Instantiate objects and access instance methods",
                "Encapsulate state and behavior within class boundaries",
            ],
            rag_search_query="python object oriented programming class instance __init__ self",
            real_world_context="Modeling bank accounts, game characters, database entities, and HTTP client sessions.",
        ),
        "py_algorithms": ConceptNode(
            id="py_algorithms",
            name="Searching, Sorting, & Algorithmic Complexity",
            domain="python_programming",
            description="Linear search, binary search, bubble/merge sort, and Big-O runtime analysis.",
            prerequisites=["py_lists_dicts", "py_recursion"],
            difficulty=4,
            learning_objectives=[
                "Implement binary search on sorted lists",
                "Compare quadratic vs logarithmic time complexity",
                "Choose optimal data structure based on access patterns",
            ],
            rag_search_query="python binary search sorting algorithms big O complexity",
            real_world_context="Fast autocomplete search, database query optimization, and ranking search results.",
        ),
    }
    return Curriculum(
        domain="python_programming",
        title="Python Programming & Computer Science",
        description="Comprehensive foundation from basic variables to data structures, recursion, and algorithms.",
        concepts=concepts,
    )


def get_calculus_curriculum() -> Curriculum:
    """Pre-seeded curriculum for Mathematics & Calculus (matching the research paper)."""
    concepts = {
        "calc_functions": ConceptNode(
            id="calc_functions",
            name="Functions, Domain, & Graphs",
            domain="calculus",
            description="Algebraic function definitions, domain and range, graphs, and composition of functions.",
            prerequisites=[],
            difficulty=1,
            learning_objectives=[
                "Determine domain and range of algebraic functions",
                "Evaluate composite functions f(g(x))",
                "Interpret behavior from Cartesian function graphs",
            ],
            rag_search_query="calculus functions domain range composition graphs",
            real_world_context="Modeling trajectory curves, financial depreciation curves, and temperature variations.",
        ),
        "calc_limits": ConceptNode(
            id="calc_limits",
            name="Limits & Behavior Near Points",
            domain="calculus",
            description="Intuition of limits, one-sided limits, algebraic evaluation, and indeterminate forms 0/0.",
            prerequisites=["calc_functions"],
            difficulty=2,
            learning_objectives=[
                "Evaluate one-sided and two-sided limits graphically and algebraically",
                "Resolve indeterminate forms using factoring and rationalization",
                "Understand limit definition of asymptote",
            ],
            rag_search_query="calculus limits one sided indeterminate forms 0/0",
            real_world_context="Predicting instantaneous speed from average velocity as time interval approaches zero.",
        ),
        "calc_continuity": ConceptNode(
            id="calc_continuity",
            name="Continuity & The Intermediate Value Theorem",
            domain="calculus",
            description="Three-part definition of continuity at a point, jump and removable discontinuities, and IVT.",
            prerequisites=["calc_limits"],
            difficulty=2,
            learning_objectives=[
                "Verify continuity using: f(c) defined, lim x->c f(x) exists, and lim = f(c)",
                "Classify jump, removable, and infinite discontinuities",
                "Apply the Intermediate Value Theorem to prove roots exist",
            ],
            rag_search_query="calculus continuity removable discontinuity intermediate value theorem",
            real_world_context="Continuous electrical voltage transitions vs abrupt on/off switch events.",
        ),
        "calc_derivatives": ConceptNode(
            id="calc_derivatives",
            name="Differentiation & Rates of Change",
            domain="calculus",
            description="Difference quotient limit definition, Power Rule, Product Rule, Quotient Rule, and Chain Rule.",
            prerequisites=["calc_limits", "calc_continuity"],
            difficulty=3,
            learning_objectives=[
                "Compute derivatives from first principles using difference quotient",
                "Apply power, product, quotient, and chain rules smoothly",
                "Interpret derivative as instantaneous rate of change and tangent slope",
            ],
            rag_search_query="calculus differentiation derivative power product quotient chain rule",
            real_world_context="Acceleration in physics, marginal revenue in economics, and gradient descent in machine learning.",
        ),
        "calc_derivative_apps": ConceptNode(
            id="calc_derivative_apps",
            name="Optimization & Extrema (Applications of Derivatives)",
            domain="calculus",
            description="Critical points, First and Second Derivative Tests, local extrema, and real-world optimization.",
            prerequisites=["calc_derivatives"],
            difficulty=4,
            learning_objectives=[
                "Locate critical points where f'(x) = 0 or undefined",
                "Classify local maxima and minima using derivative tests",
                "Solve real-world optimization problems under constraints",
            ],
            rag_search_query="calculus optimization critical points extrema first second derivative test",
            real_world_context="Minimizing material packaging costs, maximizing rocket apogee, and optimal portfolio allocation.",
        ),
        "calc_integrals": ConceptNode(
            id="calc_integrals",
            name="Riemann Sums & Definite Integrals",
            domain="calculus",
            description="Area under curves, partition approximations, Riemann sums, and indefinite integral antiderivatives.",
            prerequisites=["calc_derivatives"],
            difficulty=3,
            learning_objectives=[
                "Approximate areas using left, right, and midpoint Riemann sums",
                "Relate definite integrals to net signed area under curve",
                "Compute antiderivatives using basic integration rules",
            ],
            rag_search_query="calculus definite integral riemann sums antiderivative area under curve",
            real_world_context="Computing total energy consumed from power consumption curve over time.",
        ),
        "calc_ftc": ConceptNode(
            id="calc_ftc",
            name="Fundamental Theorem of Calculus",
            domain="calculus",
            description="Bridging differentiation and integration: Part 1 (derivative of integral) and Part 2 (evaluation).",
            prerequisites=["calc_integrals", "calc_derivatives"],
            difficulty=4,
            learning_objectives=[
                "Differentiate definite integrals with variable limits",
                "Evaluate definite integrals using antiderivatives: ∫a^b f(x)dx = F(b) - F(a)",
                "Understand inverse relationship between differentiation and integration",
            ],
            rag_search_query="calculus fundamental theorem of calculus evaluation antiderivative",
            real_world_context="Calculating cumulative distance traveled from velocity telemetry data.",
        ),
    }
    return Curriculum(
        domain="calculus",
        title="Mathematics & Calculus",
        description="Comprehensive progression from functions and limits to differential and integral calculus.",
        concepts=concepts,
    )


def get_class10_maths_curriculum() -> Curriculum:
    """
    Class 10th Mathematics curriculum aligned with Indian NCERT, CBSE, ICSE, and State Boards.
    Covers Number Systems, Algebra, Coordinate Geometry, Geometry, Trigonometry, Mensuration, and Statistics/Probability.
    """
    concepts = {
        "c10_real_numbers": ConceptNode(
            id="c10_real_numbers",
            name="Real Numbers & Fundamental Theorem of Arithmetic",
            domain="class10_maths",
            description="Prime factorization, Fundamental Theorem of Arithmetic, HCF & LCM relationships, and proofs of irrationality of numbers (sqrt(2), sqrt(3), sqrt(5)).",
            prerequisites=[],
            difficulty=1,
            learning_objectives=[
                "Apply the Fundamental Theorem of Arithmetic to find HCF and LCM of integers",
                "Verify and use the relationship: HCF(a, b) * LCM(a, b) = a * b",
                "Construct formal contradiction proofs for the irrationality of surds",
            ],
            rag_search_query="class 10 real numbers fundamental theorem of arithmetic hcf lcm irrationality proof",
            real_world_context="Used in RSA digital cryptography, data hashing, and calculating synchronization intervals of traffic signals.",
        ),
        "c10_polynomials": ConceptNode(
            id="c10_polynomials",
            name="Polynomials: Zeros & Coefficients",
            domain="class10_maths",
            description="Geometric meaning of zeros of quadratic polynomials, and relationship between zeros and coefficients: alpha + beta = -b/a, alpha * beta = c/a.",
            prerequisites=["c10_real_numbers"],
            difficulty=2,
            learning_objectives=[
                "Determine the number of zeros from the Cartesian graph of y = p(x)",
                "Calculate zeros of a quadratic polynomial by splitting the middle term",
                "Verify relations between coefficients and zeros: alpha + beta = -b/a and alpha * beta = c/a",
            ],
            rag_search_query="class 10 polynomials quadratic zeros coefficients sum product alpha beta",
            real_world_context="Architectural parabolic bridge arches, projectile trajectories, and profit-maximization curves.",
        ),
        "c10_linear_equations": ConceptNode(
            id="c10_linear_equations",
            name="Pair of Linear Equations in Two Variables",
            domain="class10_maths",
            description="Graphical representation, algebraic solutions (substitution and elimination), and consistency conditions (intersecting, parallel, coincident lines).",
            prerequisites=["c10_real_numbers", "c10_polynomials"],
            difficulty=2,
            learning_objectives=[
                "Identify consistency using ratio comparisons: a1/a2 != b1/b2 (unique), a1/a2 = b1/b2 != c1/c2 (none), a1/a2 = b1/b2 = c1/c2 (infinite)",
                "Solve simultaneous equations using elimination and substitution methods",
                "Formulate and solve word problems (upstream/downstream speed, age, fraction problems)",
            ],
            rag_search_query="class 10 linear equations two variables elimination substitution consistency",
            real_world_context="Supply-demand market equilibrium, financial break-even analysis, and speed-time navigation vectors.",
        ),
        "c10_quadratic_equations": ConceptNode(
            id="c10_quadratic_equations",
            name="Quadratic Equations & Nature of Roots",
            domain="class10_maths",
            description="Standard form ax^2 + bx + c = 0, solution by factorisation and quadratic formula, and discriminant analysis D = b^2 - 4ac for real/equal/imaginary roots.",
            prerequisites=["c10_polynomials"],
            difficulty=3,
            learning_objectives=[
                "Transform word problems into standard quadratic equations ax^2 + bx + c = 0",
                "Apply the quadratic formula: x = (-b +- sqrt(b^2 - 4ac)) / (2a)",
                "Classify root nature using discriminant: D > 0 (two distinct real), D = 0 (two equal real), D < 0 (no real roots)",
            ],
            rag_search_query="class 10 quadratic equations quadratic formula discriminant nature of roots",
            real_world_context="Calculating stopping distance of automobiles under braking, satellite dish focal points, and ballistics.",
        ),
        "c10_arithmetic_progressions": ConceptNode(
            id="c10_arithmetic_progressions",
            name="Arithmetic Progressions (AP)",
            domain="class10_maths",
            description="Definition of AP, common difference d, general n-th term an = a + (n-1)d, and sum of first n terms Sn = (n/2)[2a + (n-1)d].",
            prerequisites=["c10_linear_equations"],
            difficulty=3,
            learning_objectives=[
                "Identify whether a sequence forms an AP by testing common difference d",
                "Find any term of an AP using an = a + (n-1)d",
                "Calculate total sum of terms using Sn = (n/2)[2a + (n-1)d] or Sn = (n/2)[a + l]",
            ],
            rag_search_query="class 10 arithmetic progression nth term sum first n terms common difference",
            real_world_context="Compound loan repayment schedules, stadium seating tier increments, and recurring savings plans.",
        ),
        "c10_triangles": ConceptNode(
            id="c10_triangles",
            name="Similar Triangles & Basic Proportionality Theorem",
            domain="class10_maths",
            description="Similarity of geometric figures, Basic Proportionality Theorem (Thales' Theorem) and its converse, and criteria for triangle similarity (AAA, SSS, SAS).",
            prerequisites=["c10_real_numbers"],
            difficulty=3,
            learning_objectives=[
                "State and prove the Basic Proportionality Theorem (BPT)",
                "Apply similarity criteria (AAA, SSS, SAS) to establish geometric proportions",
                "Solve multi-step geometric proofs involving parallel transversals",
            ],
            rag_search_query="class 10 triangles similarity basic proportionality theorem thales theorem",
            real_world_context="Land surveying using shadow lengths, architectural scale blueprints, and computer vision 3D reconstruction.",
        ),
        "c10_coordinate_geometry": ConceptNode(
            id="c10_coordinate_geometry",
            name="Coordinate Geometry: Distance & Section Formulae",
            domain="class10_maths",
            description="Distance formula d = sqrt((x2-x1)^2 + (y2-y1)^2), section formula for internal division (m1x2+m2x1)/(m1+m2), and midpoint formula.",
            prerequisites=["c10_real_numbers"],
            difficulty=2,
            learning_objectives=[
                "Compute Euclidean distance between two coordinate points",
                "Determine coordinates dividing a line segment in ratio m1:m2 using section formula",
                "Verify collinearity and geometric figure properties (rhombus, parallelogram, square)",
            ],
            rag_search_query="class 10 coordinate geometry distance formula section formula midpoint",
            real_world_context="GPS latitude/longitude triangulation, air traffic vector routing, and robotics path-planning.",
        ),
        "c10_trigonometry": ConceptNode(
            id="c10_trigonometry",
            name="Introduction to Trigonometry & Standard Identities",
            domain="class10_maths",
            description="Trigonometric ratios of acute angles in right-angled triangles, values at standard angles (0, 30, 45, 60, 90 degrees), and fundamental identity sin^2 + cos^2 = 1.",
            prerequisites=["c10_triangles"],
            difficulty=3,
            learning_objectives=[
                "Define sin, cos, tan, cosec, sec, and cot in a right triangle",
                "Evaluate trigonometric expressions at standard angles: 0, 30, 45, 60, and 90 degrees",
                "Prove trigonometric identities using sin^2(theta) + cos^2(theta) = 1, 1 + tan^2 = sec^2",
            ],
            rag_search_query="class 10 trigonometry standard angles trigonometric identities sin cos tan",
            real_world_context="Signal processing, sound acoustics wave analysis, and civil structural engineering loads.",
        ),
        "c10_applications_trig": ConceptNode(
            id="c10_applications_trig",
            name="Applications of Trigonometry: Heights & Distances",
            domain="class10_maths",
            description="Horizontal line of sight, angle of elevation, angle of depression, and calculating inaccessible heights and widths of structures.",
            prerequisites=["c10_trigonometry"],
            difficulty=4,
            learning_objectives=[
                "Differentiate between angle of elevation (looking up) and angle of depression (looking down)",
                "Construct accurate geometric schematics from descriptive real-world word problems",
                "Calculate heights of towers, hills, and river widths using trigonometric equations",
            ],
            rag_search_query="class 10 heights and distances angle of elevation depression line of sight",
            real_world_context="Maritime lighthouse beacon navigation, aerospace aircraft approach glide slope, and mountain peak altitude estimation.",
        ),
        "c10_circles": ConceptNode(
            id="c10_circles",
            name="Circles: Tangents & Geometric Theorems",
            domain="class10_maths",
            description="Tangent to a circle, theorem: tangent at any point is perpendicular to radius through point of contact, and theorem: lengths of tangents from an external point are equal.",
            prerequisites=["c10_triangles"],
            difficulty=3,
            learning_objectives=[
                "Prove that the tangent at any point is perpendicular to the radius through the point of contact",
                "Prove that lengths of tangents drawn from an external point to a circle are equal",
                "Apply circle tangent theorems to cyclic quadrilaterals and circumscribed polygons",
            ],
            rag_search_query="class 10 circles tangents to a circle perpendicular radius theorem external point",
            real_world_context="Mechanical gear engagement tooth design, railway track curved switch design, and pulley belt tensions.",
        ),
        "c10_surface_areas": ConceptNode(
            id="c10_surface_areas",
            name="Surface Areas and Volumes of Solids",
            domain="class10_maths",
            description="Surface areas and volumes of combinations of solids: cubes, cuboids, cylinders, cones, spheres, and hemispheres, and solid recasting/conversion.",
            prerequisites=["c10_real_numbers"],
            difficulty=4,
            learning_objectives=[
                "Calculate total and curved surface areas of composite solids (e.g. cylinder with hemispherical ends)",
                "Calculate total volume of combined three-dimensional geometric figures",
                "Solve volume-conservation conversion problems (e.g. melting metallic spheres to recast into a wire)",
            ],
            rag_search_query="class 10 surface areas volumes cylinder cone sphere hemisphere combination of solids",
            real_world_context="Industrial chemical storage tank sizing, rocket nose cone aerodynamic fairings, and beverage packaging volume optimization.",
        ),
        "c10_statistics": ConceptNode(
            id="c10_statistics",
            name="Statistics: Mean, Median, & Mode of Grouped Data",
            domain="class10_maths",
            description="Calculation of Mean (Direct and Assumed Mean methods), Median (cumulative frequency table), Mode of grouped frequency distributions, and the empirical relation 3 Median = Mode + 2 Mean.",
            prerequisites=["c10_real_numbers"],
            difficulty=2,
            learning_objectives=[
                "Calculate Mean using Direct Method and Assumed Mean Method",
                "Calculate Mode of grouped data using modal class formula: l + [(f1 - f0)/(2f1 - f0 - f2)] * h",
                "Determine Median using median class formula: l + [(n/2 - cf)/f] * h and verify empirical relationship",
            ],
            rag_search_query="class 10 statistics mean median mode grouped data assumed mean modal class",
            real_world_context="Epidemiological public health data distributions, census demographic analysis, and quality assurance variance tracking.",
        ),
        "c10_probability": ConceptNode(
            id="c10_probability",
            name="Classical Probability & Event Modeling",
            domain="class10_maths",
            description="Theoretical (classical) probability P(E) = n(E)/n(S), elementary events, impossible and sure events, and complementary events P(E) + P(not E) = 1.",
            prerequisites=["c10_real_numbers"],
            difficulty=2,
            learning_objectives=[
                "Compute theoretical probabilities for coin tosses, dice rolls, and deck of playing cards",
                "Apply the complementary event rule: P(E) + P(not E) = 1",
                "Distinguish between sure events (P=1) and impossible events (P=0)",
            ],
            rag_search_query="class 10 probability theoretical classical probability coin dice cards complementary event",
            real_world_context="Insurance actuarial risk pricing, clinical drug trial efficacy trials, and weather forecasting confidence modeling.",
        ),
    }
    return Curriculum(
        domain="class10_maths",
        title="Class 10th Mathematics (CBSE / ICSE / State Boards)",
        description="Comprehensive Indian Board Curriculum: Real Numbers, Algebra, Geometry, Coordinate Geometry, Trigonometry, Mensuration, and Statistics/Probability.",
        concepts=concepts,
    )


def get_available_curricula() -> Dict[str, Curriculum]:
    """Registry of built-in and loaded curricula, prioritizing Class 10th Mathematics."""
    c10 = get_class10_maths_curriculum()
    py = get_python_curriculum()
    calc = get_calculus_curriculum()
    return {
        c10.domain: c10,
        py.domain: py,
        calc.domain: calc,
    }
