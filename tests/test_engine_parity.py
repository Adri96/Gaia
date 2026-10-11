"""
Engine parity: the Cython extraction loop must reproduce the pure-Python loop.

Every configuration is run twice — through ``gaia.cy.simulation_cy`` and with
the Cython path disabled — and every step field plus every result-level field
is compared at rel=1e-12. Each Cython run asserts that the compiled loop was
actually called, so a silent fallback to Python (e.g. a damage function whose
kernel tag stopped verifying) fails instead of passing vacuously.

The parity tests skip when the extension is not built or is stale; the
kernel-tag, routing and stale-build-guard tests run regardless.
"""

import dataclasses
import functools
import os
import types
import warnings

import pytest

import gaia.simulation as sim
from gaia.cases.amazon_forest import build_amazon_ecosystem
from gaia.cases.costa_brava import build_costa_brava_ecosystem
from gaia.cases.forest import build_forest_ecosystem
from gaia.cases.posidonia import build_posidonia_ecosystem
from gaia.damage import exponential_damage, logistic_damage, piecewise_damage
from gaia.models import (
    Agent,
    CarbonProfile,
    DiscountConfig,
    Ecosystem,
    InteractionEdge,
    ResilienceConfig,
    Resource,
    SubstrateProfile,
)
from tests.golden_support import compare, forced_python_engine, normalise

PARITY_REL = 1e-12


def _compiled_loop():
    """The up-to-date compiled loop, even when GAIA_FORCE_PYTHON is set."""
    saved = os.environ.pop("GAIA_FORCE_PYTHON", None)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return sim._load_cython_loop()
    finally:
        if saved is not None:
            os.environ["GAIA_FORCE_PYTHON"] = saved


COMPILED_LOOP = _compiled_loop()

needs_extension = pytest.mark.skipif(
    COMPILED_LOOP is None,
    reason="Cython extension not built or stale: python3 setup.py build_ext --inplace",
)


# ── Synthetic ecosystems ──────────────────────────────────────────────────────

_DAMAGE = {
    "logistic": lambda t: logistic_damage(threshold=t, steepness=12.0),
    "exponential": lambda t: exponential_damage(threshold=t, base=3.0),
    "piecewise": lambda t: piecewise_damage(threshold=t),
}
_MIXED = ["logistic", "exponential", "piecewise", "logistic"]


def _terrestrial(capacity_function: str, **overrides) -> SubstrateProfile:
    fields = dict(
        substrate_type="terrestrial_soil",
        soil_depth_cm=0.6,
        erosion_rate_unprotected=900.0,
        erosion_rate_protected=1.0,
        formation_rate=0.4,
        capacity_function=capacity_function,
        erosion_alpha=2.0,
        critical_minimum=0.3,
        residual_fraction=0.05,
    )
    fields.update(overrides)
    return SubstrateProfile(**fields)


def _marine(substrate_type: str, capacity_function: str, **overrides) -> SubstrateProfile:
    fields = dict(
        substrate_type=substrate_type,
        water_clarity_kd=0.06,
        sediment_stability=0.85,
        erosion_rate_unprotected=60.0,
        erosion_rate_protected=0.5,
        formation_rate=1.0,
        capacity_function=capacity_function,
        erosion_alpha=3.0,
    )
    fields.update(overrides)
    return SubstrateProfile(**fields)


def _synthetic(
    damage="logistic",
    keystone=True,
    interactions=True,
    trophic=True,
    substrate=None,
    resilience=True,
    discount=False,
    total_units=400,
):
    """Four-agent ecosystem exercising every phase of the extraction loop."""
    kinds = _MIXED if damage == "mixed" else [damage] * 4
    specs = [
        # name, weight, rate, trophic level, threshold
        ("Producers", 0.4, 500_000.0, 0, 0.30),
        ("Grazers", 0.3, 300_000.0, 1, 0.25),
        ("Predators", 0.2, 200_000.0, 2, 0.20),
        ("Water", 0.1, 100_000.0, -1, 0.35),
    ]
    agents = [
        Agent(
            name=name,
            dependency_weight=weight,
            damage_function=_DAMAGE[kind](threshold),
            monetary_rate=rate,
            description=name,
            trophic_level=level if trophic else -1,
            is_keystone=keystone and name == "Producers",
            keystone_threshold=0.6,
        )
        for (name, weight, rate, level, threshold), kind in zip(specs, kinds)
    ]
    edges = [
        ("Producers", "Grazers", 0.5),
        ("Producers", "Predators", 0.3),
        ("Grazers", "Predators", 0.4),
        ("Water", "Producers", 0.2),
    ]
    resource = Resource(
        name="Synthetic",
        total_units=total_units,
        safe_threshold_ratio=0.3,
        unit_value=50.0,
        carbon_profile=(
            CarbonProfile(
                stored_carbon_tonnes=2.0,
                annual_absorption_tonnes=0.02,
                soil_carbon_tonnes=1.0,
                soil_release_fraction=0.3,
                carbon_price_per_tonne=80.0,
            )
            if discount else None
        ),
        resilience=ResilienceConfig() if resilience else None,
        substrate=substrate,
        discount=(
            DiscountConfig(rate_schedule=[(0, 0.04), (30, 0.03)], scarcity_rate=0.01)
            if discount else None
        ),
    )
    return Ecosystem(
        name="Synthetic",
        resource=resource,
        agents=agents,
        interactions=[
            InteractionEdge(s, t, k, "dependency", f"{s}->{t}")
            for s, t, k in edges
        ] if interactions else [],
    )


