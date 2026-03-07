"""
Gaia v0.7 -- Endogenous pricing engine.

Implements a Leontief-Hannon input-output pricing model for ecosystem services.
Prices emerge endogenously from network structure, scarcity, and anchor values
rather than being fixed exogenously as static monetary rates.

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
I + SW + (SW)^2 + ... converges. When this condition fails, we either cap
scarcity multipliers to enforce convergence or fall back to static pricing.

All functions use primitive types (no numpy) for Cython compatibility.
No third-party dependencies.

Scientific references:
    - Leontief W (1970) Environmental repercussions and the economic structure.
    - Hannon B (1973) The structure of ecosystems. J Theor Biol.
    - Costanza R et al. (1997) The value of the world's ecosystem services.
    - de Groot R et al. (2012) Global estimates of the value of ecosystems.
"""

from typing import Dict, List, Optional, Tuple

from gaia.models import (
    AnchorPoint,
    InteractionEdge,
    PriceResult,
    PricingConfig,
    ScarcityFunction,
)


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
    without anchors get 0.0 — their prices are determined entirely by
    network effects from anchored agents.

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


# ── Linear algebra primitives (pure Python, Cython-compatible) ──────────────


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
    if len(b_vector) != n:
        raise ValueError(
            f"Dimension mismatch: matrix is {n}x{n}, vector has {len(b_vector)} elements"
        )

    # Create augmented matrix [A | b] — deep copy to avoid mutation
    aug: List[List[float]] = []
    for i in range(n):
        row: List[float] = []
        for j in range(n):
            row.append(a_matrix[i][j])
        row.append(b_vector[i])
        aug.append(row)

    # Forward elimination with partial pivoting
    for col in range(n):
        # Find pivot row (largest absolute value in column)
        max_val: float = abs(aug[col][col])
        max_row: int = col
        for row in range(col + 1, n):
            val: float = abs(aug[row][col])
            if val > max_val:
                max_val = val
                max_row = row

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
        for row in range(col + 1, n):
            factor: float = aug[row][col] / pivot
            for j in range(col, n + 1):
                aug[row][j] -= factor * aug[col][j]

    # Back substitution
    x: List[float] = [0.0] * n
    for i in range(n - 1, -1, -1):
        total: float = aug[i][n]
        for j in range(i + 1, n):
            total -= aug[i][j] * x[j]
        x[i] = total / aug[i][i]

    return x


# ── Eigenvalue estimation ───────────────────────────────────────────────────


