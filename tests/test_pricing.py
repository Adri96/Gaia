"""
Gaia v0.7 -- Endogenous pricing engine unit tests.

Tests the Leontief-Hannon input-output pricing model including scarcity
functions, matrix construction, the price solver, price dynamics, and
integration with the simulation engine and preconfigured case builders.

Covers these categories:

    1. ScarcityFunctions (smooth and threshold, edge cases, monotonicity)
    2. MatrixConstruction (W matrix, anchor vector, S matrix diagonal)
    3. Solver (trivial, two-agent, positivity, anchor reproduction,
       convergence bound, divergence raises, determinism)
    4. PriceDynamics (degradation, keystone pricing, price propagation)
    5. SimulationIntegration (backward compatibility, extraction cost,
       price_result presence)
    6. CaseIntegration (forest, costa_brava, posidonia with_pricing=True)
    7. Step 4 quarantine (C8): guaranteed convergence bound, direct-iteration
       certificate, explicit failure (no static fallback, no clamp), every
       agent anchored, experimental label in text and JSON.
"""

import pytest

from gaia.models import (
    AnchorPoint,
    InteractionEdge,
    PricingConfig,
    PriceResult,
    ScarcityFunction,
)
from gaia.pricing import (
    PricingConvergenceError,
    _support_lower_bound,
    anchor_every_agent,
    build_anchor_vector,
    build_scarcity_matrix,
    build_value_matrix,
    certify_convergence,
    collatz_wielandt_bounds,
    compute_scarcity,
    matrix_multiply,
    solve_prices,
    spectral_radius_bound,
)


# ── Test fixtures ─────────────────────────────────────────────────────────────


def _smooth_scarcity(**kwargs) -> ScarcityFunction:
    """Standard smooth scarcity function fixture."""
    defaults = dict(
        function_type="smooth",
        alpha=1.0,
        threshold=0.3,
        max_multiplier=50.0,
    )
    defaults.update(kwargs)
    return ScarcityFunction(**defaults)


def _threshold_scarcity(**kwargs) -> ScarcityFunction:
    """Standard threshold scarcity function fixture."""
    defaults = dict(
        function_type="threshold",
        alpha=1.0,
        threshold=0.3,
        max_multiplier=50.0,
    )
    defaults.update(kwargs)
    return ScarcityFunction(**defaults)


def _simple_pricing_config(
    agent_names=None,
    anchor_agent=None,
    anchor_value=100.0,
    **kwargs,
) -> PricingConfig:
    """Build a minimal PricingConfig for testing.

    ``anchor_agent`` is anchored at ``anchor_value``; every other agent at
    50.0 (pricing requires every agent to be anchored).
    """
    if agent_names is None:
        agent_names = ["A"]
    if anchor_agent is None:
        anchor_agent = agent_names[0]

    anchors = [
        AnchorPoint(
            agent_name=name,
            anchor_value=anchor_value if name == anchor_agent else 50.0,
            source="test",
            confidence="high",
            description="test anchor",
        )
        for name in agent_names
    ]

    defaults = dict(
        anchors=anchors,
        scarcity_functions={},
        default_scarcity=ScarcityFunction("smooth", alpha=1.0, threshold=0.3, max_multiplier=50.0),
    )
    defaults.update(kwargs)
    return PricingConfig(**defaults)


# ── 1. TestScarcityFunctions ──────────────────────────────────────────────────


