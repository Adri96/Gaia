"""
Gaia v0.7 -- Endogenous pricing engine. EXPERIMENTAL (decision D4).

Quarantined (Step 4, C8): opt-in with ``--with-pricing``, labelled
experimental in every output, every agent must be anchored, convergence is
certified with guaranteed bounds, and a state that cannot be certified
raises PricingConvergenceError — no fallback price is ever substituted.
Known open problems (the "proper fix", not done): V = S·W·V + S·A counts
upstream value once per dependent agent, and the whole loss is priced at
the end-state scarcity price instead of integrating the marginal price.

Implements a Leontief-Hannon input-output pricing model for ecosystem services.
Prices emerge endogenously from network structure, scarcity, and anchor values
rather than being fixed exogenously as static agent annual values.

The theoretical foundation draws on three pillars:

    1. Leontief (1970) input-output economics: agents in an ecosystem form a
       production network where each agent's output is another's input. The
       price of each agent's services depends on the prices of its dependencies.

    2. Hannon (1973) ecological-economic model: extends Leontief to ecosystems,
       treating species/services as sectors. The technical coefficients matrix W
       captures how much of each agent's "production" flows to others.

    3. Scarcity pricing: health-dependent multipliers amplify prices as agents
       become scarce, following either a smooth inverse-power law or a threshold
       function with quadratic rise below critical health.

The price system solves the fixed-point equation:

    V = (I - S*W)^(-1) * S * A

where:
    V = price vector (N agents)
    S = diagonal scarcity matrix (health-dependent multipliers)
    W = value-flow matrix (W[i][j] = how much of agent i's value derives from j)
    A = anchor vector (externally grounded prices from market data)
    I = identity matrix

The value-flow matrix W is the TRANSPOSE of the damage propagation direction.
If edge (source -> target) means "source's damage propagates to target", then
target's value depends on source, so W[target][source] = strength. This way,
the row for agent i in the equation V[i] = sum_j(S[i]*W[i][j]*V[j]) + S[i]*A[i]
picks up value contributions from all agents that agent i depends on.

Convergence requires spectral_radius(S*W) < 1.0, ensuring the geometric series
I + SW + (SW)^2 + ... converges. It is proven per state, never estimated
(certify_convergence): first with the row/column sum bound, then by direct
iteration with Collatz–Wielandt bounds. When it cannot be proven, the state
has no price and PricingConvergenceError is raised.

All functions use primitive types (no numpy).
No third-party dependencies.

Scientific references:
    - Leontief W (1970) Environmental repercussions and the economic structure.
    - Hannon B (1973) The structure of ecosystems. J Theor Biol.
    - Costanza R et al. (1997) The value of the world's ecosystem services.
    - de Groot R et al. (2012) Global estimates of the value of ecosystems.
"""

import dataclasses
from typing import Dict, List, Optional, Tuple

from gaia.models import (
    AnchorPoint,
    InteractionEdge,
    PriceResult,
    PricingConfig,
    ScarcityFunction,
)


# ── Anchor scaling ──────────────────────────────────────────────────────────


def scale_anchors(pricing: PricingConfig, factor: float) -> PricingConfig:
    """Return a copy of ``pricing`` with every anchor value multiplied by ``factor``.

    Case files state anchors in €/yr for a reference area; the builder scales
    them by ``area_ha / reference_area`` so anchors stay per-hectare
    consistent with the agents' €/ha/yr values (decision D2).
    """
    return dataclasses.replace(
        pricing,
        anchors=[
            dataclasses.replace(a, anchor_value=a.anchor_value * factor)
            for a in pricing.anchors
        ],
    )