def compute_spectral_radius(
    matrix: List[List[float]],
    max_iterations: int = 20,
) -> float:
    """Estimate the spectral radius (largest absolute eigenvalue) via power iteration.

    Uses the power method to find the dominant eigenvalue magnitude. For the
    Leontief price system, spectral_radius(SW) < 1.0 is the convergence
    condition (the Hawkins-Simon condition).

    Power iteration converges linearly with ratio |lambda_2/lambda_1|. For
    typical ecosystem matrices, 20 iterations provides excellent accuracy.

    The method handles both positive and negative dominant eigenvalues by
    tracking the Rayleigh quotient (v^T * A * v) / (v^T * v).

    Args:
        matrix: N x N square matrix as list of lists.
        max_iterations: Number of power iteration steps (default 20).

    Returns:
        Estimated spectral radius (non-negative). Returns 0.0 for zero or
        empty matrices.
    """
    n: int = len(matrix)
    if n == 0:
        return 0.0

    # Check for zero matrix
    all_zero: bool = True
    for i in range(n):
        for j in range(n):
            if abs(matrix[i][j]) > 1e-15:
                all_zero = False
                break
        if not all_zero:
            break
    if all_zero:
        return 0.0

    # Initialize with unit vector [1, 1, ..., 1] normalized
    v: List[float] = [1.0] * n
    norm: float = n ** 0.5
    for i in range(n):
        v[i] /= norm

    eigenvalue: float = 0.0

    for _ in range(max_iterations):
        # w = matrix * v
        w: List[float] = [0.0] * n
        for i in range(n):
            total: float = 0.0
            for j in range(n):
                total += matrix[i][j] * v[j]
            w[i] = total

        # Compute Rayleigh quotient: eigenvalue = (v^T * w) / (v^T * v)
        numerator: float = 0.0
        denominator: float = 0.0
        for i in range(n):
            numerator += v[i] * w[i]
            denominator += v[i] * v[i]
        if denominator > 1e-30:
            eigenvalue = numerator / denominator

        # Normalize w to get next v
        w_norm: float = 0.0
        for i in range(n):
            w_norm += w[i] * w[i]
        w_norm = w_norm ** 0.5

        if w_norm < 1e-15:
            # Matrix maps everything to near-zero
            return abs(eigenvalue)

        for i in range(n):
            v[i] = w[i] / w_norm

    return abs(eigenvalue)


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
    monetary_rates: Dict[str, float],
) -> PriceResult:
    """Solve the Leontief-Hannon price system for the current ecosystem state.

    Computes endogenous prices that reflect both intrinsic anchor values and
    network-propagated scarcity. The algorithm:

    1. Build the scarcity matrix S (diagonal, health-dependent).
    2. Build the value-flow matrix W (from interaction edges, transposed).
    3. Build the anchor vector A (from market price anchors).
    4. Compute SW = S @ W (the technical coefficients matrix).
    5. Compute spectral_radius(SW) to check convergence.
    6. If spectral_radius >= 1.0:
       a. If fallback_to_static: return static monetary_rates.
       b. Else: scale down scarcity multipliers until spectral_radius < 0.95.
    7. Solve V = (I - SW)^(-1) * S * A via Gaussian elimination.
    8. Decompose prices into scarcity, demand, and anchor contributions.

    The decomposition of each agent's price:
        scarcity_multiplier = S[i][i] (the health-dependent premium)
        demand_multiplier = row sum of (I - SW)^(-1) (network centrality)
        anchor_contribution = fraction of price from direct anchor vs network

    Args:
        agent_names: Ordered list of agent names.
        agent_healths: Health fraction per agent (0.0 to 1.0).
        interactions: List of InteractionEdge defining the value network.
        pricing: PricingConfig with anchors, scarcity functions, solver params.
        monetary_rates: Fallback static prices per agent (from Agent.monetary_rate).

    Returns:
        PriceResult with computed prices and full decomposition.
    """
    n: int = len(agent_names)

    # Degenerate case: no agents
    if n == 0:
        return PriceResult(
            prices={},
            scarcity_multipliers={},
            demand_multipliers={},
            anchor_contributions={},
            spectral_radius=0.0,
            converged=True,
            iterations=0,
        )

    # Step 1: Build matrices
    s_matrix: List[List[float]] = build_scarcity_matrix(
        agent_names, agent_healths, pricing
    )
    w_matrix: List[List[float]] = build_value_matrix(agent_names, interactions)
    a_vector: List[float] = build_anchor_vector(agent_names, pricing.anchors)

    # Step 2: Compute SW = S @ W
    sw_matrix: List[List[float]] = matrix_multiply(s_matrix, w_matrix)

    # Step 3: Check spectral radius for convergence
    radius: float = compute_spectral_radius(sw_matrix)
    iterations_used: int = 0

    # Step 4: Handle convergence failure
    if radius >= 1.0:
        if pricing.fallback_to_static:
            # Return static prices with converged=False
            scarcity_mults: Dict[str, float] = {}
            for i in range(n):
                scarcity_mults[agent_names[i]] = s_matrix[i][i]
            return PriceResult(
                prices=dict(monetary_rates),
                scarcity_multipliers=scarcity_mults,
                demand_multipliers={name: 1.0 for name in agent_names},
                anchor_contributions={name: 0.0 for name in agent_names},
                spectral_radius=radius,
                converged=False,
                iterations=0,
            )
        else:
            # Scale down scarcity multipliers until spectral_radius < 0.95
            target_radius: float = 0.95
            # Binary search for the right scaling factor
            scale_lo: float = 0.0
            scale_hi: float = 1.0
            scale: float = 1.0

            for iteration in range(pricing.max_iterations):
                iterations_used = iteration + 1
                scale = (scale_lo + scale_hi) / 2.0

                # Build scaled scarcity matrix
                scaled_s: List[List[float]] = [[0.0] * n for _ in range(n)]
                for i in range(n):
                    # Interpolate between 1.0 (no scarcity) and full scarcity
                    scaled_s[i][i] = 1.0 + scale * (s_matrix[i][i] - 1.0)

                scaled_sw: List[List[float]] = matrix_multiply(scaled_s, w_matrix)
                scaled_radius: float = compute_spectral_radius(scaled_sw)

                if abs(scaled_radius - target_radius) < pricing.convergence_tolerance:
                    sw_matrix = scaled_sw
                    s_matrix = scaled_s
                    radius = scaled_radius
                    break
                elif scaled_radius > target_radius:
                    scale_hi = scale
                else:
                    scale_lo = scale

                sw_matrix = scaled_sw
                s_matrix = scaled_s
                radius = scaled_radius

    # Step 5: Solve V = (I - SW)^(-1) * S * A
    identity: List[List[float]] = _identity_matrix(n)
    i_minus_sw: List[List[float]] = _matrix_subtract(identity, sw_matrix)

    # Apply scarcity to anchor vector: effective_anchor = S * A
    effective_anchor: List[float] = [0.0] * n
    for i in range(n):
        effective_anchor[i] = s_matrix[i][i] * a_vector[i]

    try:
        v_vector: List[float] = solve_linear_system(i_minus_sw, effective_anchor)
        converged: bool = True
    except ValueError:
        # Singular matrix — fall back to static prices
        v_vector = [monetary_rates.get(agent_names[i], 0.0) for i in range(n)]
        converged = False

    # Step 6: Ensure non-negative prices (clamp to zero)
    for i in range(n):
        if v_vector[i] < 0.0:
            v_vector[i] = 0.0

    # Step 7: Decompose prices
    prices: Dict[str, float] = {}
    scarcity_multipliers: Dict[str, float] = {}
    demand_multipliers: Dict[str, float] = {}
    anchor_contributions: Dict[str, float] = {}

    # Compute (I - SW)^(-1) row sums for demand multipliers
    # We already have (I - SW); compute its inverse by solving N systems
    inverse_rows: List[List[float]] = [[0.0] * n for _ in range(n)]
    if converged:
        for col in range(n):
            e_col: List[float] = [0.0] * n
            e_col[col] = 1.0
            try:
                inv_col: List[float] = solve_linear_system(i_minus_sw, e_col)
                for row in range(n):
                    inverse_rows[row][col] = inv_col[row]
            except ValueError:
                # If inversion fails for any column, set identity
                inverse_rows[col][col] = 1.0

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
        if v_vector[i] > 1e-15 and a_vector[i] > 0.0:
            anchor_contributions[name] = (
                s_matrix[i][i] * a_vector[i]
            ) / v_vector[i]
        else:
            anchor_contributions[name] = 0.0

    return PriceResult(
        prices=prices,
        scarcity_multipliers=scarcity_multipliers,
        demand_multipliers=demand_multipliers,
        anchor_contributions=anchor_contributions,
        spectral_radius=radius,
        converged=converged,
        iterations=iterations_used,
    )