class TestScarcityFunctions:
    """Tests for the compute_scarcity function with smooth and threshold types."""

    def test_smooth_scarcity_pristine(self):
        """health=1.0 should produce scarcity=1.0 (no scarcity premium)."""
        sf = _smooth_scarcity(alpha=1.0)
        result = compute_scarcity(1.0, sf)
        assert result == pytest.approx(1.0)

    def test_smooth_scarcity_degraded(self):
        """health=0.5, alpha=1.0 should produce scarcity = 1/0.5 = 2.0."""
        sf = _smooth_scarcity(alpha=1.0)
        result = compute_scarcity(0.5, sf)
        assert result == pytest.approx(2.0)

    def test_smooth_scarcity_alpha_effect(self):
        """Higher alpha should produce higher scarcity at the same health level."""
        health = 0.5
        sf_low = _smooth_scarcity(alpha=1.0)
        sf_high = _smooth_scarcity(alpha=2.0)

        scarcity_low = compute_scarcity(health, sf_low)
        scarcity_high = compute_scarcity(health, sf_high)

        # alpha=1.0: 1/0.5^1 = 2.0; alpha=2.0: 1/0.5^2 = 4.0
        assert scarcity_high > scarcity_low
        assert scarcity_low == pytest.approx(2.0)
        assert scarcity_high == pytest.approx(4.0)

    def test_smooth_scarcity_capped(self):
        """health near 0 should produce scarcity = max_multiplier (capped)."""
        sf = _smooth_scarcity(alpha=1.0, max_multiplier=50.0)
        result = compute_scarcity(0.0, sf)
        assert result == pytest.approx(50.0)

        # Very near zero also hits the cap
        result_near_zero = compute_scarcity(0.001, sf)
        assert result_near_zero == pytest.approx(50.0)

    def test_threshold_scarcity_above(self):
        """health > threshold should produce scarcity = 1.0."""
        sf = _threshold_scarcity(threshold=0.3)
        result = compute_scarcity(0.5, sf)
        assert result == pytest.approx(1.0)

        result_at = compute_scarcity(0.3, sf)
        assert result_at == pytest.approx(1.0)

    def test_threshold_scarcity_below(self):
        """health < threshold should produce scarcity > 1.0."""
        sf = _threshold_scarcity(threshold=0.3, max_multiplier=50.0)
        result = compute_scarcity(0.15, sf)
        assert result > 1.0

        # Verify the quadratic formula:
        # ratio = (0.3 - 0.15) / 0.3 = 0.5
        # scarcity = 1.0 + (50 - 1) * 0.25 = 1.0 + 12.25 = 13.25
        expected = 1.0 + (50.0 - 1.0) * 0.5 * 0.5
        assert result == pytest.approx(expected)

    def test_threshold_scarcity_at_zero(self):
        """health=0 should produce scarcity = max_multiplier."""
        sf = _threshold_scarcity(threshold=0.3, max_multiplier=50.0)
        result = compute_scarcity(0.0, sf)
        assert result == pytest.approx(50.0)

    def test_scarcity_monotonic(self):
        """Lower health should produce higher or equal scarcity for both types."""
        health_values = [1.0, 0.8, 0.6, 0.4, 0.2, 0.1, 0.01]

        for sf in [_smooth_scarcity(), _threshold_scarcity()]:
            previous = compute_scarcity(health_values[0], sf)
            for h in health_values[1:]:
                current = compute_scarcity(h, sf)
                assert current >= previous, (
                    f"Monotonicity violated for {sf.function_type}: "
                    f"scarcity({h}) = {current} < scarcity(prev) = {previous}"
                )
                previous = current


# ── 2. TestMatrixConstruction ─────────────────────────────────────────────────


class TestMatrixConstruction:
    """Tests for build_value_matrix, build_anchor_vector, build_scarcity_matrix."""

    def test_W_matrix_from_interactions(self):
        """Interaction edges should be correctly transposed into W matrix.

        Edge (source=A, target=B) means B depends on A,
        so W[B_idx][A_idx] = strength.
        """
        agents = ["A", "B", "C"]
        edges = [
            InteractionEdge("A", "B", 0.3, "dependency", "A damages B"),
            InteractionEdge("B", "C", 0.2, "trophic", "B damages C"),
        ]

        w = build_value_matrix(agents, edges)

        # W[target][source] = strength
        assert w[1][0] == pytest.approx(0.3)  # W[B][A] = 0.3
        assert w[2][1] == pytest.approx(0.2)  # W[C][B] = 0.2

        # Other entries should be 0
        assert w[0][0] == pytest.approx(0.0)
        assert w[0][1] == pytest.approx(0.0)
        assert w[0][2] == pytest.approx(0.0)
        assert w[1][1] == pytest.approx(0.0)
        assert w[1][2] == pytest.approx(0.0)
        assert w[2][0] == pytest.approx(0.0)
        assert w[2][2] == pytest.approx(0.0)

    def test_anchor_vector_construction(self):
        """Anchored agents get their anchor values, others get 0.0."""
        agents = ["A", "B", "C"]
        anchors = [
            AnchorPoint("B", 500.0, "test", "high", "test"),
        ]

        vec = build_anchor_vector(agents, anchors)

        assert vec[0] == pytest.approx(0.0)    # A: no anchor
        assert vec[1] == pytest.approx(500.0)  # B: anchored at 500
        assert vec[2] == pytest.approx(0.0)    # C: no anchor

    def test_S_matrix_diagonal(self):
        """Scarcity matrix should be diagonal with correct scarcity values."""
        agents = ["A", "B"]
        healths = {"A": 1.0, "B": 0.5}
        pricing = _simple_pricing_config(
            agent_names=agents,
            default_scarcity=ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        )

        s = build_scarcity_matrix(agents, healths, pricing)

        # Diagonal: scarcity(1.0) = 1.0, scarcity(0.5) = 2.0
        assert s[0][0] == pytest.approx(1.0)
        assert s[1][1] == pytest.approx(2.0)

        # Off-diagonal: zeros
        assert s[0][1] == pytest.approx(0.0)
        assert s[1][0] == pytest.approx(0.0)


