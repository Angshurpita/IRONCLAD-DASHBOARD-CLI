# Machine Learning & Artificial Intelligence: Core Foundational Knowledge Base

## 1. Supervised Learning Foundations
Supervised learning is the machine learning paradigm where an algorithm learns a mapping function from input features $X \in \mathbb{R}^{n \times d}$ to ground-truth target labels $Y \in \mathbb{R}^n$. The goal is empirical risk minimization over a training dataset $\mathcal{D} = \{(x_i, y_i)\}_{i=1}^N$ such that generalization error on unseen data is minimized. Generalization is evaluated using cross-validation and strict separation of training, validation, and test partitions to diagnose underfitting (high bias) and overfitting (high variance).

### 1.1 Linear Regression & Gradient Descent
Linear regression models the relationship between dependent continuous targets and continuous predictors:
$$\hat{y} = w^T x + b = \sum_{j=1}^d w_j x_j + b$$
The model parameters $w$ and $b$ are optimized by minimizing the Mean Squared Error (MSE) loss function:
$$\mathcal{L}_{MSE}(w, b) = \frac{1}{2N} \sum_{i=1}^N (\hat{y}_i - y_i)^2$$
Optimization is performed iteratively using Gradient Descent with learning rate $\eta$:
$$w \leftarrow w - \eta \nabla_w \mathcal{L} = w - \frac{\eta}{N} \sum_{i=1}^N (\hat{y}_i - y_i) x_i$$
To combat overfitting in multicollinear feature spaces, $L_2$ Ridge regularization adds $\lambda ||w||_2^2$ penalty while $L_1$ Lasso regularization adds $\lambda ||w||_1$ penalty enforcing sparse feature selection.

### 1.2 Logistic Regression & Binary Classification
Logistic regression adapts linear models to probabilistic classification by passing the linear logit through the sigmoid activation function:
$$\sigma(z) = \frac{1}{1 + e^{-z}}, \quad P(y=1|x) = \sigma(w^T x + b)$$
The model parameters are estimated by maximizing the Bernoulli likelihood, equivalent to minimizing the Binary Cross-Entropy (BCE) log-loss:
$$\mathcal{L}_{BCE} = -\frac{1}{N} \sum_{i=1}^N \left[ y_i \log(\hat{y}_i) + (1 - y_i) \log(1 - \hat{y}_i) \right]$$
Decision thresholds default to $P \ge 0.5$ but are tuned to balance precision and recall using Receiver Operating Characteristic (ROC) curves and Area Under Curve (AUC).

### 1.3 Decision Trees & Ensemble Methods
Decision trees partition feature space through greedy recursive binary splitting. At each internal node, the feature and threshold that maximize Information Gain or minimize Gini Impurity are selected:
$$\text{Gini}(S) = 1 - \sum_{k=1}^K p_k^2, \quad \text{Entropy}(S) = -\sum_{k=1}^K p_k \log_2(p_k)$$
To overcome high variance and overfitting of single trees, ensemble methods aggregate multiple learners:
- **Bagging (Random Forests)**: Trains independent decorrelated trees on bootstrap replicas of data with random feature subspace sampling.
- **Boosting (Gradient Boosted Trees / XGBoost)**: Sequentially fits shallow trees to pseudo-residuals of previous models: $F_m(x) = F_{m-1}(x) + \gamma_m h_m(x)$.

### 1.4 Deep Neural Networks & Backpropagation
Artificial neural networks arrange computational units in stacked affine transformations followed by non-linear activations:
$$z^{[l]} = W^{[l]} a^{[l-1]} + b^{[l]}, \quad a^{[l]} = g^{[l]}(z^{[l]})$$
Activations like Rectified Linear Unit (ReLU) $g(z) = \max(0, z)$ and GELU prevent vanishing gradients across deep architectures. Training optimizes weights via the Backpropagation algorithm, which computes gradients using the multivariate calculus Chain Rule:
$$\frac{\partial \mathcal{L}}{\partial W^{[l]}} = \delta^{[l]} (a^{[l-1]})^T, \quad \delta^{[l]} = (W^{[l+1]})^T \delta^{[l+1]} \odot g'^{[l]}(z^{[l]})$$
Modern adaptive optimizers like Adam combine exponentially decaying running averages of past gradients (momentum) and squared gradients (RMSProp) to stabilize convergence.

---

## 2. Unsupervised Learning Foundations
Unsupervised learning models uncover hidden statistical structures, geometric manifolds, and latent distributions within unlabeled data $X = \{x_1, \dots, x_N\}$ without supervisory targets.

### 2.1 Clustering & K-Means Optimization
Clustering groups observations into cohesive clusters where intra-cluster similarity is maximized and inter-cluster similarity is minimized. The K-Means algorithm partitions $N$ points into $K$ disjoint clusters $S = \{S_1, \dots, S_K\}$ by minimizing the within-cluster sum of squares (Inertia):
$$\mathcal{J} = \sum_{k=1}^K \sum_{x \in S_k} ||x - \mu_k||^2$$
Lloyd's algorithm alternates between two steps until convergence:
1. **Assignment step**: Assign each data point $x_i$ to its nearest centroid $\mu_k = \arg\min_j ||x_i - \mu_j||^2$.
2. **Update step**: Recompute centroids as cluster sample means $\mu_k = \frac{1}{|S_k|} \sum_{x \in S_k} x$.
Optimal cluster count $K$ is determined via the Elbow Method (inflection point of inertia curve) and Silhouette Analysis measuring cluster cohesion versus separation: $s(i) = \frac{b(i) - a(i)}{\max(a(i), b(i))}$.