# id → (ecosystem factory, units to extract)
CONFIGS = {
    # Shipped cases (extracting past the safe threshold)
    "forest": (lambda: build_forest_ecosystem(total_trees=2000), 1500),
    "forest_total": (lambda: build_forest_ecosystem(total_trees=500), 500),
    "costa_brava": (lambda: build_costa_brava_ecosystem(total_trees=2000), 1500),
    "posidonia": (lambda: build_posidonia_ecosystem(total_hectares=1000), 700),
    "amazon_forest": (lambda: build_amazon_ecosystem(total_trees=4000), 2000),
    # Damage-function kinds
    "dmg_logistic": (lambda: _synthetic("logistic"), 360),
    "dmg_exponential": (lambda: _synthetic("exponential"), 360),
    "dmg_piecewise": (lambda: _synthetic("piecewise"), 360),
    "dmg_mixed": (lambda: _synthetic("mixed"), 400),
    # Propagation variants
    "keystones_off": (lambda: _synthetic("mixed", keystone=False), 360),
    "no_interactions": (lambda: _synthetic("mixed", interactions=False), 360),
    "no_trophic": (lambda: _synthetic("mixed", trophic=False), 360),
    "bare_v02": (
        lambda: _synthetic("mixed", interactions=False, trophic=False,
                           resilience=False), 360,
    ),
    "single_step": (lambda: _synthetic("mixed"), 1),
    "discount_and_carbon": (lambda: _synthetic("mixed", discount=True), 300),
    # Substrate types × capacity functions
    "soil_linear": (lambda: _synthetic(substrate=_terrestrial("linear")), 380),
    "soil_threshold": (lambda: _synthetic(substrate=_terrestrial("threshold")), 380),
    "soil_logistic": (lambda: _synthetic(substrate=_terrestrial("logistic")), 380),
    "soil_zero_depth": (
        lambda: _synthetic(substrate=_terrestrial("linear", soil_depth_cm=0.0)), 200,
    ),
    "soil_threshold_shallow": (
        lambda: _synthetic(substrate=_terrestrial(
            "threshold", soil_depth_cm=0.2, critical_minimum=0.3)), 200,
    ),
    "sediment_linear": (
        lambda: _synthetic(substrate=_marine("marine_sediment", "linear")), 380,
    ),
    "sediment_logistic": (
        lambda: _synthetic(substrate=_marine("marine_sediment", "logistic")), 380,
    ),
    "matte_linear": (lambda: _synthetic(substrate=_marine("marine_matte", "linear")), 380),
    "matte_logistic": (
        lambda: _synthetic(substrate=_marine("marine_matte", "logistic")), 380,
    ),
    "matte_zero_stability": (
        lambda: _synthetic(substrate=_marine(
            "marine_matte", "logistic", sediment_stability=0.0)), 200,
    ),
    "substrate_with_discount": (
        lambda: _synthetic(substrate=_terrestrial("threshold"), discount=True), 300,
    ),
}


def _run_cython(monkeypatch, ecosystem, units):
    calls = []

    def spy(**kwargs):
        calls.append(kwargs)
        return COMPILED_LOOP(**kwargs)

    monkeypatch.setattr(sim, "extraction_loop_cy", spy, raising=False)
    monkeypatch.setattr(sim, "_HAS_CYTHON", True)
    result = sim.run_extraction(ecosystem, units)
    assert len(calls) == 1, (
        "run_extraction did not use the Cython loop (silent fallback to Python)"
    )
    return result


def _run_python(ecosystem, units):
    with forced_python_engine():
        return sim.run_extraction(ecosystem, units)


def _snapshot(result):
    return {
        "result": {
            f.name: normalise(getattr(result, f.name))
            for f in dataclasses.fields(result)
            if f.name not in ("ecosystem", "steps")
        },
        "steps": [normalise(s) for s in result.steps],
    }


@needs_extension
@pytest.mark.parametrize("config", list(CONFIGS))
def test_engines_agree(config, monkeypatch):
    factory, units = CONFIGS[config]
    cy_result = _run_cython(monkeypatch, factory(), units)
    py_result = _run_python(factory(), units)

    assert len(cy_result.steps) == units
    diffs = compare(_snapshot(py_result), _snapshot(cy_result),
                    rel=PARITY_REL, abs_tol=0.0)
    if diffs:
        shown = "\n  ".join(diffs[:30])
        pytest.fail(f"{config}: Cython differs from Python in {len(diffs)} "
                    f"value(s):\n  {shown}")