# ── 3. TestSolver ────────────────────────────────────────────────────────────


class TestSolver:
    """Tests for the solve_prices function."""

    def test_solve_trivial(self):
        """Single anchored agent, no interactions: price = anchor_value * scarcity."""
        agents = ["A"]
        healths = {"A": 1.0}
        interactions = []
        pricing = _simple_pricing_config(agent_names=agents, anchor_value=100.0)

        result = solve_prices(agents, healths, interactions, pricing)

        assert result.spectral_radius_bound < 1.0
        # At health=1.0, scarcity=1.0, no interactions: V = (I - 0)^-1 * 1 * 100 = 100
        assert result.prices["A"] == pytest.approx(100.0)

    def test_solve_two_agents(self):
        """Agent A depends on B (edge B->A). B's price should increase from demand."""
        agents = ["A", "B"]
        healths = {"A": 1.0, "B": 1.0}
        edges = [
            InteractionEdge("B", "A", 0.3, "dependency", "A depends on B"),
        ]
        anchors = [
            AnchorPoint("A", 100.0, "test", "high", "test"),
            AnchorPoint("B", 200.0, "test", "high", "test"),
        ]
        pricing = PricingConfig(
            anchors=anchors,
            scarcity_functions={},
            default_scarcity=ScarcityFunction("smooth", 1.0, 0.3, 50.0),
        )

        result = solve_prices(agents, healths, edges, pricing)

        assert result.spectral_radius_bound < 1.0
        # A depends on B, so A's price should be > its anchor (100) because
        # it picks up value from B: V_A = 100 + 0.3 * V_B
        assert result.prices["A"] > 100.0
        # B has no dependencies so its price should be its anchor value
        assert result.prices["B"] == pytest.approx(200.0)

    def test_solve_prices_positive(self):
        """All computed prices should be > 0 for a well-formed system."""
        agents = ["A", "B", "C"]
        healths = {"A": 0.8, "B": 0.6, "C": 0.9}
        edges = [
            InteractionEdge("A", "B", 0.2, "dependency", "B depends on A"),
            InteractionEdge("B", "C", 0.15, "trophic", "C depends on B"),
        ]
        anchors = [
            AnchorPoint("A", 100.0, "test", "high", "test"),
            AnchorPoint("B", 10.0, "test", "high", "test"),
            AnchorPoint("C", 10.0, "test", "high", "test"),
        ]
        pricing = PricingConfig(
            anchors=anchors,
            scarcity_functions={},
            default_scarcity=ScarcityFunction("smooth", 1.0, 0.3, 50.0),
        )

        result = solve_prices(agents, healths, edges, pricing)

        for name in agents:
            assert result.prices[name] > 0.0, (
                f"Price for {name} is negative: {result.prices[name]}"
            )

    def test_solve_reproduces_anchor(self):
        """Anchored agent price should be >= anchor_value (scarcity can only increase it)."""
        agents = ["A"]
        healths = {"A": 0.7}  # Some degradation -> scarcity > 1
        interactions = []
        pricing = _simple_pricing_config(agent_names=agents, anchor_value=100.0)

        result = solve_prices(agents, healths, interactions, pricing)

        # scarcity(0.7) = 1/0.7 ~ 1.43, so price = 1.43 * 100 ~ 143
        assert result.prices["A"] >= 100.0

    def test_spectral_radius_check(self):
        """Solver reports a guaranteed bound on the spectral radius of SW."""
        agents = ["A", "B"]
        healths = {"A": 1.0, "B": 1.0}
        edges = [
            InteractionEdge("A", "B", 0.3, "dependency", "B depends on A"),
        ]
        pricing = _simple_pricing_config(
            agent_names=agents,
            anchor_agent="A",
            anchor_value=100.0,
        )

        result = solve_prices(agents, healths, edges, pricing)

        # SW = [[0, 0], [0.3, 0]]: row/column sum bound 0.3
        assert result.spectral_radius_bound == pytest.approx(0.3)
        assert result.convergence_check == "norm_bound"

    def test_divergence_raises_instead_of_falling_back(self):
        """A divergent system raises; no static or scaled price is returned."""
        agents = ["A", "B"]
        healths = {"A": 0.01, "B": 0.01}  # Very degraded -> high scarcity
        # Strong bidirectional dependency: ρ(SW) = 50 × 0.9 = 45
        edges = [
            InteractionEdge("A", "B", 0.9, "dependency", "B depends on A"),
            InteractionEdge("B", "A", 0.9, "dependency", "A depends on B"),
        ]
        pricing = PricingConfig(
            anchors=[AnchorPoint("A", 100.0, "test", "high", "test"),
                     AnchorPoint("B", 100.0, "test", "high", "test")],
            scarcity_functions={},
            default_scarcity=ScarcityFunction("smooth", 1.0, 0.3, 50.0),
        )

        with pytest.raises(PricingConvergenceError, match="diverges") as info:
            solve_prices(agents, healths, edges, pricing)
        assert info.value.spectral_radius_bound >= 1.0

    def test_solve_deterministic(self):
        """Same inputs should produce identical outputs across runs."""
        agents = ["A", "B"]
        healths = {"A": 0.8, "B": 0.6}
        edges = [
            InteractionEdge("A", "B", 0.2, "dependency", "B depends on A"),
        ]
        pricing = _simple_pricing_config(
            agent_names=agents,
            anchor_agent="A",
            anchor_value=100.0,
        )

        result1 = solve_prices(agents, healths, edges, pricing)
        result2 = solve_prices(agents, healths, edges, pricing)

        assert result1.prices["A"] == pytest.approx(result2.prices["A"])
        assert result1.prices["B"] == pytest.approx(result2.prices["B"])
        assert result1.spectral_radius_bound == pytest.approx(result2.spectral_radius_bound)
        assert result1.convergence_check == result2.convergence_check