def anchor_every_agent(
    pricing: PricingConfig,
    agents: list,
    area_ha: float,
) -> PricingConfig:
    """Return a copy of ``pricing`` with an anchor for every agent.

    Pricing requires every agent to be anchored (Step 4, C8). An agent with
    no documented anchor gets a PLACEHOLDER one: its own direct annual
    service value, annual_value_per_ha × area_ha (€/yr), the same €/yr scale
    as the documented anchors and the static values. Documented anchors are
    kept as they are.

    Args:
        pricing: PricingConfig whose anchors are already scaled to area_ha.
        agents: The ecosystem's agents.
        area_ha: Resource area (ha).
    """
    anchored = {a.agent_name for a in pricing.anchors}
    derived = [
        AnchorPoint(
            agent_name=agent.name,
            anchor_value=agent.annual_value(area_ha),
            source=(
                "PLACEHOLDER: no documented anchor; the agent's own direct "
                "annual service value, annual_value_per_ha × area_ha"
            ),
            confidence="low",
            description=(
                f"Direct service value: €{agent.annual_value_per_ha:,.2f}/ha/yr "
                f"× {area_ha:,.2f} ha [PLACEHOLDER]"
            ),
        )
        for agent in agents
        if agent.name not in anchored
    ]
    return dataclasses.replace(pricing, anchors=list(pricing.anchors) + derived)


# ── Scarcity computation ────────────────────────────────────────────────────


def compute_scarcity(health: float, scarcity_fn: ScarcityFunction) -> float:
    """Compute the scarcity price multiplier for a given agent health.

    Maps agent health (0.0 = collapsed, 1.0 = pristine) to a price multiplier
    (1.0 = no scarcity premium, up to max_multiplier at collapse).

    Two function types:
        smooth: scarcity = min(max_multiplier, 1.0 / health^alpha)
            Continuous, differentiable. Good default for gradual degradation.
        threshold: 1.0 above threshold, quadratic rise below:
            scarcity = 1.0 + (max_multiplier - 1.0) * ((threshold - health) / threshold)^2
            Models tipping-point dynamics where prices remain stable until a
            critical health level is breached.

    Args:
        health: Agent health fraction in [0.0, 1.0].
        scarcity_fn: ScarcityFunction defining the mapping.

    Returns:
        Price multiplier >= 1.0. At health=1.0, returns 1.0. At health=0.0,
        returns max_multiplier.
    """
    max_mult: float = scarcity_fn.max_multiplier

    # Edge cases: health at boundaries
    if health <= 0.0:
        return max_mult
    if health >= 1.0:
        return 1.0

    if scarcity_fn.function_type == "smooth":
        alpha: float = scarcity_fn.alpha
        # Protect against near-zero health producing infinity
        raw: float = 1.0 / max(health, 1e-10) ** alpha
        if raw > max_mult:
            return max_mult
        return raw

    elif scarcity_fn.function_type == "threshold":
        threshold: float = scarcity_fn.threshold
        if health >= threshold:
            return 1.0
        # Quadratic rise below threshold
        ratio: float = (threshold - health) / threshold
        return 1.0 + (max_mult - 1.0) * ratio * ratio

    # Fallback for unknown types (should not happen after validation)
    return 1.0


# ── Matrix construction ─────────────────────────────────────────────────────


def build_scarcity_matrix(
    agent_names: List[str],
    agent_healths: Dict[str, float],
    pricing: PricingConfig,
) -> List[List[float]]:
    """Build the diagonal scarcity matrix S.

    S is an N x N diagonal matrix where S[i][i] = scarcity(health_i) using
    the agent-specific scarcity function if configured, otherwise the default.
    Off-diagonal elements are zero.

    Args:
        agent_names: Ordered list of agent names defining matrix indices.
        agent_healths: Health fraction per agent (0.0 to 1.0).
        pricing: PricingConfig containing scarcity functions and defaults.

    Returns:
        N x N diagonal matrix as list of lists.
    """
    n: int = len(agent_names)
    matrix: List[List[float]] = [[0.0] * n for _ in range(n)]

    for i in range(n):
        name: str = agent_names[i]
        health: float = agent_healths.get(name, 1.0)
        scarcity_fn: ScarcityFunction = pricing.scarcity_functions.get(
            name, pricing.default_scarcity
        )
        matrix[i][i] = compute_scarcity(health, scarcity_fn)

    return matrix