@needs_extension
def test_parity_configs_exercise_every_branch():
    """The parametrised configs cover each kernel, substrate type and capacity fn."""
    kinds, substrates = set(), set()
    for factory, _ in CONFIGS.values():
        eco = factory()
        kinds |= {sim._extract_damage_params(a.damage_function)[0] for a in eco.agents}
        sub = eco.resource.substrate
        if sub is not None:
            substrates.add((sub.substrate_type, sub.capacity_function))
    assert kinds == {0, 1, 2}
    assert substrates >= {
        ("terrestrial_soil", "linear"), ("terrestrial_soil", "threshold"),
        ("terrestrial_soil", "logistic"), ("marine_sediment", "linear"),
        ("marine_sediment", "logistic"), ("marine_matte", "linear"),
        ("marine_matte", "logistic"),
    }


# ── Kernel tags and routing (no extension needed) ─────────────────────────────


@pytest.mark.parametrize("kind", sorted(_DAMAGE))
@pytest.mark.parametrize("threshold", [0.05, 0.3, 0.7, 0.95])
def test_factory_kernels_verify(kind, threshold):
    """Each factory's kernel tag reproduces the function, so Cython can use it."""
    fn = _DAMAGE[kind](threshold)
    assert sim._extract_damage_params(fn) == fn.kernel
    assert sim._extract_damage_params(fn)[0] != -1


def test_untagged_damage_function_falls_back():
    assert sim._extract_damage_params(lambda d: d)[0] == -1


def test_mismatched_kernel_tag_falls_back():
    """A wrapper that copies the tag (functools.wraps) but changes the curve."""
    base = logistic_damage(threshold=0.3)

    @functools.wraps(base)
    def squared(d):
        return base(d) ** 2

    assert squared.kernel == base.kernel
    assert sim._extract_damage_params(squared)[0] == -1


def test_untagged_agent_routes_to_python(monkeypatch):
    eco = _synthetic("mixed")
    eco.agents[0].damage_function = lambda d: d
    monkeypatch.setattr(sim, "_HAS_CYTHON", True)
    assert sim._can_use_cython(eco) is False


@pytest.mark.parametrize("config", list(CONFIGS))
def test_every_parity_config_routes_to_cython(config, monkeypatch):
    monkeypatch.setattr(sim, "_HAS_CYTHON", True)
    assert sim._can_use_cython(CONFIGS[config][0]())


def test_pricing_routes_to_python(monkeypatch):
    monkeypatch.setattr(sim, "_HAS_CYTHON", True)
    assert sim._can_use_cython(build_forest_ecosystem(with_pricing=True)) is False


# ── Stale-build guard ─────────────────────────────────────────────────────────


def _fake_module(sha):
    return types.SimpleNamespace(PYX_SOURCE_SHA256=sha, extraction_loop_cy=object())


def test_guard_accepts_matching_hash(monkeypatch):
    monkeypatch.delenv("GAIA_FORCE_PYTHON", raising=False)
    module = _fake_module(sim._pyx_sha256(sim._PYX_PATH))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert sim._load_cython_loop(module) is module.extraction_loop_cy


@pytest.mark.parametrize("sha", ["0" * 64, None])
def test_guard_rejects_stale_build(monkeypatch, sha):
    monkeypatch.delenv("GAIA_FORCE_PYTHON", raising=False)
    with pytest.warns(RuntimeWarning, match="out of date"):
        assert sim._load_cython_loop(_fake_module(sha)) is None


def test_guard_trusts_build_without_pyx_source(monkeypatch, tmp_path):
    """Installed package without the .pyx: use the compiled module as is."""
    monkeypatch.delenv("GAIA_FORCE_PYTHON", raising=False)
    module = _fake_module("anything")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert (sim._load_cython_loop(module, pyx_path=tmp_path / "missing.pyx")
                is module.extraction_loop_cy)


def test_force_python_env_disables_extension(monkeypatch):
    monkeypatch.setenv("GAIA_FORCE_PYTHON", "1")
    module = _fake_module(sim._pyx_sha256(sim._PYX_PATH))
    assert sim._load_cython_loop(module) is None


@needs_extension
def test_built_extension_matches_source(monkeypatch):
    """The .so built by setup.py embeds the hash of the current .pyx."""
    from gaia.cy import simulation_cy
    assert simulation_cy.PYX_SOURCE_SHA256 == sim._pyx_sha256(sim._PYX_PATH)
    monkeypatch.setattr(simulation_cy, "PYX_SOURCE_SHA256", "f" * 64)
    monkeypatch.delenv("GAIA_FORCE_PYTHON", raising=False)
    with pytest.warns(RuntimeWarning, match="out of date"):
        assert sim._load_cython_loop() is None