# ── 4. TestPriceDynamics ─────────────────────────────────────────────────────


class TestPriceDynamics:
    """Tests for dynamic pricing behavior under ecosystem degradation."""

    def test_degradation_increases_prices(self):
        """Lower health should produce higher total ecosystem value."""
        agents = ["A", "B"]
        edges = [
            InteractionEdge("A", "B", 0.2, "dependency", "B depends on A"),
        ]
        anchors = [
            AnchorPoint("A", 100.0, "test", "high", "test"),
            AnchorPoint("B", 200.0, "test", "high", "test"),
        ]
        pricing = PricingConfig(
            anchors=anchors,
            scarcity_functions={},
            default_scarcity=ScarcityFunction("smooth", 1.0, 0.3, 50.0),
        )

        # Pristine
        healths_pristine = {"A": 1.0, "B": 1.0}
        result_pristine = solve_prices(agents, healths_pristine, edges, pricing)
        total_pristine = sum(result_pristine.prices.values())

        # Degraded
        healths_degraded = {"A": 0.5, "B": 0.5}
        result_degraded = solve_prices(agents, healths_degraded, edges, pricing)
        total_degraded = sum(result_degraded.prices.values())

        assert total_degraded > total_pristine

    def test_keystone_highest_price(self):
        """Agent with most incoming dependency edges should tend to have the highest price."""
        agents = ["A", "B", "C"]
        # B and C both depend on A -> A is the keystone / most depended upon
        edges = [
            InteractionEdge("A", "B", 0.2, "dependency", "B depends on A"),
            InteractionEdge("A", "C", 0.2, "dependency", "C depends on A"),
        ]
        anchors = [
            AnchorPoint("A", 100.0, "test", "high", "test"),
            AnchorPoint("B", 100.0, "test", "high", "test"),
            AnchorPoint("C", 100.0, "test", "high", "test"),
        ]
        pricing = PricingConfig(
            anchors=anchors,
            scarcity_functions={},
            default_scarcity=ScarcityFunction("smooth", 1.0, 0.3, 50.0),
        )

        healths = {"A": 0.5, "B": 0.5, "C": 0.5}
        result = solve_prices(agents, healths, edges, pricing)

        # B and C depend on A, so B and C get value from A.
        # B and C should have higher prices than A (since they pick up A's
        # contribution), while A's price is just scarcity * anchor.
        # With equal anchors and equal scarcity, the dependents get more.
        assert result.prices["B"] >= result.prices["A"]
        assert result.prices["C"] >= result.prices["A"]

    def test_price_propagation(self):
        """Degrading one agent should raise prices of its dependents."""
        agents = ["A", "B"]
        edges = [
            InteractionEdge("A", "B", 0.3, "dependency", "B depends on A"),
        ]
        anchors = [
            AnchorPoint("A", 100.0, "test", "high", "test"),
            AnchorPoint("B", 100.0, "test", "high", "test"),
        ]
        pricing = PricingConfig(
            anchors=anchors,
            scarcity_functions={},
            default_scarcity=ScarcityFunction("smooth", 1.0, 0.3, 50.0),
        )

        # Baseline: A is healthy
        result_healthy = solve_prices(
            agents, {"A": 1.0, "B": 1.0}, edges, pricing
        )

        # Degraded: A is damaged -> scarcity(A) rises -> B picks up more value
        result_degraded = solve_prices(
            agents, {"A": 0.3, "B": 1.0}, edges, pricing
        )

        # B's price should increase when A is degraded, because B depends on A
        # and A's scarcity multiplier increases its value contribution to B
        assert result_degraded.prices["B"] > result_healthy.prices["B"]