### 2.2 Dimensionality Reduction & Principal Component Analysis (PCA)
Principal Component Analysis (PCA) performs orthogonal linear transformations to project high-dimensional data onto lower-dimensional subspaces while retaining maximal variance.
Given zero-centered data matrix $X \in \mathbb{R}^{N \times d}$, PCA computes the empirical covariance matrix:
$$\Sigma = \frac{1}{N-1} X^T X$$
Spectral eigendecomposition yields eigenvalues $\lambda_1 \ge \lambda_2 \ge \dots \ge \lambda_d$ and corresponding orthonormal eigenvectors $v_1, \dots, v_d$:
$$\Sigma v_j = \lambda_j v_j$$
The top $k$ eigenvectors form the projection matrix $W_k = [v_1, \dots, v_k]$, transforming data to reduced representation $Z = X W_k \in \mathbb{R}^{N \times k}$. The proportion of variance explained is $\frac{\sum_{j=1}^k \lambda_j}{\sum_{j=1}^d \lambda_j}$.

### 2.3 Anomaly & Outlier Detection
Anomaly detection identifies instances that deviate significantly from expected normal distributions. Core methodologies include:
- **Isolation Forests**: Isolates anomalies by random partitioning; anomalous points have shorter average path lengths in isolation trees.
- **Gaussian Mixture Models (GMM)**: Models data as a superposition of $K$ multivariate Gaussian components with parameters estimated via Expectation-Maximization (EM). Points with low log-likelihood are flagged as anomalies.

---

## 3. Reinforcement Learning Foundations
Reinforcement learning formalized optimal decision making through trial-and-error interactions between an active Agent and an external Environment.

### 3.1 The Agent-Environment Interaction Loop
At discrete time step $t$, the agent observes environment state $s_t \in \mathcal{S}$, selects action $a_t \in \mathcal{A}$ according to policy $\pi(a|s)$, receives scalar reward $r_{t+1} \in \mathbb{R}$, and transitions to next state $s_{t+1} \sim \mathcal{P}(\cdot|s_t, a_t)$.
The agent's objective is to maximize expected discounted cumulative future return:
$$G_t = \sum_{k=0}^\infty \gamma^k r_{t+k+1}$$
where $\gamma \in [0, 1)$ is the discount factor balancing immediate and long-term rewards.

### 3.2 Markov Decision Processes & Bellman Equations
A Markov Decision Process (MDP) is defined by the 5-tuple $(\mathcal{S}, \mathcal{A}, \mathcal{P}, \mathcal{R}, \gamma)$. The Markov Property asserts that future states depend only on current state and action:
$$P(s_{t+1}=s', r_{t+1}=r \mid s_t, a_t, s_{t-1}, a_{t-1}, \dots) = P(s_{t+1}=s', r_{t+1}=r \mid s_t, a_t)$$
The State-Value Function $V^\pi(s)$ and Action-Value Function $Q^\pi(s, a)$ represent expected returns under policy $\pi$. They obey recursive Bellman Expectation Equations:
$$V^\pi(s) = \sum_{a \in \mathcal{A}} \pi(a|s) \sum_{s', r} \mathcal{P}(s', r \mid s, a) \left[ r + \gamma V^\pi(s') \right]$$
$$Q^\pi(s, a) = \sum_{s', r} \mathcal{P}(s', r \mid s, a) \left[ r + \gamma \sum_{a'} \pi(a'|s') Q^\pi(s', a') \right]$$
The Bellman Optimality Equation states that the optimal value is achievable by selecting the maximizing action:
$$Q^*(s, a) = \mathbb{E}_{s'} \left[ r + \gamma \max_{a'} Q^*(s', a') \;\middle|\; s, a \right]$$

### 3.3 Model-Free RL: Q-Learning & Policy Gradients
When environment transition dynamics $\mathcal{P}$ are unknown, model-free methods learn directly from sampled experience:
- **Temporal Difference Q-Learning (Off-Policy TD Control)**: Updates action-values using one-step bootstrapping towards the greedy target:
$$Q(s_t, a_t) \leftarrow Q(s_t, a_t) + \alpha \left[ r_{t+1} + \gamma \max_a Q(s_{t+1}, a) - Q(s_t, a_t) \right]$$
Deep Q-Networks (DQN) parameterize $Q(s, a; \theta)$ using deep neural networks stabilized by experience replay buffers and target networks.
- **Policy Gradient Methods (REINFORCE & Actor-Critic)**: Directly parameterize policy $\pi_\theta(a|s)$ and optimize expected return $J(\theta) = \mathbb{E}_{\tau \sim \pi_\theta}[R(\tau)]$ via gradient ascent. The Policy Gradient Theorem provides:
$$\nabla_\theta J(\theta) = \mathbb{E}_{\pi_\theta} \left[ \nabla_\theta \log \pi_\theta(a_t|s_t) Q^{\pi_\theta}(s_t, a_t) \right]$$
Subtracting a state-dependent baseline $V(s_t)$ yields the Advantage function $A(s_t, a_t) = Q(s_t, a_t) - V(s_t)$, significantly reducing gradient variance.