def build_value_matrix(
    agent_names: List[str],
    interactions: List[InteractionEdge],
) -> List[List[float]]:
    """Build the value-flow matrix W from interaction edges.

    W[target_idx][source_idx] = edge_strength. This is the TRANSPOSE of the
    damage propagation direction: if agent A's damage propagates to agent B
    (edge source=A, target=B), then B depends on A for its value, so
    W[target_idx][source_idx] = strength.

    In Leontief terms: W[i][j] represents how much of agent i's value is
    derived from agent j's services. This ensures that in the equation
    V[i] = sum_j(S[i]*W[i][j]*V[j]) + S[i]*A[i], agent i's price includes
    contributions from agents it depends on (those that damage-propagate to it).

    The row sums should ideally be < 1.0 for the system to be productive
    (spectral radius condition).

    Args:
        agent_names: Ordered list of agent names defining matrix indices.
        interactions: List of InteractionEdge defining dependencies.

    Returns:
        N x N value-flow matrix as list of lists.
    """
    n: int = len(agent_names)
    # Build name-to-index lookup
    name_to_idx: Dict[str, int] = {}
    for i in range(n):
        name_to_idx[agent_names[i]] = i

    matrix: List[List[float]] = [[0.0] * n for _ in range(n)]

    for edge in interactions:
        src_idx: int = name_to_idx.get(edge.source, -1)
        tgt_idx: int = name_to_idx.get(edge.target, -1)
        if src_idx >= 0 and tgt_idx >= 0:
            # Target depends on source: W[target][source] = strength
            matrix[tgt_idx][src_idx] = edge.strength

    return matrix


def build_anchor_vector(
    agent_names: List[str],
    anchors: List[AnchorPoint],
) -> List[float]:
    """Build the anchor price vector A.

    Anchors ground the relative price system in absolute euro values.
    Each anchor provides an external market price for one agent. Agents
    without anchors get 0.0, which solve_prices rejects: every agent must
    be anchored when pricing is on (an unanchored agent used to be priced
    at €0, C8).

    If multiple anchors exist for the same agent, values are summed
    (weighted by confidence could be a future extension).

    Args:
        agent_names: Ordered list of agent names defining vector indices.
        anchors: List of AnchorPoint with agent-specific anchor values.

    Returns:
        N-length vector with anchor values for anchored agents, 0.0 for others.
    """
    n: int = len(agent_names)
    name_to_idx: Dict[str, int] = {}
    for i in range(n):
        name_to_idx[agent_names[i]] = i

    vector: List[float] = [0.0] * n

    for anchor in anchors:
        idx: int = name_to_idx.get(anchor.agent_name, -1)
        if idx >= 0:
            vector[idx] += anchor.anchor_value

    return vector


# ── Linear algebra primitives (pure Python) ─────────────────────────────────