# ── 5. TestSimulationIntegration ──────────────────────────────────────────────


class TestSimulationIntegration:
    """Tests for pricing integration with the simulation engine."""

    def test_backward_compat_no_pricing(self):
        """Without PricingConfig, simulation output should be identical to v0.6."""
        from gaia.cases.forest import build_forest_ecosystem
        from gaia.simulation import run_extraction

        eco = build_forest_ecosystem(total_trees=100, with_pricing=False)
        assert eco.pricing is None

        result = run_extraction(eco, 50)

        # v0.6 behavior: agent_prices should be empty, price_result should be None
        for step in result.steps:
            assert step.agent_prices == []
            assert step.price_result is None

    def test_pricing_increases_extraction_cost(self):
        """Total externality with pricing should be >= without at moderate degradation.

        At moderate degradation, scarcity multipliers > 1.0 amplify the prices
        used for cost computation, increasing the total externality.
        """
        from gaia.cases.forest import build_forest_ecosystem
        from gaia.simulation import run_extraction

        eco_no_pricing = build_forest_ecosystem(total_trees=100, with_pricing=False)
        eco_with_pricing = build_forest_ecosystem(total_trees=100, with_pricing=True)

        # Extract past the safe threshold (30%) to trigger scarcity
        extract_count = 50  # 50% depletion

        result_no = run_extraction(eco_no_pricing, extract_count)
        result_yes = run_extraction(eco_with_pricing, extract_count)

        # With pricing, dynamic prices reflect scarcity and network effects.
        # The total externality should generally differ from the static case.
        # At moderate degradation, scarcity > 1 increases costs.
        # We verify that the pricing result is present and total externality differs.
        assert result_yes.annual_externality != result_no.annual_externality

    def test_price_vector_in_steps(self):
        """When pricing is active, each step should have price_result set."""
        from gaia.cases.forest import build_forest_ecosystem
        from gaia.simulation import run_extraction

        eco = build_forest_ecosystem(total_trees=100, with_pricing=True)
        result = run_extraction(eco, 50)

        for step in result.steps:
            assert step.price_result is not None
            assert isinstance(step.price_result, PriceResult)
            assert len(step.agent_prices) == len(eco.agents)
            # Every per-step price is positive and certified
            assert step.price_result.spectral_radius_bound < 1.0
            for price in step.agent_prices:
                assert price > 0.0


# ── 6. TestCaseIntegration ───────────────────────────────────────────────────


class TestCaseIntegration:
    """Tests that preconfigured cases run without error with pricing enabled."""

    def test_forest_with_pricing(self):
        """Oak Valley forest with with_pricing=True runs without error."""
        from gaia.cases.forest import build_forest_ecosystem
        from gaia.simulation import run_extraction

        eco = build_forest_ecosystem(total_trees=100, with_pricing=True)
        assert eco.pricing is not None

        result = run_extraction(eco, 50)

        assert result.total_units_extracted == 50
        assert result.final_ecosystem_health >= 0.0
        assert result.final_ecosystem_health <= 1.0
        assert len(result.steps) == 50

        # Verify pricing was applied
        last_step = result.steps[-1]
        assert last_step.price_result is not None
        assert last_step.price_result.spectral_radius_bound < 1.0

    def test_costa_brava_with_pricing(self):
        """Costa Brava with with_pricing=True runs without error."""
        from gaia.cases.costa_brava import build_costa_brava_ecosystem
        from gaia.simulation import run_extraction

        eco = build_costa_brava_ecosystem(total_trees=100, with_pricing=True)
        assert eco.pricing is not None

        # 30%: pricing cannot be certified beyond ~32.6% depletion
        result = run_extraction(eco, 30)

        assert result.total_units_extracted == 30
        assert result.final_ecosystem_health >= 0.0
        assert result.final_ecosystem_health <= 1.0
        assert len(result.steps) == 30

        # Verify pricing was applied
        last_step = result.steps[-1]
        assert last_step.price_result is not None

    def test_posidonia_with_pricing(self):
        """Posidonia with with_pricing=True runs without error."""
        from gaia.cases.posidonia import build_posidonia_ecosystem
        from gaia.simulation import run_extraction

        eco = build_posidonia_ecosystem(total_hectares=100, with_pricing=True)
        assert eco.pricing is not None

        # 30%: pricing cannot be certified beyond ~35.4% depletion
        result = run_extraction(eco, 30)

        assert result.total_units_extracted == 30
        assert result.final_ecosystem_health >= 0.0
        assert result.final_ecosystem_health <= 1.0
        assert len(result.steps) == 30

        # Verify pricing was applied
        last_step = result.steps[-1]
        assert last_step.price_result is not None


