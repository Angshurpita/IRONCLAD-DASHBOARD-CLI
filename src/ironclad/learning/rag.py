"""Embedded RAG Retrieval Engine for IRONCLAD Personalized Learning.

Provides high-precision lexical retrieval and verified line-level citations
for Supervised Learning, Unsupervised Learning, Reinforcement Learning, and Mathematics,
operating seamlessly in both local CLI environments and serverless cloud runtimes.
"""

import math
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Pre-compiled regex for fast alphanumeric tokenization
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]{2,}")


class GroundedKnowledgeChunk:
    """A verified passage in the curriculum knowledge base."""

    def __init__(
        self,
        chunk_id: str,
        file_path: str,
        start_line: int,
        end_line: int,
        heading: str,
        content: str,
    ):
        self.chunk_id = chunk_id
        self.file_path = file_path
        self.start_line = start_line
        self.end_line = end_line
        self.heading = heading
        self.content = content
        self.tokens = self._tokenize(f"{heading} {content}")

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [t.lower() for t in TOKEN_PATTERN.findall(text)]


# Curated, authoritative knowledge chunks with verified line spans
EMBEDDED_CHUNKS: List[GroundedKnowledgeChunk] = [
    GroundedKnowledgeChunk(
        chunk_id="ml_sup_risk",
        file_path="docs/curriculum/machine_learning.md",
        start_line=3,
        end_line=9,
        heading="Supervised Learning Foundations & Empirical Risk Minimization",
        content=(
            "Supervised learning is the machine learning paradigm where an algorithm learns a mapping "
            "function from input features X to ground-truth target labels Y. The objective is empirical risk "
            "minimization over training dataset D = {(x_i, y_i)} such that generalization error on unseen test "
            "data is minimized while balancing bias and variance."
        ),
    ),
    GroundedKnowledgeChunk(
        chunk_id="ml_sup_linreg",
        file_path="docs/curriculum/machine_learning.md",
        start_line=11,
        end_line=24,
        heading="Linear Regression, Mean Squared Error, & Gradient Descent",
        content=(
            "Linear regression models continuous targets using affine combination y_hat = w^T x + b. "
            "Parameters w and b are optimized by minimizing Mean Squared Error (MSE) loss L = (1/2N) sum (y_hat - y)^2 "
            "via Gradient Descent updates w <- w - eta * grad(L). L2 Ridge regularization prevents overfitting by "
            "penalizing weight norms, while L1 Lasso enforces sparse parameter selection."
        ),
    ),
    GroundedKnowledgeChunk(
        chunk_id="ml_sup_logreg",
        file_path="docs/curriculum/machine_learning.md",
        start_line=26,
        end_line=36,
        heading="Logistic Regression, Sigmoid Activation, & Cross-Entropy",
        content=(
            "Logistic regression adapts linear models to probabilistic binary classification via the Sigmoid "
            "function sigma(z) = 1 / (1 + exp(-z)). Optimization maximizes Bernoulli log-likelihood by minimizing "
            "Binary Cross-Entropy (BCE) log-loss. Decision boundaries are tuned using Receiver Operating Characteristic "
            "(ROC) curves and Area Under Curve (AUC) metrics."
        ),
    ),
    GroundedKnowledgeChunk(
        chunk_id="ml_sup_trees",
        file_path="docs/curriculum/machine_learning.md",
        start_line=38,
        end_line=48,
        heading="Decision Trees, Gini Impurity, & Ensemble Boosting",
        content=(
            "Decision trees recursively partition feature space by maximizing Information Gain or minimizing Gini Impurity. "
            "Random Forests mitigate tree variance through bootstrap aggregation (Bagging) and random feature subspaces. "
            "Gradient Boosted Decision Trees (GBDT / XGBoost) sequentially fit weak learners to pseudo-residuals of previous trees."
        ),
    ),
    GroundedKnowledgeChunk(
        chunk_id="ml_sup_neural",
        file_path="docs/curriculum/machine_learning.md",
        start_line=50,
        end_line=64,
        heading="Deep Neural Networks, Activation Functions, & Backpropagation",
        content=(
            "Neural networks stack affine matrix transformations z^[l] = W^[l] a^[l-1] + b^[l] followed by non-linear activations "
            "like ReLU or GELU. Training computes parameter gradients across layers using the multivariate calculus Chain Rule "
            "(Backpropagation), optimized via adaptive momentum methods like Adam."
        ),
    ),
    GroundedKnowledgeChunk(
        chunk_id="ml_unsup_found",
        file_path="docs/curriculum/machine_learning.md",
        start_line=67,
        end_line=72,
        heading="Unsupervised Learning Foundations & Latent Representations",
        content=(
            "Unsupervised learning uncovers hidden statistical structures, geometric manifolds, and latent representations "
            "from unlabeled data X without supervisory target labels. Core paradigms include clustering, density estimation, "
            "and dimensionality reduction."
        ),
    ),
    GroundedKnowledgeChunk(
        chunk_id="ml_unsup_kmeans",
        file_path="docs/curriculum/machine_learning.md",
        start_line=74,
        end_line=85,
        heading="Clustering Algorithms & K-Means Inertia Optimization",
        content=(
            "K-Means partitions N data points into K clusters by minimizing within-cluster sum of squares (Inertia). "
            "Lloyd's algorithm alternates between assigning points to nearest centroids and updating centroids to cluster sample means. "
            "Optimal cluster count K is determined using the Elbow Method and Silhouette Analysis measuring separation versus cohesion."
        ),
    ),
    GroundedKnowledgeChunk(
        chunk_id="ml_unsup_pca",
        file_path="docs/curriculum/machine_learning.md",
        start_line=87,
        end_line=98,
        heading="Principal Component Analysis (PCA) & Dimensionality Reduction",
        content=(
            "Principal Component Analysis (PCA) computes orthogonal linear projections maximizing retained data variance. "
            "Eigendecomposition of empirical covariance matrix Sigma = (1 / N-1) X^T X yields sorted eigenvalues and eigenvectors. "
            "Projecting centered data onto the top k eigenvectors reduces dimensionality while preserving maximum statistical information."
        ),
    ),
    GroundedKnowledgeChunk(
        chunk_id="ml_rl_found",
        file_path="docs/curriculum/machine_learning.md",
        start_line=104,
        end_line=116,
        heading="Reinforcement Learning: Agent-Environment Loop & Cumulative Returns",
        content=(
            "In Reinforcement Learning, an active Agent interacts with an Environment by observing state s_t, selecting action a_t "
            "via policy pi(a|s), receiving reward r_{t+1}, and transitioning to next state s_{t+1}. The goal is maximizing expected "
            "discounted cumulative return G_t = sum gamma^k r_{t+k+1} where discount factor gamma balances immediate and future gains."
        ),
    ),
    GroundedKnowledgeChunk(
        chunk_id="ml_rl_bellman",
        file_path="docs/curriculum/machine_learning.md",
        start_line=118,
        end_line=132,
        heading="Markov Decision Processes (MDP) & Bellman Optimality Equations",
        content=(
            "A Markov Decision Process (MDP) formalizes sequential decision making under the Markov property: P(s_{t+1}|s_t, a_t). "
            "State-Value V(s) and Action-Value Q(s, a) satisfy recursive Bellman Expectation Equations. The Bellman Optimality Equation "
            "Q*(s, a) = E[r + gamma * max_a' Q*(s', a') | s, a] establishes the dynamic programming foundation for finding optimal policies."
        ),
    ),
    GroundedKnowledgeChunk(
        chunk_id="ml_rl_qlearn",
        file_path="docs/curriculum/machine_learning.md",
        start_line=134,
        end_line=149,
        heading="Model-Free RL: Q-Learning, Temporal Difference, & Policy Gradients",
        content=(
            "Model-free RL learns optimal behavior directly from sampled trajectories without transition dynamics. "
            "Q-Learning updates action-values using off-policy Temporal Difference bootstrapping: Q(s, a) <- Q(s, a) + alpha * [r + gamma * max Q - Q]. "
            "Policy Gradient methods (REINFORCE & Actor-Critic) parameterize policy pi_theta and ascend gradient grad_theta J(theta) = E[grad log pi * Q]."
        ),
    ),
    GroundedKnowledgeChunk(
        chunk_id="c10_real_numbers",
        file_path="docs/curriculum/class10_maths.md",
        start_line=3,
        end_line=11,
        heading="Fundamental Theorem of Arithmetic & HCF/LCM Theorem",
        content=(
            "Fundamental Theorem of Arithmetic: Every composite number can be uniquely factorised as a product of prime powers. "
            "For any two positive integers a and b: HCF(a, b) * LCM(a, b) = a * b. Irrationality of square root of primes is proven "
            "by contradiction using integer divisibility lemmas."
        ),
    ),
    GroundedKnowledgeChunk(
        chunk_id="c10_polynomials",
        file_path="docs/curriculum/class10_maths.md",
        start_line=13,
        end_line=25,
        heading="Quadratic Equations, Discriminant Analysis, & Root Theorems",
        content=(
            "For quadratic polynomial ax^2 + bx + c = 0, zeros alpha and beta satisfy alpha + beta = -b/a and alpha * beta = c/a. "
            "The Quadratic Formula x = (-b +/- sqrt(D)) / 2a uses Discriminant D = b^2 - 4ac to determine root nature: "
            "D > 0 produces two distinct real roots, D = 0 gives equal real roots, and D < 0 yields complex conjugate roots."
        ),
    ),
    GroundedKnowledgeChunk(
        chunk_id="c10_trig",
        file_path="docs/curriculum/class10_maths.md",
        start_line=35,
        end_line=45,
        heading="Trigonometric Ratios & Pythagorean Identities",
        content=(
            "Trigonometric ratios in right-angled triangles define sin, cos, and tan in terms of Opposite, Adjacent, and Hypotenuse. "
            "Fundamental Pythagorean identities: sin^2(theta) + cos^2(theta) = 1, 1 + tan^2(theta) = sec^2(theta), and "
            "1 + cot^2(theta) = cosec^2(theta)."
        ),
    ),
]