def matrix_multiply(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    """Multiply two matrices A and B.

    Standard O(n^3) matrix multiplication. Both matrices must be compatible:
    A is m x p and B is p x n, producing an m x n result.

    Args:
        a: First matrix (m x p) as list of lists.
        b: Second matrix (p x n) as list of lists.

    Returns:
        Result matrix (m x n) as list of lists.

    Raises:
        ValueError: If matrix dimensions are incompatible.
    """
    m: int = len(a)
    if m == 0:
        return []
    p: int = len(a[0])
    if len(b) != p:
        raise ValueError(
            f"Matrix dimensions incompatible for multiplication: "
            f"A is {m}x{p}, B has {len(b)} rows"
        )
    n: int = len(b[0]) if p > 0 else 0

    result: List[List[float]] = [[0.0] * n for _ in range(m)]
    for i in range(m):
        for j in range(n):
            total: float = 0.0
            for k in range(p):
                total += a[i][k] * b[k][j]
            result[i][j] = total

    return result


def matrix_vector_multiply(
    matrix: List[List[float]],
    vector: List[float],
) -> List[float]:
    """Multiply a matrix by a column vector.

    Args:
        matrix: N x N matrix as list of lists.
        vector: N-length vector as list.

    Returns:
        N-length result vector as list.
    """
    n: int = len(matrix)
    result: List[float] = [0.0] * n
    for i in range(n):
        total: float = 0.0
        for j in range(n):
            total += matrix[i][j] * vector[j]
        result[i] = total
    return result


def solve_linear_system(
    a_matrix: List[List[float]],
    b_vector: List[float],
) -> List[float]:
    """Solve the linear system Ax = b via Gaussian elimination with partial pivoting.

    Implements standard Gaussian elimination with row swaps for numerical
    stability. The algorithm is O(n^3) and suitable for the small systems
    (typically N < 20 agents) used in Gaia ecosystems.

    Args:
        a_matrix: N x N coefficient matrix as list of lists. NOT modified in place.
        b_vector: N-length right-hand-side vector. NOT modified in place.

    Returns:
        N-length solution vector x such that Ax = b.

    Raises:
        ValueError: If the matrix is singular or dimensions are incompatible.
    """
    n: int = len(a_matrix)
    if n == 0:
        return []
    return solve_linear_systems(a_matrix, [b_vector])[0]


def solve_linear_systems(
    a_matrix: List[List[float]],
    b_vectors: List[List[float]],
) -> List[List[float]]:
    """Solve Ax = b for several right-hand sides with one elimination.

    The same Gaussian elimination with partial pivoting as
    solve_linear_system, run once on A with every b appended as an extra
    column of the augmented matrix. The pivots depend on A only and each
    right-hand-side column goes through exactly the operations a separate
    solve would apply, so every solution is bit-for-bit the one
    solve_linear_system(a_matrix, b) gives, at the cost of a single
    factorisation (decision D7 profiling: the price solve used to repeat
    it n + 1 times per step).

    Args:
        a_matrix: N x N coefficient matrix. NOT modified in place.
        b_vectors: Right-hand sides, each N-length. NOT modified in place.

    Returns:
        One N-length solution per right-hand side, in order.

    Raises:
        ValueError: If the matrix is singular or dimensions are incompatible.
    """
    n: int = len(a_matrix)
    m: int = len(b_vectors)
    if n == 0:
        return [[] for _ in range(m)]
    for b_vector in b_vectors:
        if len(b_vector) != n:
            raise ValueError(
                f"Dimension mismatch: matrix is {n}x{n}, vector has {len(b_vector)} elements"
            )
    width: int = n + m

    # Augmented matrix [A | b_1 ... b_m] — deep copy to avoid mutation
    aug: List[List[float]] = []
    for i in range(n):
        row: List[float] = []
        for j in range(n):
            row.append(a_matrix[i][j])
        for k in range(m):
            row.append(b_vectors[k][i])
        aug.append(row)

    # Forward elimination with partial pivoting
    for col in range(n):
        # Find pivot row (largest absolute value in column)
        max_val: float = abs(aug[col][col])
        max_row: int = col
        for r in range(col + 1, n):
            val: float = abs(aug[r][col])
            if val > max_val:
                max_val = val
                max_row = r

        if max_val < 1e-15:
            raise ValueError(
                f"Matrix is singular or near-singular at column {col} "
                f"(pivot magnitude {max_val:.2e})"
            )

        # Swap rows if needed
        if max_row != col:
            aug[col], aug[max_row] = aug[max_row], aug[col]

        # Eliminate below
        pivot: float = aug[col][col]
        pivot_row: List[float] = aug[col]
        for r in range(col + 1, n):
            target: List[float] = aug[r]
            factor: float = target[col] / pivot
            for j in range(col, width):
                target[j] -= factor * pivot_row[j]

    # Back substitution, one right-hand side at a time
    solutions: List[List[float]] = []
    for k in range(m):
        rhs: int = n + k
        x: List[float] = [0.0] * n
        for i in range(n - 1, -1, -1):
            total: float = aug[i][rhs]
            for j in range(i + 1, n):
                total -= aug[i][j] * x[j]
            x[i] = total / aug[i][i]
        solutions.append(x)
    return solutions


# ── Convergence certificates ────────────────────────────────────────────────

# A certified bound must clear 1 by this margin, so rounding in the bound
# itself cannot turn a borderline system into an accepted one.
_CERTIFICATE_MARGIN: float = 1e-9


class PricingConvergenceError(ValueError):
    """The price system has no certified convergent solution at this state.

    Raised instead of substituting any other price (C8): endogenous pricing
    is experimental (decision D4), and a state at which the Neumann series
    I + SW + (SW)² + ... cannot be shown to converge has no valid price, so
    no euro figure is produced for it. A ValueError, so the case CLIs report
    it as an error.

    Attributes:
        spectral_radius_bound: Best guaranteed upper bound on ρ(S·W) found
            (>= 1, or None when the failure is not about convergence).
        step: Extraction step at which pricing failed (set by run_extraction).
        depletion_ratio: Depletion at that step (set by run_extraction).
    """

    def __init__(
        self,
        message: str,
        spectral_radius_bound: Optional[float] = None,
        step: Optional[int] = None,
        depletion_ratio: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.spectral_radius_bound = spectral_radius_bound
        self.step = step
        self.depletion_ratio = depletion_ratio


def spectral_radius_bound(matrix: List[List[float]]) -> float:
    """Guaranteed upper bound on the spectral radius of a square matrix.

    ρ(M) <= min(max_i Σ_j |M[i][j]|, max_j Σ_i |M[i][j]|): the maximum
    absolute row sum is the ∞-norm and the maximum absolute column sum the
    1-norm, and every induced norm bounds the spectral radius. For the
    non-negative S·W these are its row and column sums. A bound < 1
    guarantees that the Neumann series converges. Unlike a power-iteration
    estimate (which underestimated ρ for non-symmetric S·W, C8), it can
    only overestimate.

    Returns:
        The bound (0.0 for an empty matrix).
    """
    n: int = len(matrix)
    if n == 0:
        return 0.0
    max_row: float = 0.0
    col_sums: List[float] = [0.0] * n
    for i in range(n):
        row_sum: float = 0.0
        for j in range(n):
            entry: float = abs(matrix[i][j])
            row_sum += entry
            col_sums[j] += entry
        if row_sum > max_row:
            max_row = row_sum
    return min(max_row, max(col_sums))


def collatz_wielandt_bounds(
    matrix: List[List[float]],
    x: List[float],
) -> Tuple[float, float]:
    """Lower and upper bounds on ρ(M) from a positive vector x.

    For a non-negative M and any x with every x_i > 0 (Collatz–Wielandt):

        min_i (M·x)_i / x_i  <=  ρ(M)  <=  max_i (M·x)_i / x_i

    The upper bound is the ∞-norm of diag(x)⁻¹·M·diag(x), which is similar
    to M; the lower bound follows from M^k·x >= c^k·x. Both are guaranteed,
    not estimates.

    Args:
        matrix: N x N non-negative matrix.
        x: N-length vector with every entry > 0.

    Returns:
        (lower, upper).
    """
    mx: List[float] = matrix_vector_multiply(matrix, x)
    ratios: List[float] = [mx[i] / x[i] for i in range(len(x))]
    return min(ratios), max(ratios)


# Power-iterate entries below this (relative to its maximum) are treated as
# outside its support by _support_lower_bound, and the iterate is floored at
# _MIN_ITERATE so that it stays strictly positive.
_SUPPORT_THRESHOLD: float = 1e-6
_MIN_ITERATE: float = 1e-300


def _support_lower_bound(matrix: List[List[float]], u: List[float]) -> float:
    """Guaranteed lower bound on ρ(M) from the significant part of u.

    x = u restricted to J = {i : u_i >= _SUPPORT_THRESHOLD · max(u)}, zero
    elsewhere. If (M·x)_i >= c·x_i for every i in J, then M·x >= c·x
    (x >= 0, x != 0), so M^k·x >= c^k·x and ρ(M) >= c. Restricting to the
    support matters for reducible S·W: an agent that depends on nothing has
    a zero row, and its ratio (0) would otherwise pin the plain
    Collatz–Wielandt lower bound at 0.
    """
    n: int = len(u)
    cutoff: float = _SUPPORT_THRESHOLD * max(u)
    x: List[float] = [u[i] if u[i] >= cutoff else 0.0 for i in range(n)]
    mx: List[float] = matrix_vector_multiply(matrix, x)
    return min(mx[i] / x[i] for i in range(n) if x[i] > 0.0)


def certify_convergence(
    sw_matrix: List[List[float]],
    b_vector: List[float],
    max_iterations: int,
) -> Tuple[str, float, int]:
    """Prove that ρ(S·W) < 1, so that V = S·W·V + S·A has a convergent solution.

    1. Norm bound: if min(max row sum, max column sum) of S·W is below 1,
       convergence is guaranteed ("norm_bound").
    2. Direct iteration otherwise ("direct_iteration"): V_0 = b,
       V_{k+1} = S·W·V_k + b with b = S·A, alongside a power iterate
       u_{k+1} = (S·W + I)·u_k (normalised; the shift keeps it positive and
       aperiodic, and it tends to the Perron vector of S·W). Both stay
       positive (b > 0: every agent is anchored), so each gives
       Collatz–Wielandt bounds on ρ(S·W) at every iteration:
         - an upper bound < 1 proves convergence. With x = V_k it also bounds
           the residual: V_{k+1} − V_k shrinks geometrically, by at least
           that factor per iteration in the V_k-weighted max norm.
         - a lower bound >= 1 (from the support of u, _support_lower_bound)
           proves divergence (the series grows without bound).
       If neither settles it within ``max_iterations`` the state fails:
       convergence is never assumed.

    Args:
        sw_matrix: N x N non-negative matrix S·W.
        b_vector: N-length vector S·A, every entry > 0.
        max_iterations: Cap on direct iterations.

    Returns:
        (method, bound, iterations): the method that certified convergence,
        the guaranteed bound on ρ(S·W) (< 1) and the iterations used.

    Raises:
        PricingConvergenceError: If ρ(S·W) >= 1 is proven, or convergence
            cannot be proven within max_iterations.
    """
    limit: float = 1.0 - _CERTIFICATE_MARGIN
    norm_bound: float = spectral_radius_bound(sw_matrix)
    if norm_bound < limit:
        return "norm_bound", norm_bound, 0

    n: int = len(sw_matrix)
    best_upper: float = norm_bound
    v: List[float] = list(b_vector)
    u: List[float] = [1.0] * n
    for iteration in range(1, max_iterations + 1):
        swv: List[float] = matrix_vector_multiply(sw_matrix, v)
        swu: List[float] = matrix_vector_multiply(sw_matrix, u)
        upper: float = min(
            max(swv[i] / v[i] for i in range(n)),
            max(swu[i] / u[i] for i in range(n)),
        )
        lower: float = _support_lower_bound(sw_matrix, u)
        best_upper = min(best_upper, upper)
        if upper < limit:
            return "direct_iteration", upper, iteration
        if lower >= 1.0:
            raise PricingConvergenceError(
                f"ρ(S·W) >= {lower:.4f} (Collatz–Wielandt lower bound after "
                f"{iteration} direct iterations), so the price series "
                f"diverges.",
                spectral_radius_bound=best_upper,
            )
        v = [swv[i] + b_vector[i] for i in range(n)]
        u = [swu[i] + u[i] for i in range(n)]
        u_max: float = max(u)
        u = [max(x / u_max, _MIN_ITERATE) for x in u]
    raise PricingConvergenceError(
        f"convergence of the price series could not be proven: the best "
        f"guaranteed bound on ρ(S·W) is {best_upper:.4f} >= 1 (row/column "
        f"sum bound {norm_bound:.4f}; {max_iterations} direct iterations).",
        spectral_radius_bound=best_upper,
    )


# ── Matrix helper functions ─────────────────────────────────────────────────


def _identity_matrix(n: int) -> List[List[float]]:
    """Create an N x N identity matrix."""
    matrix: List[List[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        matrix[i][i] = 1.0
    return matrix


def _matrix_subtract(
    a: List[List[float]],
    b: List[List[float]],
) -> List[List[float]]:
    """Compute A - B for two same-sized matrices."""
    n: int = len(a)
    result: List[List[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            result[i][j] = a[i][j] - b[i][j]
    return result


# ── Price solver ────────────────────────────────────────────────────────────


def solve_prices(
    agent_names: List[str],
    agent_healths: Dict[str, float],
    interactions: List[InteractionEdge],
    pricing: PricingConfig,
) -> PriceResult:
    """Solve the Leontief-Hannon price system for the current ecosystem state.

    EXPERIMENTAL (decision D4): the formulation still counts upstream value
    once per dependent agent and prices the whole loss at the end-state
    price (C8, to be revisited).

    The algorithm:

    1. Build the scarcity matrix S (diagonal, health-dependent).
    2. Build the value-flow matrix W (from interaction edges, transposed).
    3. Build the anchor vector A. Every agent must be anchored (A > 0).
    4. Compute SW = S @ W and certify ρ(SW) < 1 (certify_convergence):
       a guaranteed bound, never an estimate.
    5. Solve V = (I - SW)^(-1) * S * A via Gaussian elimination.
    6. Decompose prices into scarcity, demand, and anchor contributions.

    There is no fallback: when convergence cannot be proven, or the solve
    yields a non-positive price (impossible for a convergent series with
    S·A > 0, so a sign of an invalid solve), PricingConvergenceError is
    raised. No other price is substituted and no price is clamped.

    The decomposition of each agent's price:
        scarcity_multiplier = S[i][i] (the health-dependent premium)
        demand_multiplier = row sum of (I - SW)^(-1) (network centrality)
        anchor_contribution = fraction of price from direct anchor vs network

    Args:
        agent_names: Ordered list of agent names.
        agent_healths: Health fraction per agent (0.0 to 1.0).
        interactions: List of InteractionEdge defining the value network.
        pricing: PricingConfig with anchors, scarcity functions, solver params.

    Returns:
        PriceResult with computed prices, full decomposition and the
        convergence certificate.

    Raises:
        ValueError: If an agent has no anchor, or S·W has a negative entry.
        PricingConvergenceError: If convergence cannot be proven or the
            solve is invalid.
    """
    n: int = len(agent_names)

    # Degenerate case: no agents
    if n == 0:
        return PriceResult(
            prices={},
            scarcity_multipliers={},
            demand_multipliers={},
            anchor_contributions={},
            spectral_radius_bound=0.0,
            convergence_check="norm_bound",
            iterations=0,
        )

    # Step 1: Build matrices
    s_matrix: List[List[float]] = build_scarcity_matrix(
        agent_names, agent_healths, pricing
    )
    w_matrix: List[List[float]] = build_value_matrix(agent_names, interactions)
    a_vector: List[float] = build_anchor_vector(agent_names, pricing.anchors)

    unanchored: List[str] = [
        agent_names[i] for i in range(n) if not a_vector[i] > 0.0
    ]
    if unanchored:
        raise ValueError(
            f"Every agent must be anchored when pricing is on; no positive "
            f"anchor for: {unanchored}"
        )

    # Step 2: Compute SW = S @ W. S is diagonal, so SW scales row i of W
    # by S[i][i]: the same numbers as matrix_multiply (whose other terms are
    # 0.0 × w), without its O(n³) loop.
    sw_matrix: List[List[float]] = [
        [s_matrix[i][i] * w_matrix[i][j] for j in range(n)] for i in range(n)
    ]
    for i in range(n):
        for j in range(n):
            if sw_matrix[i][j] < 0.0:
                raise ValueError(
                    f"S·W must be non-negative, got {sw_matrix[i][j]} at "
                    f"({agent_names[i]!r}, {agent_names[j]!r})"
                )

    # Effective anchor b = S * A (every entry > 0)
    effective_anchor: List[float] = [s_matrix[i][i] * a_vector[i] for i in range(n)]

    # Step 3: Certify convergence (raises PricingConvergenceError)
    method, bound, iterations_used = certify_convergence(
        sw_matrix, effective_anchor, pricing.max_iterations
    )

    # Step 4: Solve V = (I - SW)^(-1) * S * A
    identity: List[List[float]] = _identity_matrix(n)
    i_minus_sw: List[List[float]] = _matrix_subtract(identity, sw_matrix)

    # One elimination for the prices and the columns of (I - SW)^(-1)
    # (the demand multipliers below), instead of n + 1.
    unit_columns: List[List[float]] = [
        [1.0 if row == col else 0.0 for row in range(n)] for col in range(n)
    ]
    try:
        solutions: List[List[float]] = solve_linear_systems(
            i_minus_sw, [effective_anchor] + unit_columns
        )
    except ValueError as exc:
        raise PricingConvergenceError(
            f"the price system is singular although ρ(S·W) <= {bound:.4f} ({exc}).",
        ) from exc
    v_vector: List[float] = solutions[0]

    # Step 5: Check the solve. V = Σ (SW)^k S·A >= S·A > 0, so a
    # non-positive price, or a large residual, means the solve is invalid.
    non_positive: List[str] = [
        agent_names[i] for i in range(n) if not v_vector[i] > 0.0
    ]
    if non_positive:
        raise PricingConvergenceError(
            f"the price solve gave non-positive prices for {non_positive}; "
            f"prices are never clamped.",
        )
    residual_vector: List[float] = matrix_vector_multiply(i_minus_sw, v_vector)
    scale: float = max(abs(x) for x in effective_anchor)
    residual: float = max(
        abs(residual_vector[i] - effective_anchor[i]) for i in range(n)
    )
    if residual > pricing.convergence_tolerance * scale:
        raise PricingConvergenceError(
            f"the price solve is inaccurate: residual {residual:.3e} exceeds "
            f"convergence_tolerance × max(S·A) = "
            f"{pricing.convergence_tolerance * scale:.3e}.",
        )

    # Step 6: Decompose prices
    prices: Dict[str, float] = {}
    scarcity_multipliers: Dict[str, float] = {}
    demand_multipliers: Dict[str, float] = {}
    anchor_contributions: Dict[str, float] = {}

    # (I - SW)^(-1) row sums for demand multipliers, from its columns
    inverse_rows: List[List[float]] = [[0.0] * n for _ in range(n)]
    for col in range(n):
        inv_col: List[float] = solutions[1 + col]
        for row in range(n):
            inverse_rows[row][col] = inv_col[row]

    for i in range(n):
        name: str = agent_names[i]
        prices[name] = v_vector[i]
        scarcity_multipliers[name] = s_matrix[i][i]

        # Demand multiplier: row sum of (I - SW)^(-1)
        row_sum: float = 0.0
        for j in range(n):
            row_sum += inverse_rows[i][j]
        demand_multipliers[name] = row_sum

        # Anchor contribution: fraction of price from direct anchor
        anchor_contributions[name] = effective_anchor[i] / v_vector[i]

    return PriceResult(
        prices=prices,
        scarcity_multipliers=scarcity_multipliers,
        demand_multipliers=demand_multipliers,
        anchor_contributions=anchor_contributions,
        spectral_radius_bound=bound,
        convergence_check=method,
        iterations=iterations_used,
    )