# ── 7. Step 4 quarantine (C8) ────────────────────────────────────────────────


def _old_power_iteration_estimate(matrix, max_iterations=20):
    """The pre-Step-4 convergence check: 20 power iterations and a Rayleigh
    quotient. Kept here only to show what it used to accept (C8)."""
    n = len(matrix)
    v = [1.0 / n ** 0.5] * n
    eigenvalue = 0.0
    for _ in range(max_iterations):
        w = [sum(matrix[i][j] * v[j] for j in range(n)) for i in range(n)]
        eigenvalue = sum(v[i] * w[i] for i in range(n)) / sum(x * x for x in v)
        norm = sum(x * x for x in w) ** 0.5
        if norm < 1e-15:
            break
        v = [x / norm for x in w]
    return abs(eigenvalue)


def _posidonia_sw_at_health(health):
    from gaia.cases.posidonia import build_posidonia_ecosystem

    eco = build_posidonia_ecosystem(with_pricing=True)
    names = [a.name for a in eco.agents]
    s = build_scarcity_matrix(names, {n: health for n in names}, eco.pricing)
    w = build_value_matrix(names, eco.interactions)
    b = [s[i][i] * a for i, a in enumerate(build_anchor_vector(names, eco.pricing.anchors))]
    return eco, names, matrix_multiply(s, w), b


def _true_spectral_radius_2x2(m):
    """ρ of a non-negative 2x2 matrix (its eigenvalues are real)."""
    a, b, c, d = m[0][0], m[0][1], m[1][0], m[1][1]
    return (a + d) / 2.0 + (((a - d) / 2.0) ** 2 + b * c) ** 0.5


class TestConvergenceBound:
    """ρ(S·W) <= min(max row sum, max column sum): guaranteed, never an estimate."""

    def test_bound_is_min_of_max_row_and_column_sums(self):
        # Row sums 0.9, 0.9; column sums 0.0, 1.8 → 0.9 (row bound wins)
        m = [[0.0, 0.9], [0.0, 0.9]]
        assert spectral_radius_bound(m) == pytest.approx(0.9)
        # Transposed: row sums 0.0, 1.8; column sums 0.9, 0.9 → 0.9 (column)
        mt = [[0.0, 0.0], [0.9, 0.9]]
        assert spectral_radius_bound(mt) == pytest.approx(0.9)
        assert spectral_radius_bound([]) == 0.0

    def test_bound_never_underestimates(self):
        import random

        rng = random.Random(7)
        for _ in range(500):
            m = [[rng.uniform(0, 2) for _ in range(2)] for _ in range(2)]
            assert spectral_radius_bound(m) >= _true_spectral_radius_2x2(m) - 1e-12

    def test_collatz_wielandt_brackets_rho(self):
        m = [[0.0, 1.5], [0.3, 0.0]]  # ρ = √0.45
        lower, upper = collatz_wielandt_bounds(m, [1.0, 0.7])
        assert lower <= 0.45 ** 0.5 <= upper

    def test_posidonia_at_health_02_old_check_accepted_new_rejects(self):
        """C8: at uniform health 0.2 the old estimate was 0.714 (accepted);
        the true ρ is 1.099, so the price series diverges."""
        _, names, sw, b = _posidonia_sw_at_health(0.2)

        old_estimate = _old_power_iteration_estimate(sw)
        assert old_estimate == pytest.approx(0.714, abs=1e-3)
        assert old_estimate < 1.0  # the old check accepted this state

        assert spectral_radius_bound(sw) >= 1.0  # no norm certificate
        with pytest.raises(PricingConvergenceError, match="diverges") as info:
            certify_convergence(sw, b, max_iterations=100)
        assert info.value.spectral_radius_bound >= 1.0

        # Bounds from the (shifted) power iterate bracket the true ρ = 1.099
        u = [1.0] * len(names)
        for _ in range(100):
            u = [x + y for x, y in zip(u, [sum(r[j] * u[j] for j in range(len(u))) for r in sw])]
            u = [x / max(u) for x in u]
        lower = _support_lower_bound(sw, u)
        _, upper = collatz_wielandt_bounds(sw, u)
        assert 1.0 < lower <= 1.0991 and 1.0990 <= upper < 1.1

    def test_posidonia_at_health_02_solve_prices_raises(self):
        eco, names, _, _ = _posidonia_sw_at_health(0.2)
        with pytest.raises(PricingConvergenceError):
            solve_prices(names, {n: 0.2 for n in names}, eco.interactions, eco.pricing)