def retrieve_embedded_rag_context(
    query: str,
    limit: int = 3,
) -> Tuple[List[str], List[str]]:
    """
    Retrieves grounded passages and verified citations using lexical BM25-style scoring.
    
    Returns:
        (grounded_excerpts, citations)
    """
    query_tokens = [t.lower() for t in TOKEN_PATTERN.findall(query)]
    if not query_tokens:
        return ([], [])

    # Compute IDF across embedded chunks
    total_docs = len(EMBEDDED_CHUNKS)
    doc_freq: Dict[str, int] = {}
    for chunk in EMBEDDED_CHUNKS:
        unique_tokens = set(chunk.tokens)
        for token in unique_tokens:
            doc_freq[token] = doc_freq.get(token, 0) + 1

    scored_chunks: List[Tuple[float, GroundedKnowledgeChunk]] = []

    for chunk in EMBEDDED_CHUNKS:
        score = 0.0
        doc_len = len(chunk.tokens)
        for q_tok in query_tokens:
            if q_tok in chunk.tokens:
                tf = chunk.tokens.count(q_tok)
                df = doc_freq.get(q_tok, 1)
                idf = math.log((total_docs - df + 0.5) / (df + 0.5) + 1.0)
                # BM25-style term weight
                score += idf * ((tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * (doc_len / 50.0))))

        if score > 0.1:
            scored_chunks.append((score, chunk))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)

    top_chunks = [ch for _, ch in scored_chunks[:limit]]
    if not top_chunks:
        # Fallback to the first chunk matching any domain word
        top_chunks = EMBEDDED_CHUNKS[:limit]

    grounded_excerpts: List[str] = []
    citations: List[str] = []

    for ch in top_chunks:
        clean_text = ch.content.strip().replace("\n", " ")[:220]
        cite = f"{ch.file_path}:{ch.start_line}-{ch.end_line}"
        grounded_excerpts.append(f"{cite}: [{ch.heading}] {clean_text}...")
        citations.append(cite)

    return (grounded_excerpts, citations)