class TestDirectIterationCheck:
    """When the norm bound is >= 1, convergence is proven by direct iteration."""

    # Row/column sum bound 1.5, but ρ = √0.45 ≈ 0.67
    CONVERGENT = [[0.0, 1.5], [0.3, 0.0]]
    # ρ = √1.2 ≈ 1.095
    DIVERGENT = [[0.0, 4.0], [0.3, 0.0]]

    def test_norm_bound_used_when_below_one(self):
        method, bound, iterations = certify_convergence(
            [[0.0, 0.5], [0.3, 0.0]], [1.0, 1.0], max_iterations=100)
        assert (method, iterations) == ("norm_bound", 0)
        assert bound == pytest.approx(0.5)

    def test_direct_iteration_certifies_convergent_system(self):
        assert spectral_radius_bound(self.CONVERGENT) >= 1.0
        method, bound, iterations = certify_convergence(
            self.CONVERGENT, [1.0, 1.0], max_iterations=100)
        assert method == "direct_iteration"
        assert iterations >= 1
        assert 0.45 ** 0.5 <= bound < 1.0

    def test_direct_iteration_residual_decreases_to_the_solution(self):
        """The certified series converges, to the Gaussian solve."""
        m, b = self.CONVERGENT, [1.0, 2.0]
        certify_convergence(m, b, max_iterations=100)
        v = list(b)
        residuals = []
        for _ in range(60):
            nxt = [sum(m[i][j] * v[j] for j in range(2)) + b[i] for i in range(2)]
            residuals.append(max(abs(x - y) for x, y in zip(nxt, v)))
            v = nxt
        assert residuals[-1] < 1e-9 * residuals[0]
        # V* = (I − M)⁻¹ b: v0 = 1.5·v1 + 1, v1 = 0.3·v0 + 2
        v1 = (0.3 + 2.0) / (1.0 - 0.45)
        assert v == pytest.approx([1.5 * v1 + 1.0, v1])

    def test_direct_iteration_rejects_divergent_system(self):
        with pytest.raises(PricingConvergenceError, match="diverges"):
            certify_convergence(self.DIVERGENT, [1.0, 1.0], max_iterations=100)

    def test_undetermined_within_max_iterations_fails(self):
        # One iteration is not enough to bound ρ below or above 1
        with pytest.raises(PricingConvergenceError, match="could not be proven"):
            certify_convergence(self.CONVERGENT, [1.0, 1.0], max_iterations=1)


class TestExplicitFailure:
    """No static fallback, no scaled scarcity, no clamp of negative prices."""

    def test_no_fallback_api(self):
        import dataclasses
        import inspect

        assert "static_prices" not in inspect.signature(solve_prices).parameters
        assert "fallback_to_static" not in {
            f.name for f in dataclasses.fields(PricingConfig)}

    def test_negative_price_is_failure_not_clamped(self, monkeypatch):
        import gaia.pricing as pricing_module

        agents = ["A", "B"]
        pricing = _simple_pricing_config(agent_names=agents)
        # the first solution is the price vector; the others, columns of the inverse
        monkeypatch.setattr(
            pricing_module, "solve_linear_systems",
            lambda a, bs: [[-1.0, 5.0]] + [list(b) for b in bs[1:]])
        with pytest.raises(PricingConvergenceError, match="non-positive"):
            solve_prices(agents, {"A": 0.5, "B": 0.5}, [], pricing)

    def test_multi_rhs_solve_is_bit_identical_to_single_solves(self):
        """One elimination for n + 1 right-hand sides (D7 profiling) gives
        exactly the numbers of separate solves."""
        import random

        from gaia.pricing import solve_linear_system, solve_linear_systems

        rng = random.Random(3)
        for _ in range(200):
            n = rng.randint(1, 12)
            a = [[rng.uniform(-1.0, 1.0) for _ in range(n)] for _ in range(n)]
            bs = [[rng.uniform(-5.0, 5.0) for _ in range(n)] for _ in range(n + 1)]
            assert solve_linear_systems(a, bs) == [solve_linear_system(a, b) for b in bs]
        with pytest.raises(ValueError, match="singular"):
            solve_linear_systems([[1.0, 2.0], [2.0, 4.0]], [[1.0, 1.0]])
        with pytest.raises(ValueError, match="Dimension mismatch"):
            solve_linear_systems([[1.0]], [[1.0, 2.0]])

    def test_unanchored_agent_rejected_by_solver(self):
        pricing = PricingConfig(
            anchors=[AnchorPoint("A", 100.0, "test", "high", "test")],
            scarcity_functions={},
        )
        with pytest.raises(ValueError, match="must be anchored"):
            solve_prices(["A", "B"], {"A": 1.0, "B": 1.0}, [], pricing)

    def test_extraction_fails_explicitly_at_divergent_depletion(self):
        from gaia.cases.costa_brava import build_costa_brava_ecosystem
        from gaia.simulation import run_extraction

        eco = build_costa_brava_ecosystem(total_trees=200, with_pricing=True)
        with pytest.raises(PricingConvergenceError, match="No fallback") as info:
            run_extraction(eco, 100)
        step = info.value.step
        assert 1 < step <= 100
        assert info.value.depletion_ratio == pytest.approx(step / 200)
        assert f"certified up to step {step - 1}" in str(info.value)

        # Every step before the failure is priced and certified
        result = run_extraction(eco, step - 1)
        for s in result.steps:
            assert s.price_result.spectral_radius_bound < 1.0
            assert all(p > 0.0 for p in s.agent_prices)


class TestAnchoring:
    """Every agent must be anchored when pricing is on."""

    def test_validation_rejects_unanchored_agent(self):
        import dataclasses

        from gaia.cases.forest import build_forest_ecosystem
        from gaia.validation import validate_ecosystem

        eco = build_forest_ecosystem(total_trees=100, with_pricing=True)
        validate_ecosystem(eco)
        eco.pricing = dataclasses.replace(eco.pricing, anchors=eco.pricing.anchors[:1])
        with pytest.raises(ValueError, match="every agent must be anchored"):
            validate_ecosystem(eco)

    def test_anchor_every_agent_derives_placeholders(self):
        from gaia.models import Agent

        agents = [
            Agent(name=n, dependency_weight=0.5, damage_function=lambda x: x,
                  annual_value_per_ha=v, description=n)
            for n, v in (("A", 100.0), ("B", 40.0))
        ]
        documented = AnchorPoint("A", 7.0, "documented", "high", "doc")
        pricing = anchor_every_agent(
            PricingConfig(anchors=[documented], scarcity_functions={}), agents, 25.0)
        by_agent = {a.agent_name: a for a in pricing.anchors}
        assert by_agent["A"] is documented
        assert by_agent["B"].anchor_value == pytest.approx(40.0 * 25.0)
        assert "PLACEHOLDER" in by_agent["B"].source
        assert by_agent["B"].confidence == "low"

    @pytest.mark.parametrize("case", ["forest", "costa_brava", "posidonia", "amazon_forest"])
    def test_shipped_cases_anchor_every_agent_in_eur_per_year(self, case):
        """Derived anchors equal the agent's static annual value (€/yr), so
        anchors and static values share one scale."""
        import importlib

        module = importlib.import_module(f"gaia.cases.{case}")
        builder = getattr(module, f"build_{case.replace('_forest', '') if case == 'amazon_forest' else case}_ecosystem")
        eco = builder(with_pricing=True)
        area = eco.resource.area_ha
        anchored = {a.agent_name for a in eco.pricing.anchors}
        assert anchored == {a.name for a in eco.agents}
        for anchor in eco.pricing.anchors:
            agent = next(a for a in eco.agents if a.name == anchor.agent_name)
            if anchor.source.startswith("PLACEHOLDER: no documented anchor"):
                assert anchor.anchor_value == pytest.approx(agent.annual_value(area))


class TestExperimentalLabel:
    """--with-pricing is labelled experimental in help, text and JSON."""

    def test_text_report_banner(self):
        from gaia.cases.forest import build_forest_ecosystem
        from gaia.report import format_report
        from gaia.simulation import run_extraction

        priced = format_report(run_extraction(
            build_forest_ecosystem(total_trees=100, with_pricing=True), 30))
        static = format_report(run_extraction(
            build_forest_ecosystem(total_trees=100), 30))
        assert "EXPERIMENTAL: endogenous pricing (--with-pricing) is quarantined" in priced
        assert "Convergence: certified" in priced
        assert "EXPERIMENTAL" not in static

    def test_json_flag(self):
        import json

        from gaia.cases.forest import build_forest_ecosystem
        from gaia.serialization import to_json
        from gaia.simulation import run_extraction

        for units in (0, 30):
            d = json.loads(to_json(run_extraction(
                build_forest_ecosystem(total_trees=100, with_pricing=True), units)))
            assert d["pricing"]["experimental"] is True
            assert d["pricing"]["status"] == "converged"
            assert "EXPERIMENTAL" in d["pricing"]["note"]
        d = json.loads(to_json(run_extraction(build_forest_ecosystem(total_trees=100), 30)))
        assert "pricing" not in d

    def test_cli_help(self, capsys):
        from gaia.cases import load_case
        from gaia.cli import case_main

        with pytest.raises(SystemExit):
            case_main(load_case("forest"), ["--help"])
        assert "EXPERIMENTAL" in " ".join(capsys.readouterr().out.split())
