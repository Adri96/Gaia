# Changelog

## Unreleased

### Step 8g, follow-up — the owner's review of #11

The owner's decisions on the open questions of #11 and the blocking bug, one commit each. The version is not bumped (the owner decides).

#### Fixed
- **A meadow at 30 m or deeper is valued, never rejected** (Posidonia; Step 8g.7, blocking). `--depth-m 30` (and 35, 40, …) stopped with "at or below the depth limit", though real Catalan meadows live at 30–40 m: a rejected valid input, against the Core Valuation Principles (b). A meadow that lives at depth z proves that its site's depth limit lies deeper, so at a project depth the depth function uses **the site's depth limit**: the regional one (40 m, triangular 30–44) **conditioned on lying at least 2 m below the deepest depth given** (`depth_production.depth_limit_margin`, inferred from the Medes Islands meadow, whose deeper station, 13 m, lies 2 m above its 15 m lower limit and still produced 271 g DW/m²/yr; Mateo & Romero 1997, full text). Its distribution is truncated below that floor (exact conditional; central value max(40 m, floor)); within two margins of 44 m, or below it, it is extended to [floor, floor + 2 m] (triangular, mode at the floor; inferred, beyond the deepest limits documented). The Monte Carlo draws it comonotone with the regional limit (`Sampled.quantile_of`, `Sampled.floor`). The site's curve keeps the fitted P_ref and k (normalised with the regional limit) and reaches zero at the site's limit; the €35's basis, the production at 15 m, keeps the regional limit. Only a negative depth is rejected. Meadow food value, net: **€53.87/ha/yr at 30 m, €22.20 at 35 m, €7.37 at 40 m, €6.00 at 43 m, €30.30 over 30–40 m**; unchanged at 0–28 m and in the regional run. The golden files gain the margin and the (empty) site block; no number changes.

### Step 8g — the meadow's production by depth, the owner's answers

The owner's answers to the open questions 1–5 of #10 and two further items, one commit each. The version is not bumped (the owner decides).

#### Added
- **Depth → primary production for marine primary producers** (`gaia/production.py`; Posidonia; Step 8g.1, D6). A general function that, given a depth, returns how much a marine primary producer (seagrass or macroalga) produces: light falls exponentially with depth (Beer–Lambert), production below light saturation follows it minus a light-independent respiration, so **NPP(z) = P_ref · (e^(−k·z) − e^(−k·z_max)) / (e^(−k·z_ref) − e^(−k·z_max))**, declining monotonically (and convex) to zero at the depth limit. The shape is shared; each species gives three hyperparameters in its case file (`production_function.depth_production`: `npp_at_reference_depth`, `decline_rate`, `depth_limit`, with the reference depth, the data they were fitted to and the depth to value at). *P. oceanica*: P_ref **498.8 g DW/m²/yr at 10 m** (lognormal, 314–792, the 95% prediction interval) and k **0.0803/m** (triangular, 0.0428–0.1178, ±1.96 SE), fitted on ln(production) to six full-text measurements of blades + sheaths + rhizomes (Cala Jonquet 989.3 at 4 m, Cebrián et al. 1997; Medes Islands 803 at 5 m and **271** at 13 m, Mateo & Romero 1997, Table 3 — 257 before, a misreading of the rhizomes; Ischia 709.8, 509.1, 238.2 at 5, 10, 20 m, Pergent et al. 1994) by the new `scripts/fit_depth_production.py` (`--check` compares the case file with the fit; residual sd of ln 0.218, correlation −0.12); z_max **40 m** (triangular 30–44, inferred from the Catalan lower limit ~30 m and 40 m in clear waters, Generalitat 2004, and 44 m in the clearest, Gobert et al. 2009). It gives 770, 499, 318, 196, 115 and 61 g DW/m²/yr at 5, 10, 15, 20, 25 and 30 m. The plant's NPP is now derived from it (no longer a sampled link); its three hyperparameters are sampled links of the Monte Carlo. **The case's depth**: the regional mean, **15 m** (inferred, Generalitat 2004; no source of meadow area by depth could be read, the EMODnet seagrass layer did not answer), conservative since f(mean depth) < mean of f. **`--depth-m M` or `LOW-HIGH`** (new project input, plain-words help): the affected meadow's depth, one depth or a band (exact band mean); a depth at or below 30 m, the depth limit's low end, is rejected with a plain error, never valued at €0 (`Case.with_project_depth`, `gaia.production.with_project_depth`). At a project depth the services the entry is net of scale with the plant's production there (NPP(depth)/NPP(15 m), `net_of_scale`), so the net value stays > 0 at every allowed depth; the regional run subtracts exactly the booked €35 (PR #10 question 3). The depth, the function and the NPP it gives are shown in the meadow's line, the "Primary Production" section and the JSON (`production_functions.<agent>.depth_production`). The meadow's food value: gross **€509.48 → €367.59/ha/yr**, net **€474.48 → €332.59** (range €12.41–1,953.76; by depth €688 at 5 m, €475 at 10, €237 at 20, €174 at 25 m); Monte Carlo net P5 / P50 / P95 **€151 / €320 / €622** (€215 / €490 / €1,085 before). Ledger total **€1,293.15 → €1,151.25/ha/yr**. Default run (50 ha): annual externality **€64,657 → €57,563**, PV **€12.57 M → €11.90 M** (P5 / P50 / P95 10.45 / 13.79 / 17.58). New tests: `tests/test_depth_production.py`; `tests/test_valuation_principles.py` runs every preset and flag at every allowed depth. The three Posidonia goldens and the README example change.
- **The leaf epiphytes' food belongs to the Epiphytes & Algae agent** (Posidonia; Step 8g.2, PR #10 question 2). The food the epiphytes' production supports (€82.20/ha/yr gross) moved from the meadow's production function, where the epiphytes were a producer (Step 8f.2), to a ledger entry of the Epiphytes & Algae agent with its own production function (the main producer may now be given in carbon, `npp_carbon`). Same producer, same links: the total is unchanged (€285.39 + €82.20 = the former €367.59) and nothing is counted twice. The €35 of commercial catch stays netted out of the meadow's chain alone, whose lowest value is €38.83 gross (> €35; €3.83 net), so `net_of` needed no rebalancing. **Shared links**: a link from the food web to the catch that two production functions of a case document identically is one quantity of one food web, drawn once in the Monte Carlo and taken by both chains (`Sampled.same_as`; the tornado shows it once). Per hectare a year: the meadow **€332.59 → €250.39** (P5 / P50 / P95 €151 / €320 / €622 → **€114 / €245 / €511**), Epiphytes & Algae **€0.21 → €82.41** (its food P5 / P50 / P95 **€32 / €72 / €151**). Ledger total and the default run's annual externality unchanged (€1,151.25/ha/yr, €57,563); PV €11.90 M (P5 / P50 / P95 10.45 / 13.79 / 17.58 → **10.50 / 14.11 / 18.12**). The three Posidonia goldens change (beyond the threshold the two agents' cascades differ; the pricing run's meadow anchor falls with its value).

#### Changed
- **The plant's share not buried: the shoots' own, 81.1%** (Posidonia; Step 8g.4, PR #10 question 4). Since the roots are a separate producer (Step 8f.2), the plant's share must exclude them: the leaf blades are not buried, the sheaths and rhizomes go to the matte, so blades / (blades + sheaths + rhizomes) in Mateo & Romero (1997), Table 3 (carbon, Medes Islands, read in the full text) is 79.2% at 5 m and 82.9% at 13 m; value **81.1%**, their mean (status `derived`), replacing the whole-plant 74% (roots included). Range unchanged, 71–83.2% (Pergent et al. 1994 and Cebrián et al. 1997, both blades, sheaths and rhizomes), triangular with its mode at 81.1%. The meadow's food value: gross **€285.39 → €312.49/ha/yr**, net **€250.39 → €277.49** (MC P5 / P50 / P95 €114 / €245 / €511 → **€118 / €254 / €528**; range unchanged, €3.83–1,525.48). Ledger total **€1,151.25 → €1,178.35/ha/yr**. Default run: annual externality **€57,563 → €58,918**, PV **€11.90 M → €12.03 M** (P5 / P50 / P95 10.52 / 14.13 / 18.16). The three Posidonia goldens and the README example change.

- **A Posidonia meadow size requires the diving input too** (Step 8g.5). `gaia run posidonia --total-units N` and the deprecated `gaia posidonia --hectares N` set the size of a specific project meadow just as `--area-ha` does, so they now require `--dive-intensity` and/or `--dive-site-share` and otherwise stop (exit status 1) with the same plain message (naming the flag given). Applies only to cases whose ledger has site-restricted services; the size flags are recognised by the option they set (`--area-ha`, `--total-units`, a legacy case's own size flag), even at the regional value once given. The golden scenarios now give the regional diving input explicitly (`--dive-site-share 0.03106721955477957`, the documented share, exactly), so their numbers are identical (only their recorded argv changes); tests and the README option table updated. No number changes.

- **International dollars converted to euros everywhere** (all cases; Step 8g.6, the owner's item 10). The conversion Amazon used since Step 8e.5, Spain's PPP factor for household final consumption (World Bank PA.NUS.PRVT.PP, the series de Groot et al. used), now applies to every value taken in Int$, through one documented module, `gaia/currency.py` (`EUR_PER_INT_DOLLAR`: 2007 0.808165, 2020 0.686508 €/Int$, read from the World Bank API). A case file records each converted number with `converted_from` (`{"currency": "Int$", "price_year", "amounts"}`) on a parameter, a pricing anchor or a benchmark; parsing checks that the number is its amount × the factor (so it cannot diverge), the provenance carries the conversion, and a Monte Carlo draw drops the record (a draw is not the converted figure). No income or price-year adjustment (Step 8d.5). **forest**: the agent value, de Groot et al. (2012) Table 2 (read in full) temperate forest Int$3,013 − 152 climate regulation = Int$2,861 → **€2,312.16/ha/yr** (was €2,848 at face value, from figures partly typed from memory); anchors water 191 and food 299 Int$/ha × 40 ha → €6,174 and €9,666. Default run (5,000 of 10,000 trees): annual externality **€101,899 → €82,727**, PV **€10.70 M → €9.05 M** (P5 / P50 / P95 6.50 / 10.68 / 17.19 → 5.69 / 9.22 / 14.54). **costa_brava**: woodlands Int$1,588 − 7 = Int$1,581 → **€1,277.71/ha/yr** (was €1,593 at face value); anchors food 52 and pollination 31 Int$/ha × 100 ha → €4,202 and €2,505. Default run (4,000 of 10,000 trees): annual **€127,048 → €101,902**, PV **€9.13 M → €7.55 M** (5.63 / 9.45 / 15.29 → 4.81 / 7.92 / 12.63). **amazon_forest**: the agent value was already converted (now recorded with `converted_from`, €2,602.29 unchanged); its anchors food 200, pollination 30 and water 27 Int$/ha × 1,000 ha → €161,633, €24,245 and €21,820 (default run unchanged, €520,458/yr, PV €60.35 M; only the EXPERIMENTAL pricing run changes). **posidonia**: no value was in Int$; the benchmarks are converted: Stamatiadou et al. 2025 (Int$2020: mean 8,712 → **€5,981**, countries €1,090–65,745; Gaia is now within the country range), de Groot et al. 2012 coastal systems (28,917 → **€23,370**) and Costanza et al. 2014 seagrass/algae beds (international $ per the paper, 28,916 → €23,369); default run unchanged. The benchmark output says Int$ figures are converted at PPP. New `tests/test_currency.py`: the factors, the check, and that no case file carries an Int$ value without the conversion. Goldens: all of forest and costa_brava (numbers), amazon_forest (the pricing run; notes in the other two), posidonia extraction runs (benchmark block); the README examples.

#### Decided (no number changes)
- **The €35 `net_of` subtraction stays fixed** (Step 8g.3, PR #10 question 3): every Monte Carlo draw subtracts the booked commercial catch, not the Fish Populations and Marine Invertebrates values sampled in the same draw (coupling them could bring the meadow to €0). Documented in the case file, the literature review §2b, the methods note §6 and `CASE_NOTES.md`. At a project depth (Step 8g.1) the €35 scales deterministically with the plant's production there.
- **The transfer efficiency's range stays 12.2–21.8%** (Step 8g.3, PR #10 question 5), the Balearic upper end included.

### Step 8f — the meadow's production function, the owner's answers

The owner's answers to the open questions 6–8 of #9, one commit each. The version is not bumped (the owner decides).

#### Added
- **Roots and leaf epiphytes in the meadow's primary production** (Posidonia; Step 8f.2). A production function can now have several primary producers (`gaia/production.py`: a `producers` list beside the plant's links, each with `npp_dry_weight` and `carbon_fraction`, or `npp_carbon`, and its own `food_web_share`; parsed parameters `<producer>.<parameter>`), each feeding the food web only with the production that is not buried (D3). **Roots**: 17 (11–23) g DW/m²/yr, Medes Islands at 13 and 5 m (Mateo & Romero 1997, doi:10.3354/meps151043, full text, Table 3), 40.9% C (Table 4), of which only 4% (2.7–5.3%) decomposes within the year: the rest goes to the matte (Mateo & Romero book all of it as buried; the 0.00015/d belowground decay rate is Mateo 1995 as cited by Cebrián et al. 1997, `secondary`). **Leaf epiphytes**: 1.9 mol C/m²/yr = 22.8 g C/m²/yr (11.4–45.6, ×/÷2, a judgement), Corsica (Bay 1984, as reported by Champenois & Borges 2021, doi:10.1002/lno.11724, Fig. 6, `secondary`; no Catalan figure was found), none buried (`inferred`, lower end 74%). **No double counting with the Epiphytes & Algae agent**: it owns the epiphyte metric of the bioindicator service (monitoring, a cultural service), not food, and no other entry values the epiphytes' production. The plant's NPP range now reaches the Catalan maximum, 989.3 g DW/m²/yr at Cala Jonquet, Cap de Creus (Cebrián et al. 1997, doi:10.3354/meps155029, full text read from an archived copy; it was unreadable in Step 8e.6); its central value stays 476. The meadow's food value: gross **€426.29 → €509.48/ha/yr** (roots +€1.00, epiphytes +€82.20), net **€391.29 → €474.48** (range €31.41–2,993.09). Ledger total **€1,209.95 → €1,293.15/ha/yr**. Default run: annual externality **€60,497 → €64,657**, PV **€12.18 M → €12.57 M** (P5 / P50 / P95 12.09 / 17.27 / 23.94). The report's chain and the meadow's line list the producers; the JSON `production_functions` block gains `producer` and `producers`. The three Posidonia goldens and the README example change.

- **Monte Carlo: production functions sampled link by link** (all cases; Step 8f.3). An agent whose value a production function derives is no longer sampled as one aggregate between the ends of its range (every link at its least or most favourable end at once; for the meadow it reached €0.10/ha/yr before Step 8f.1). `gaia.uncertainty` samples each link of the chain from its own range and distribution, a new per-link `distribution` (`triangular`, the default with a range; `uniform`; `lognormal`, median at the value, the range as its central 95%, truncated at the range ends; `fixed`, the default without one) with an optional `distribution_basis`, and every draw recomputes the chain, the gross value, the net value (gross − the services it is net of, at their booked values) and the agent's value. Seeded and reproducible; generic over any `production_function` in any case file. **No draw at €0**: every distribution stays inside its documented range, parsing now requires the chain with every link at its least favourable end to exceed what the entry is net of (citing the Core Valuation Principles), and a draw at or below €0 would raise `InvariantError`, which is never redrawn or clipped. Outputs: the links appear in the tornado (`production[<agent>].<link>`), the text report and the JSON `uncertainty.production_functions` give each production function's gross and net P5/P50/P95 per hectare, its lowest draw and the count of draws at or below €0 (always 0); the "Primary Production" section says how the links are sampled. Posidonia, distributions per link documented in the case file: the meadow's food value, net, **P5 / P50 / P95 €215 / €490 / €1,085 per hectare a year** (base €474; lowest draw €79). Default run, PV of externality €12.57 M, **P5 / P50 / P95 €11.06 / 14.70 / 18.97 M** (€12.09 / 17.27 / 23.94 M with the aggregate sampling); the carbon release leads the tornado again, the transfer efficiency is the food value's largest driver. The goldens change only in their `production_functions` block (each link's `distribution` and basis); no deterministic number changes.

#### Changed
- **Transfer efficiency of the meadow's production function: a Western Mediterranean figure, 14.3%** (Posidonia; Step 8f.1). The owner asked for the temperate mean, 14.25% (Coll et al. 2008, doi:10.1371/journal.pone.0003881, verified in the full text, Methods (e): temperate and high-latitude models, n = 39, mean 14.25%, sd 5.95, median 13.7%; a temperate estimate, not a Mediterranean one), or a Mediterranean-specific figure if a verified one exists. One does, and is used: the median of the mean transfer efficiencies of five Western Mediterranean Ecopath models tabulated by Sánchez-Zulueta et al. (2023), *Front. Mar. Sci.* 10:1166674, doi:10.3389/fmars.2023.1166674 (full text, Table 3: Balearic Islands 21.8%, Gulf of Alicante 13.9%, South Catalan Sea 12.2%, north-western Mediterranean 14.3%, Gulf of Lions 19.7%), **14.3%**, which is the north-western Mediterranean model (Corrales et al. 2015), the one covering the Catalan coast; range 12.2–21.8% (status `derived`: a median of read values; the model papers are closed and were not read). It replaces the global median, 11.8%. The meadow's food value: gross **€284.74 → €426.29/ha/yr**, net of the €35 commercial catch **€249.74 → €391.29/ha/yr** (range over the links' ends €22.71–1,837.96 net). Ledger total €1,068.40 → **€1,209.95/ha/yr**. Default run (50 of 4,582 ha): annual externality **€53,420 → €60,497**, PV of externality **€11.51 M → €12.18 M** (P5 / P50 / P95 11.46 / 15.56 / 20.60). The meadow's food value, still sampled as one aggregate between the ends of its links, now leads the tornado (Step 8f.3 replaces that sampling). The three Posidonia goldens and the README example change.

### Step 8e — the owner's answers, third round

The owner's answers to the five open questions of #8, one commit each. The version is not bumped (the owner decides).

#### Added
- **No agent at €0: a hard invariant** (all cases; Step 8e.7; PROJECT_DEFINITION.md, Core Valuation Principles (b)). `gaia.validation.validate_ecosystem` now requires every agent's `annual_value_per_ha` (its value on every hectare) to be > 0 (it accepted 0); case parsing rejects an agent whose value, or the low end of whose Monte Carlo range, is not > 0, and a ledger in which an agent owns no service that applies on every hectare; each error cites the rule. No input scales that part of the value, so no preset, flag or draw can reach €0; the pricing check that failed at a zero anchor is gone (it can no longer happen). `tests/test_valuation_principles.py` holds the rule over every case: the full grid of presets and flags (`--dive-site-share`, `--dive-intensity`, `--matte-fate`, `--area-ha` / `--total-units`, `--threshold`, `--with-pricing`), 200 seeded random combinations, the CLI, restoration, and the Monte Carlo ranges at their low ends. Forest, costa_brava and amazon_forest were checked against it and needed no change (every agent shares a positive biome value; EXPERIMENTAL derived prices stay > 0). No number changes.
- **The Posidonia meadow's own value, from its primary production; no agent at €0** (Step 8e.6, the owner's rule). With `--dive-intensity none` the meadow agent used to fall to €0, because diving was its only ledger entry; that was documented as an exception, and the owner rejected it. The meadow now owns, on every hectare, **the food its primary production supports**: a production function (`gaia/production.py`, the ledger entry's `production_function`) from net primary production (476 g DW = 160 g C/m²/yr, Pergent et al. 1994, doi:10.3354/meps106139; 33.6% C, Duarte 1990, doi:10.3354/meps067201) through the share not buried in the matte (74%, Mateo & Romero 1997, Medes Islands, doi:10.3354/meps151043), trophic transfer (11.8% per level, Coll et al. 2008, doi:10.1371/journal.pone.0003881) to the catch's trophic level (3.1: Francour 1997, doi:10.1111/j.1439-0485.1997.tb00434.x, with FishBase), ×9 wet weight (Pauly & Christensen 1995, cited second-hand), a sustainable catch share (46.5%: Zhou et al. 2012, doi:10.1139/f2012-060) and the Catalan first-sale price of white fish in 2014 (€5.11/kg, Generalitat open data): **€284.74/ha/yr gross**, booked **net of the €35 of commercial catch** already owned by Fish Populations and Marine Invertebrates (which keep their entries): **€249.74/ha/yr**. The ledger gains `gross` and `net_of` (parsing enforces value = gross − the services it is net of) and `production_function` (parsing checks that the chain gives the gross). An agent's value is now `annual_value_per_ha` (every hectare) + `site_value_per_ha` × site share (the case format's new `site_value_per_ha`; `Agent.site_value_per_ha`, `Agent.value_per_ha`): `--dive-intensity` and `--dive-site-share` scale only the diving service, so **`none` zeroes the diving service, never the meadow** (€249.74/ha/yr left), and EXPERIMENTAL pricing now runs with `none`. **Productivity is visible**: the meadow's line in the text report shows the NPP → food → € chain and the matte's carbon (1,199 tCO2/ha, 0.95 tCO2/ha/yr buried: an attribution, valued once by `gaia.carbon`, D3); a "Primary Production" section and the JSON (`production_functions`, `value_notes`) carry the chain, each link's source status (verified / derived / secondary / inferred) and a sourced comparison of gross primary production (seagrass 1,903, coral reefs 1,720, intensive cropland 2,182, tropical rainforest 3,000–4,000, a Corsican *P. oceanica* meadow 997, bare sediment 68 g C/m²/yr). No usable willingness-to-pay value for the meadow's existence was found, so none is added. Ledger total €818.66 → **€1,068.40/ha/yr**. Default run (50 of 4,582 ha): annual externality **€40,933 → €53,420**, PV of externality **€10.35 M → €11.51 M** (P5 / P50 / P95 10.30 / 13.65 / 17.67). 50 ha with `--dive-intensity none`: €18,207 → €30,694/yr, PV €8.22 M → €9.39 M. 63 parameters for an extraction (one more, `low`). The three Posidonia goldens and the README example change (see the commit).

- **Dive-activity intensity presets, `--dive-intensity {none,low,medium,high}`** (Posidonia; Step 8e.2). How much the meadow near the dive sites is dived, in dives per hectare of meadow a year: each level is a real Mediterranean dive area's annual dives over the *P. oceanica* cover of its Natura 2000 site (EEA forms). **none** 0; **low** 66.2, Banyuls-Cerbère (14,000 dives, Lloret 2006 conference slides, grey literature); **medium** 566.5, Portofino (up to 40,000 dives, Betti et al. 2023, doi:10.1002/aqc.3918); **high** 5,581, the Medes Islands (60,000 dives over 10.75 ha). At €34.71 a dive: €0, €2,298, €19,663 and €193,730 per hectare near dive sites a year. **Intensity sets the value per hectare near the dive sites, `--dive-site-share` the part of the affected meadow near them** (1 when the intensity is given alone). The default is the Costa Brava average, 421.5 dives/ha/yr (the documented `site_intensity`, a new recorded parameter), so **the default run does not change**. `none` zeroes only the diving service (since Step 8e.6 the meadow keeps its own food value; the exception first documented here is gone). The level is recorded as user-supplied with its basis and is not sampled; the diving part of the meadow's EXPERIMENTAL anchor scales with it. The case format gains `site_intensity` and `site_intensity_levels` on a site-restricted agent (`--<activity>-intensity`; `Agent.site_intensity`, reported in the JSON). For 50 ha with the intensity alone, PV of externality (P5 / P50 / P95): none €8.22 M (6.26 / 9.09 / 12.88), low €18.97 M (16.28 / 23.75 / 35.11), medium €100.2 M (75.4 / 132.0 / 230.2), high €914.8 M (666.9 / 1,216.3 / 2,187.0). 62 parameters for an extraction (one more, sourced); the three Posidonia goldens change only in their calibration block.

#### Changed

- **Amazon agent value re-based on de Groot et al. (2012)** (amazon_forest; Step 8e.5, audit S4). The value every agent shares is now the tropical-forest total of de Groot et al. (2012), *Ecosystem Services* 1:50–61, doi:10.1016/j.ecoser.2012.07.005, Table 2, without climate regulation (carbon is valued by `gaia.carbon`, D3): Int$5,264 − 2,044 = **Int$3,220/ha/yr** (2007), converted with the World Bank PPP conversion factor for household (private) consumption, the series the paper used, for Spain in 2007 (PA.NUS.PRVT.PP, 0.808165 € per Int$): **€2,602.29/ha/yr**, 2007 euros, no income or price-year adjustment (8d.5). An international dollar converts at a PPP rate, not the market rate (the paper's footnote 5; at the 2007 market rate it would be €2,350). It replaces €580/ha/yr, the sum of the spec's partly unverified §8 anchors. Confidence stays `low` (a global mean, not a Central Amazon valuation). Default run, 80,000 of 400,000 trees: annual externality **€116,000 → €520,458**, PV of externality **€34.93 M → €60.35 M** (P5 / P50 / P95 €53.71 / 71.40 / 120.05 M), net social cost €34.81 M → €60.23 M. The three Amazon goldens change (extraction €1,160 → €5,204.58/yr and PV €349,338 → €603,505; restoration net value €61,914 → €223,539; the pricing golden's numbers are unchanged, its anchors are not affected), and the README example. The pricing anchors are still Int$ used as € at face value.
- **The Monte Carlo works for costa_brava and amazon_forest** (Step 8e.4). It used to reject (almost) every draw: their edges into Understory, Canopy Trees (and Costa Brava's Soil Microbiome) sit at or near the in-degree cap, so the placeholder ×/÷3 range pushed them above it, and a third of Costa Brava's fire-curve bases fell at or below 1. Their ranges are narrowed the way Posidonia's were (a judgement per parameter, documented in each parameter's note and in `CASE_NOTES.md`): edges ×0.5–×1.5, but only up to the cap for an agent whose incoming strengths exceed 1/1.5 of it (×1.0–×1.333: the documented strength is then the top of its range); the fire curve's base 1.5–3; the logistic steepness 6–18 and the keystone thresholds ±0.15, uniform, as Posidonia. Drawn values are never rescaled. No draw is rejected now. Default runs, PV of externality, base (P5 / P50 / P95): costa_brava €9.13 M (5.63 / 9.45 / 15.29); amazon_forest €34.93 M (32.83 / 39.76 / 50.96) at the €580/ha/yr value of the time. A new test runs every shipped case's Monte Carlo and checks that it accepts its draws. The seven goldens of the two cases change only in their calibration block (ranges and notes). No number changes.
- **A project meadow must state its diving** (Posidonia; Step 8e.3). `gaia run` with `--area-ha` (a specific project meadow) now requires `--dive-intensity` and/or `--dive-site-share`, and otherwise stops (exit status 1) with a plain message: *"with --area-ha (a specific project site), the dive sites input is required: --dive-intensity {none,low,medium,high} … and/or --dive-site-share F …. If no dive site is within reach, give --dive-intensity none. Without --area-ha the run uses the regional averages."* The regional averages describe a meadow of unknown location, not a named one. The default regional run, `--total-units`/`--hectares` (the size of the reference stock), the other cases and the Python API (`Case.build_ecosystem`) are unchanged. No number changes.
- **The `buried` matte preset is kept** (Posidonia; Step 8e.1): 0.125 released with a 10-year half-life, labelled *inferred, no source*, as before. It is no longer an open question (literature review §4, methods note §5). No number changes.

## 0.10.0 — Step 8: the Posidonia v1.0 case (2026-10-12)

Step 8 of `TOP_PRIORITIES_REPORT.md`: one credible case (decision D6), *Posidonia oceanica* meadows on the Catalan coast, for a named user (a Catalan coastal authority or marine NGO reviewing a port or marina expansion), with every parameter sourced or flagged, uncertainty bounds, benchmarks and a methods note ready for external review. It also releases Step 7 (PR #5: cases as JSON files, `gaia run`).

- **PR #6 — Step 8a, static engine** (D5 option B, D7): the engine evaluates its static damage function directly and says so; Cython is dropped; no number changed. A path-dependent engine (option A) is a committed milestone after v1.0.
- **PR #7 — Step 8b, the Posidonia v1.0 case**: literature review (every DOI checked, every number read), sourced carbon profile (S5 resolved), benchmarks, Monte Carlo uncertainty and a tornado ranking replacing the heuristic band (S7), methods note.
- **PR #8 — Steps 8c and 8d, the owner's answers**:
  - small losses priced linearly in every case (`damage_model: "area_loss"`), so no shipped case issues a CalibrationWarning;
  - a service ledger that prices every Posidonia agent without double counting, with the meadow's diving value only near dive sites (`--dive-site-share`) and the seascape attribution labelled provisional;
  - the reference resource, the carbon release fraction and its half-life as project inputs, with a plain-words `--matte-fate {exposed,excavated,buried}` preset;
  - EXPERIMENTAL pricing from a few sourced anchors in every case, derived prices labelled (they add no independent information);
  - benefit transfers without income or price-year adjustment, documented as a known limitation.

Headline numbers of the default runs (annual externality, PV of externality), 0.9.0 → 0.10.0: Posidonia €4.70 M/yr and €589.7 M (2,000 of 5,000 ha, owner-specified values) → €40,933/yr and €10.35 M (50 of 4,582 ha; P5–P95 €8.73–15.98 M); forest €95,050 → €101,899/yr, €10.11 M → €10.70 M; Costa Brava €121,767 → €127,048/yr, €8.80 M → €9.13 M; Amazon €177,757 → €116,000/yr, €38.81 M → €34.93 M.

The version has one source, `gaia/__init__.py` (read by `pyproject.toml`).

### Step 8d — the owner's answers, second round (PR #8)

#### Changed

- **Small losses priced linearly in every case** (forest, costa_brava, amazon_forest; Step 8d.1), the owner's answer: the structure of Posidonia (Step 8c.3), `"damage_model": "area_loss"` with `threshold_logistic` curves, and for Costa Brava's Fire & Microclimate Regulation a new `threshold_exponential` curve (`gaia.damage.threshold_exponential_damage`, kernel 4: zero up to the threshold, then (base^((D − t)/(1 − t)) − 1)/(base − 1)). Below the threshold each unit lost costs its average value; past it the remaining forest degrades. **Their CalibrationWarnings are gone** (the check looks at the remaining resource, healthy up to the threshold; their former direct curves still warn, a test keeps that visible). Default runs, annual externality and PV: forest €95,050 → €101,899/yr, €10.11 M → €10.70 M; costa_brava €121,767 → €127,048/yr, €8.80 M → €9.13 M; amazon_forest (exactly at its 20% threshold, so now exactly the linear transfer) €177,757 → €116,000/yr, €38.81 M → €34.93 M. All 11 of their goldens change.
- **EXPERIMENTAL pricing: a few sourced anchors in every case** (Step 8d.6), with the reachability rule of Step 8c.6. Forest: Watershed & Local Climate (water, Int$191/ha/yr) and Vegetation & Flora (food, 299), both roots; Costa Brava: Mycorrhizal Fungi (food, 52; the only root) and Pollinators & Insects (pollination, 31); Amazon: Canopy Trees (food, 200), Pollinators (pollination, 30), Aquatic System (water, 27). All from de Groot et al. (2012) Table 2, market-based values (Table 1), read in full. `anchor_every_agent` is off in every file and no placeholder anchor is left; the other prices are derived and labelled `(derived)`, `derived_prices`, `pricing.derived[…]`. **Derived prices are the anchors propagated through placeholder edge weights: they add no independent information.** Quarantine unchanged. The three pricing goldens change (annual externality at the last step: forest €1,153,079 → €70,101; costa_brava €83,902 → €1,208; amazon_forest €4,271 → €518): the former placeholders anchored each agent at its whole static value. `--with-pricing --help` no longer says every agent must be anchored.
- **Seascape attribution labelled provisional** (Posidonia; Step 8d.3). The owner accepted spreading the coralligenous diving value and the megafauna and seabird non-use values evenly over the 190,000 ha of mapped seabed as a provisional assumption. The three agents' provenance notes and ledger entries say PROVISIONAL; the docs no longer list it as an open question. No number changes.
- **Benefit transfers: no income or price-year adjustment** (Posidonia; Step 8d.5), the owner's decision for now. Documented as a known limitation in the methods note (§8) and the literature review (§2); no longer an open question. No number changes.

#### Added

- **The meadow's diving value only near dive sites** (Posidonia; Step 8d.4). The Medes dives (€34.71 × 60,000/yr) are divided over the meadow within reach of dive sites, 142.35 ha (the *P. oceanica* cover of the Costa Brava's five coastal Natura 2000 sites, EEA Standard Data Forms; a flagged proxy, cross-checked with the 8.8 ha Medes meadow of Romero et al. 2001): €14,630/ha/yr near dive sites. A new project input, `--dive-site-share F` (`Agent.site_share`, the case format's agent `sites` / `site_share`, recorded as user-supplied), says what share of the affected meadow is near dive sites; the default is the regional share 0.0311, which gives back the former regional average, so **the default run does not change** (last-digit float noise in the goldens). For 50 ha at a dive site: €749,714/yr, PV €76.7 M (P5–P95 58.4–173.5 M); far from any: €18,207/yr, PV €8.2 M. The service ledger books the near-site value (`site_restricted`), `Case.ledger_by_agent(regional=True)` the regional one; the meadow's EXPERIMENTAL pricing anchor scales with the share. 61 parameters for an extraction (one more, sourced by an official URL).
- **`--matte-fate {exposed,excavated,buried}`** (Posidonia; Step 8d.2): what the project does to the matte, a preset of `--carbon-release-fraction` and `--carbon-release-half-life` (which still override it), from the sourced table of the literature review §4. **exposed** (default, unchanged): 0.63, half-life 10 yr; **excavated**: 0.96, at once (IPCC 2013); **buried**: 0.125, half-life 10 yr, *inferred, no source*. `--help`, the README and the methods note explain the three fates in plain words. The case format gains `carbon.release_fates` (`--<subject>-fate` for any case that defines it; `Case.fate_check()`). No number changes.

### Step 8c — the owner's answers, first round (PR #8)

The owner's answers to the seven open questions of #7, one commit each. **Posidonia numbers change; the other cases change only in four last-digit golden values (8c.7).**

#### Changed

- **Goldens bit for bit** (8c.7): four extraction values still held the old Cython rounding; `scripts/regen_golden.py --exact` compares bit for bit (CI keeps rel 1e-9).
- **First user and question confirmed** (8c.1): a Catalan coastal authority or marine NGO reviewing a port or marina expansion; the "proposal" labels are gone.
- **The reference resource is an input** (8c.4): for hectare cases `--area-ha` sets the reference (the meadow a project affects) and `--resource-name` names it; default the Catalan stock, 4,582 ha.
- **Carbon release over time** (8c.5): `--carbon-release-fraction` and `--carbon-release-half-life` are project inputs; a positive half-life releases the soil carbon as a negative exponential, each year's tranche at that year's SCC, discounted (`CarbonProfile.release_half_life_years`).
- **Small losses priced linearly** (8c.3, Posidonia): `damage_model: "area_loss"`, damage = D + (1 − D) × degradation(D), with a new `threshold_logistic` curve, zero up to the threshold; the marginal hectare costs its average value. Posidonia's CalibrationWarning is resolved by the model (the check looks at the remaining meadow).
- **Service ledger, every agent priced** (8c.2): `service_ledger` books each final service once, with owner, value, method, source and transfer; parsing rejects double counting. Posidonia: €818.66/ha/yr (was €284.83), adding the meadow's diving amenity, coralligenous diving and the non-use values of megafauna and seabirds.
- **A few anchors determine every price** (8c.6, EXPERIMENTAL pricing): reachability replaces "every agent anchored"; derived prices are labelled in text, JSON and provenance. Posidonia: three sourced anchors.
- Posidonia default run (50 of 4,582 ha): €6,325 → €40,933/yr; PV €7.83 M → €10.35 M (P5–P95 8.73–15.98 M).

### Step 8b — Posidonia v1.0 case (PR #7; decision D6)

The Posidonia meadow is the v1.0 case (D6): one case with every parameter sourced or flagged, results with uncertainty bounds, and a methods note ready for external review. **Posidonia numbers change. For the other three cases, no number changes**; their golden files lose only the retired heuristic band.

#### Added

- **First user and question** (`PROJECT_DEFINITION.md`, v1.0; confirmed by the owner in Step 8c): a Catalan coastal authority or marine NGO assessing a port or marina expansion that destroys *N* ha of meadow.
- **`docs/POSIDONIA_LITERATURE_REVIEW.md`**: every parameter of the case with value, range, source and mapping.
  - Every DOI was checked through Crossref and every number read from the source: abstract, full text or official PDF.
  - 25 of 69 parameters are sourced (21 by DOI or arXiv id, 4 by an official URL); 44 are flagged (34 placeholders, the 10 owner-specified weights).
  - Also covers what was searched for and not found.
- **`docs/POSIDONIA_METHODS_NOTE.md`**: a 5–6 page methods note for an ecologist and an environmental economist. It covers structure, unit semantics, calibration regime, sources, the uncertainty method, results, limitations (including the static engine and the committed option A), and questions for the reviewers.
- **Uncertainty** (`gaia/uncertainty.py`; `gaia run <case> --uncertainty [N] [--seed S]`, extraction), replacing the heuristic band (S7). It works on any case file, and gives:
  - a seeded Monte Carlo over each parameter's documented range, or a range set by its confidence;
  - P5/P50/P95 of the annual externality, the PV parts, the PV and the net social cost;
  - a tornado ranking;
  - normative sensitivities (carbon price views, discount rate, scarcity, horizon), which are not sampled.

  The case format gains `"range"`, `"relative_range"` and `"distribution"` on any parameter or provenance template. The JSON calibration block shows them.
- **Benchmarks** (`gaia/benchmarks.py`, `run.benchmarks` in the case format). Each extraction report and its JSON `"benchmarks"` block show where Gaia's per-hectare values fall among published ones. For Posidonia these are Campagne et al. 2015, Stamatiadou et al. 2025, de Groot et al. 2012 / ESVD and Costanza et al. 2014.

#### Changed (Posidonia)

- **Carbon (S5 resolved).** One sourced value with a range for each term:
  - burial 0.953 tCO₂/ha/yr (Mazarrasa et al. 2017), was 1.577;
  - top-metre matte stock 1,199 tCO₂/ha (Monnier et al. 2022), was 2,600 (placeholder);
  - loss on conversion 0.63 (Pendleton et al. 2012), was 0.05 (placeholder);
  - no separate biomass term, was 130.

  Release per hectare destroyed: 755 tCO₂, was 260.
- **Agent values: final services only.** From Campagne et al. 2015:
  - coastal protection 188, water purification 60, fisheries 35 (27–74), knowledge/bioindicator 1.83 €/ha/yr;
  - the six ecological agents carry no euro value (intermediate services or unvalued non-use);
  - total €284.83/ha/yr at full damage, was €1,066 (owner specification). A lower bound: tourism, recreation and non-use are not valued.
- **Resource.** The Catalan stock, 4,582 ha (Generalitat marine habitat map, 2025), was 5,000 ha, more than the whole Catalan stock. The default run destroys 50 ha, was 2,000. The case is renamed *Posidonia oceanica meadows of Catalonia (Costa Brava)*.
- **Succession.** From Kendrick et al. 2005: 100 / 400 / 600 years, was 20 / 50 / 120.
- **Provenance** of the discount rate (Drupp et al. 2018 mean recommended SDR 2.27%; the Ramsey reference fields are now the survey medians), the scarcity rate, planting cost and matte formation. Placeholders are flagged with reasons. The unsourced "80× fish biomass in the Medes Islands" claim is removed.
- **Results.**

  | Run | Quantity | Before | After |
  |---|---|---|---|
  | Default run | Annual externality | 4.70 M€/yr (0.9 default, 2,000 of 5,000 ha) | €6,325/yr (50 of 4,582 ha) |
  | Default run | PV | 589.7 M€ | 7.83 M€ |
  | Default run | Net social cost | — | 7.70 M€ |
  | Golden scenario (2,000 of 5,000 ha) | Annual externality | 4.70 M€ | 1.27 M€ |
  | Golden scenario (2,000 of 5,000 ha) | PV | 589.7 M€ | 408.6 M€ |

  Default run Monte Carlo (1,000 draws), P5 / P50 / P95:
  - PV: 5.62 M€ / 8.78 M€ / 12.78 M€;
  - net social cost: 5.49 M€ / 8.66 M€ / 12.65 M€;
  - led by the carbon release fraction and the matte carbon stock.
- **CalibrationWarning** (health 0.67 at the 20% threshold) remains. No source supports moving the curves; the review explains why.

#### Changed (all cases)

- `DiscountConfig.discount_factor` caches the cumulative factors of a declining schedule. The values are bit-identical, and a present value costs O(H) instead of O(H²).
- EXPERIMENTAL pricing (Posidonia): the six agents without a euro value get their former owner-specified impacts as PLACEHOLDER anchors.

#### Removed

- **The heuristic band** (S7): `SimulationResult.annual_externality_band`, `gaia.resilience.compute_confidence_band`, the text section and the JSON `summary.annual_externality_band`. The Monte Carlo replaces it. Resilience zones and model confidence remain.

### Step 8a — static engine, evaluated directly (PR #6; decisions D5, D7)

The owner's decisions of 2026-10-12: **D5 option B now** (Gaia evaluates a static damage function of depletion and says so), **option A — a path-dependent engine — a firm commitment after v1.0**, and **D7: drop Cython**. **No output number changes**: the golden files are byte-identical, and the new engine reproduces the former pure-Python loop bit for bit on every step and field of the 14 golden scenarios, 25 synthetic configurations and the CLI text/JSON outputs of the four cases.

#### Changed

- **Direct evaluation replaces the per-unit loop** (`gaia/simulation.py`). `run_extraction` evaluates the static function at the final depletion (and the step before, for the marginal cost) and returns `result.steps` as a lazy `ExtractionSteps` sequence: a step is computed when it is indexed or iterated, with the same arithmetic as the old loop. `run_restoration` does the same (`RestorationSteps`). The substrate's per-step Riemann sum (the extraction spread over one year) is kept as is, computed once per run, so its numbers do not change. EXPERIMENTAL pricing still certifies every step on construction, so it still stops at the first step that cannot be certified; restoration still checks every recovery ratio it uses against [0, 1].
- The text report's keystone crossings, zone transitions and irreversibility step come from scans of the quantities involved (`gaia.simulation.keystone_crossings`, `zone_transitions`, `first_irreversible_step`) instead of building every step; `--steps-every N` builds only the steps it prints.
- Speed (Python 3.10, arm64; `docs/ENGINE_PROFILE.md`, measured alternately against `main`): the default Amazon extraction takes 0.21 s instead of 1.52 s with the old Python loop (0.6 s with Cython), its restoration 0.51 s instead of 2.32 s, a 100,000-unit full-depletion sweep 0.25 s instead of 2.03 s; the smaller cases are 1.4–5× faster.
- `PROJECT_DEFINITION.md` §13 rewritten ("A Static Damage Function, Evaluated Directly"): what the engine computes, where time enters (discounting, succession, the substrate ceiling), what that gives up, and the committed option A roadmap (A1 time axis and substrate erosion over real time → A2 relaxation and keystone hysteresis → A3 damage-dependent recovery), with the schema-2 `dynamics` block that keeps the format open for it. README, roadmap ("v1.x — Path-dependent engine"), `version_specs/V09_SPEC.md` (status and §4: the owner's decision) and `TOP_PRIORITIES_REPORT.md` (D5, D7 marked decided) updated.
- `scripts/regen_golden.py` rewrites a golden file only when its snapshot differs beyond the comparison tolerance (rel 1e-9), so last-digit float noise never churns the files. (The stored extraction snapshots were written by the Cython build, whose compiler fused a few multiply-adds: five values differ from the Python engine in their last digit.)
- `scripts/profile_engine.py` times the one engine, summary only and with every step evaluated.
- Packaging: the version is read by `pyproject.toml` (`[tool.setuptools.dynamic]`), so `setup.py` is gone.

#### Removed

- The Cython extension (`gaia/cy/simulation_cy.pyx`), its build (`setup.py`, the `speedups` extra), the engine switch (`_HAS_CYTHON`, `GAIA_FORCE_PYTHON`), the stale-build guard, the CI matrix entries that built it, the parity tests (`tests/test_engine_parity.py`, replaced by `tests/test_direct_evaluation.py`: lazy direct evaluation vs a sequential per-unit loop, exact equality) and `gaia.damage.evaluate_kernel` (the kernel tags stay; `gaia.ecosystem_io` uses them to write curves to files).

### Step 7 — data-driven ecosystems (PR #5)

Step 7 of `TOP_PRIORITIES_REPORT.md` (findings E6, E7). **No output number changes**: the golden snapshots are untouched, which proves that the case files reproduce the 0.9.0 code-defined cases exactly; text and JSON output of the 0.9 command lines are byte-identical.

#### Added

- **Case file format** (`gaia/ecosystem_io.py`, E7): JSON, `"gaia_schema": 1`, stdlib only. `ecosystem_from_dict` / `ecosystem_to_dict`, `load_ecosystem` / `save_ecosystem`, `case_from_dict` / `load_case_file`. It covers everything the four cases use (resource with `area_ha`, a reference density or hectare units; agents, shared or inline damage curves, `annual_value_per_ha`; interactions and keystones; carbon, resilience, substrate, discount schedules or profiles; EXPERIMENTAL pricing; restoration costs, recovery and succession; `calibration_regime`). Every number is bare or `{value, unit, source, confidence, note}`, which becomes a `gaia.provenance.Param`; `provenance_defaults` covers repeated list items. Validation on load names the JSON path and rejects unknown keys, duplicate keys and NaN/Infinity. Round trips (ecosystem → dict → ecosystem, dict → ecosystem → dict) are exact and tested.
- **`gaia run <case | file.json> [options]`** (E6): one CLI for shipped cases and your own files, with `--total-units` for the resource size and every 0.9 option; `gaia run <case> --help` shows the case's defaults. `gaia.cases.load_case(name_or_path)` returns a `Case` with `build_ecosystem(...)`, `run_extraction(...)`, `run_restoration(...)` and `report(result)`.
- The four cases as data files, `gaia/cases/data/{forest,costa_brava,posidonia,amazon_forest}.json`, shipped in the wheel and sdist. The derivations from the former module docstrings are in `gaia/cases/definitions/CASE_NOTES.md`.
- README: *Writing your own case*, with a complete example file that a test runs.
- `version_specs/V09_SPEC.md`: **proposal, pending owner decision D5** (path dependence). Option A (a path-dependent engine: yearly time steps with extraction rates, relaxation, keystone hysteresis, substrate erosion over real time, recovery that depends on prior damage; a `dynamics` block in schema 2) and option B (drop the claim, evaluate the static function directly), with effects on Cython, golden tests and the format, effort estimates and a recommendation (B now, A staged later). Nothing is implemented.
- `docs/ENGINE_PROFILE.md` and `scripts/profile_engine.py` (decision D7): pure Python vs Cython on the four cases, extract and restore, with and without pricing, and a 100,000-unit full-depletion sweep. The compiled loop gains 1.2–3.3× on a whole run; pricing never uses it and spends three quarters of its time in n + 1 linear solves per step, where two would do. Recommendation: keep Cython for now, do not extend it, drop it with either D5 option, and optimise the pricing solver before any `.pyx` work. `--smoke` (tiny sizes) is run by a test, with and without the extension.

#### Changed

- `python -m gaia ... --help` printed `usage: __main__.py`; the program name is now `gaia run <case>` (or `gaia <case>` for the legacy form).
- The `run_*` library wrappers took literal defaults (e.g. `tree_value=100.0`) that could drift from the case's `Param` values; every default now comes from the data file.
- `gaia --help` lists the cases and the deprecated forms; an unknown command or case exits with status 2.
- EXPERIMENTAL pricing is 1.4–3.3× faster with bit-identical results: `solve_prices` runs one Gaussian elimination for the prices and the columns of `(I − S·W)⁻¹` (`gaia.pricing.solve_linear_systems`) instead of n + 1, and computes `S·W` by row scaling.

#### Deprecated (removed in 0.11)

- `gaia <case> [options]` and `python -m gaia.cases.<case> [options]`, with the 0.9 flags (`--trees` / `--hectares`, and the `--cut`, `--destroy`, `--tree-value`, `--revenue` aliases). They run the same code and print the same output, plus a `FutureWarning` on stderr.
- The case modules `gaia.cases.forest`, `costa_brava`, `posidonia`, `amazon_forest`: `build_<case>_ecosystem`, `run_<case>`, `run_<case>_restoration`, the reference-size constants and `main` remain as thin wrappers over the case files.

#### Removed

- The duplicated per-case plumbing (four copies of `run_X`, `run_X_restoration`, `_parse_args` and `main`) and the private module constants (`_FOREST_SUCCESSION`, `_OAK_VALLEY_SUBSTRATE`, ...): use `load_case(name)` and the built ecosystem. `gaia.cli.CASES` (now `gaia.cases.CASE_NAMES` / `CASE_ALIASES`). The provenance helpers only the case modules used: `weight_params`, `keystone_params`, `edge_params`, `restoration_params`, `IDENTICAL_CURVES_NOTE`.

#### Migration

| 0.9 | Now |
|---|---|
| `gaia forest --trees 10000 --units 5000` | `gaia run forest --total-units 10000 --units 5000` |
| `gaia posidonia --hectares 5000` | `gaia run posidonia --total-units 5000` |
| `--cut N`, `--destroy N` / `--tree-value E`, `--revenue E` | `--units N` / `--unit-value E` |
| `build_forest_ecosystem(total_trees=N, tree_value=V)` | `load_case("forest").build_ecosystem(total_units=N, unit_value=V)` |
| `run_forest(...)` (text) | `case.report(case.run_extraction(units, ...))` |
| `gaia.cases.forest._FOREST_SUCCESSION` | `load_case("forest").succession_curve` |
| An ecosystem in Python | still works; `save_ecosystem(eco, "case.json")` writes it as a file |

One difference between the two command lines: the `source` of a user-supplied value names the flag that set it, `user-supplied (--unit-value / unit_value)` with `gaia run` where the legacy form says `(--unit-value / tree_value)`; for Posidonia `(--total-units / total_units)` instead of `(--hectares / total_hectares)`.

## 0.9.0 — audit fixes (2026-10-12)

The fixes from the 2026-10 audit (`TOP_PRIORITIES_REPORT.md`, Steps 0–6), on branch `audit-fixes` after tag `v0.8.1-pre-audit`. The commit messages record every changed number and the reason for it. The changes break the API, CLI and JSON (see *Migration* below), hence the minor-version bump.

**Results are illustrative.** Every output now says how many of its parameters are placeholders or low-confidence. The numbers test the model's internal consistency, not the world.

### Fixed

- **Restoration value did not depend on how much was restored** (C1). Restoration now starts from a real degraded state and retraces that extraction's damage path in reverse. Recovered value = recovery efficiency × damage reversed × substrate ceiling, so it never exceeds the damage reversed. Trophic amplification of recovery, which made consumers recover 1.6–4.1× faster, and the 0.5× recovery cascade are gone (`9037b8a`).
- **One-off totals and yearly flows were mixed** (C2). Agent values are yearly flows, while revenue and restoration costs are one-off. The two are compared only through the present value of the flow. Every monetary line and JSON key carries its unit (`6a3feea`).
- **Results depended on the arbitrary size of the resource** (C4). Agent values are €/ha/yr × `area_ha`, so results are invariant to how finely the resource is divided into units (`c791b6c`).
- **NPVs could diverge** (C3). Validation rejects any configuration whose scarcity rate or carbon-price growth is not strictly below the discount rate. The case scarcity rates were brought within the empirical range: Costa Brava and Amazon 1.28%, Posidonia and the environmental profile 1%. One year convention (flows at the end of years 1..H) replaces the old off-by-one (`9d3eea1`).
- **Carbon was counted two or three times** (C5). `gaia/carbon.py` is the single owner of carbon value. The carbon agents and carbon anchors were removed or renamed to their non-carbon services, and the substrate loss is counted once, as a reduced restoration ceiling (`4a26845`, `c429a9c`).
- **Amazon carbon stock 10× too low** (C6): the reference area is now 1,000 ha (400 trees/ha) (`97508b9`).
- **Soil erosion conversion 10× too small** (C7): 1 t/ha = 0.0769 mm at 1,300 kg/m³ (`2a389c3`).
- **Unsafe endogenous pricing** (C8): convergence is certified at each step; there is no silent fallback to static values, and every agent is anchored (`aa17792`).
- **Cascades saturated** (S2). Incoming edge strengths are capped at 1.0 per agent, keystone boosts included (12 Amazon and 3 Costa Brava edges were rescaled mechanically). The cascade acts on the service still standing, `effective = direct + (1 − direct) × pressure`. Amazon's marginal cost from 50% to 100% depletion is no longer zero (`2beaaee`, `4c7816d`).
- **Posidonia carbon contradicted itself** (S5): one absorption value is used, the IPCC (2013) Tier 1 seagrass rate (`4a26845`).
- **The Cython and Python engines diverged** on substrate types and marine matte. A parity test now compares every step and field at a relative tolerance of 1e-12, and a stale extension is detected and not used (`6d0baa1`).
- **The text report computed figures the JSON did not have** (E3). The report now only formats result fields, so text and JSON cannot disagree (`7fd0bbb`).
- **JSON allowed NaN/Infinity, and inputs were not checked for finiteness** (E8). Output is now strict JSON, and every numeric input must be finite (`bce41d1`).
- **CLI**: the warning about unused restoration flags now reads the parsed arguments, not `sys.argv`. An `--output` write error is a clean message. The default Amazon JSON drops from ~169 MB to 16 KB (`61c1dd7`).

### Changed

- **Monetary semantics** (decisions D1, D2): `annual_value_per_ha` is the € per hectare per year of service lost at full damage, and `Resource.area_ha` is required. `net_social_cost = pv_externality − revenue`, so positive means society loses (the sign is flipped from before).
- **Carbon price** (D3): the social cost of carbon, US EPA (2023) $190/t (2020 emissions) converted at the ECB 2020 rate to €166.35/t, growing 1.3%/yr. €80 (EU ETS) survives only as the labelled market/ETS view (`--carbon-price ets`).
- **"Prevention advantage" is replaced** (C9): `restoration_cost_ratio` = 1 + restoration cost per unit / unit value, described as an input-price ratio, and `destroy_then_restore_penalty` = the PV cost of cutting and restoring over not cutting, split into restoration cost, maturation gap, substrate loss, recovery shortfall and carbon not recovered (`f9f3c65`).
- **Calibration regime**: `Ecosystem.calibration_regime` (A empirical / B direct effects only) is required when there are edges, and all four cases declare B. A `CalibrationWarning` fires when health at the safe threshold is below 0.8; it fires for every shipped case (`2beaaee`).
- **Model constants** (trophic, keystone, edge limits) live in `gaia/constants.py`, each with a source or a PLACEHOLDER flag (`2beaaee`).
- **Endogenous pricing is quarantined** (D4): `--with-pricing` is labelled EXPERIMENTAL in help, text and JSON. It raises `PricingConvergenceError` when a step cannot be certified, and it is ignored, with a warning, in restore mode (`aa17792`).
- **Agent values**: the forest and Costa Brava values, previously back-solved to produce an outcome, are global biome means per hectare (de Groot 2012, Costanza 2014, low confidence). Posidonia's are restated per hectare. Amazon's are brought to its documented non-carbon anchors (`c791b6c`, `4a26845`).
- **Damage-curve invariants** (six shape properties) are checked on every run, for every agent, by `validate_ecosystem` (`bce41d1`).
- **Maturation gap**: a discounted PV over the discount horizon, measured against the substrate-capped mature value (`6a3feea`, `c429a9c`, `f9f3c65`).
- **Confidence band**: renamed the externality band and labelled HEURISTIC (`7fd0bbb`).
- **Deprecated flag aliases** (`--cut`, `--destroy`, `--tree-value`, `--revenue`) warn with `FutureWarning` (`61c1dd7`).
- **Engine refactor**: `run_extraction` and `run_restoration` are split into phases, with no behaviour change (`d4d1da7`).
- **README and `PROJECT_DEFINITION.md`** describe the model as it is: illustrative, with a path-independent engine (open decision D5), and a proposed v1.0 of one credible case pending decision D6. README examples are generated from the code. The version specs carry "superseded in part" notes.

### Removed

- `Agent.monetary_rate` (raises, pointing to `annual_value_per_ha`), `CarbonProfile.carbon_price_per_tonne`, `Agent.succession_curve`, `RestorationConfig`, `SubstrateProfile.water_availability_mm_yr` / `water_clarity_kd`, and `SubstrateState`'s water-clarity and `years_to_recover` fields (`6a3feea`, `4a26845`, `3867e7b`).
- `RestorationResult.prevention_advantage`, `prevention_advantage_with_substrate`, `prevention_advantage_v06`, `substrate_recovery_cost`, `extraction_npv`; `PreventionAdvantageV06` and `compute_prevention_advantage_v06` (`f9f3c65`, `3867e7b`).
- `SimulationStep.discount_factor_at_step`, `npv_externality`, `carbon_price_used` (`3867e7b`).
- `PricingConfig.fallback_to_static`, the scarcity-scaling fallback, and `solve_prices(static_prices=)`; the power-iteration spectral-radius estimate (`aa17792`).
- `propagate_interactions(recovery_mode=, recovery_cascade_factor=)` and `RECOVERY_CASCADE_FACTOR` (`3867e7b`).
- The carbon agents and anchors: Forest "General Biosphere" became "Watershed & Local Climate", Costa Brava "Carbon & Climate" became "Fire & Microclimate Regulation", and Posidonia "Blue Carbon" was removed, with the other weights renormalised (`4a26845`).

### Added

- **Safety net**: golden snapshots of every case × extraction / pricing / restoration scenario (`scripts/regen_golden.py`, `--check`), Cython/Python parity tests, and property tests (`b40e1c0`, `6d0baa1`).
- **Horizon sensitivity**: PV at 50, 100 and 200 years in every output (`9d3eea1`).
- **Restoration**: `run_restoration(starting_state=, units_lost=)` and `--units-lost` on every case; `annual_damage_reversal`, `depletion_before` / `depletion_after` and `initial_ecosystem_health` in the results (`9037b8a`).
- **`--area-ha`** and **`--carbon-price {scc,ets}`** on every case (`c791b6c`, `4a26845`).
- **Parameter provenance and calibration status** (Step 5): `gaia.provenance.Param(value, unit, source, confidence, note)` for every meaningful parameter of the four cases, and `Ecosystem.provenance`. Every result has a `calibration` status: the text reports open with an `ILLUSTRATIVE: N of M recorded parameters are placeholders (p) or low-confidence (l)` banner and end with a Parameter Provenance section, and the JSON has a top-level `calibration` block (`8e349ee`).
- **Packaging**: `pyproject.toml`; a `gaia <case> [args]` command and `python -m gaia`; Cython optional at build time; a CI matrix (Python 3.9–3.12 × Cython / pure Python, golden check, README check, ruff, mypy) (`5974aca`, `d4ea31f`).
- **`--steps-every N`** for JSON, which is summary-only by default above 10,000 steps (`61c1dd7`).
- **`scripts/gen_readme_examples.py`** (`--check`): the README examples are regenerated from the code, and a test fails when they drift (`b0cb831`).
- **`LICENSE`**, and a single version source in `gaia/__init__.py` (`9a007e9`).

### Migration (API, CLI and JSON users)

**Python API**

| Before | Now |
|---|---|
| `Agent(monetary_rate=X)` (€ total at full damage) | `Agent(annual_value_per_ha=v)` in €/ha/yr. The yearly total is `v × Resource.area_ha` (`Agent.annual_value(area_ha)`). Passing `monetary_rate=` raises `TypeError` |
| `Resource(...)` | `Resource(..., area_ha=...)` is required (finite, > 0) |
| `Ecosystem(..., interactions=[...])` | Also `calibration_regime=CalibrationRegime.DIRECT_ONLY` (or `EMPIRICAL`), required when there are edges. Each agent's incoming strengths must sum to ≤ 1.0, keystone boosts included |
| `SimulationResult.total_private_revenue` | `revenue` (€, one-off) |
| `SimulationResult.total_externality_cost` | `annual_externality` (€/yr) and `pv_externality` (€ PV) |
| `SimulationResult.net_social_cost` = revenue − externality | `net_social_cost` = `pv_externality − revenue` (sign flipped) |
| `SimulationStep.agent_costs`, `marginal_cost`, `cumulative_cost`, `private_revenue` | `agent_annual_costs`, `marginal_annual_externality`, `annual_externality` (€/yr), `revenue` (€, cumulative) |
| `RestorationResult.total_recovered_value`, `net_restoration_value`, `total_maturation_gap` | `annual_recovered_value` (€/yr), `net_restoration_pv` (€ PV), `maturation_gap_pv` (€ PV) |
| `RestorationResult.prevention_advantage*` | `restoration_cost_ratio` (input-price ratio) and `destroy_then_restore_penalty` (`.total`, `.ratio`, components) |
| `run_restoration(eco, k, cost, fns)` restored k units from an unspecified state | It restores k of `units_lost` units (default k) cut from the pristine resource, or starts from `starting_state=` |
| `CarbonProfile(carbon_price_per_tonne=...)` | Removed. The price is `DiscountConfig.carbon_price_current` (default: the SCC); `gaia.carbon.with_carbon_price_view(discount, "ets")` gives the market view |
| A `DiscountConfig` with scarcity ≥ discount rate | Rejected (`ValueError`) |
| `--with-pricing` / `PricingConfig` falling back to static values | `PricingConvergenceError` (a `ValueError`) at the first step that cannot be certified. Every agent needs an anchor (`gaia.pricing.anchor_every_agent`) |
| — | `result.calibration` (`CalibrationStatus`) and `Ecosystem.provenance` (list of `Param`) |

**CLI**

- Use `gaia <case>` (or `python -m gaia <case>`). `python -m gaia.cases.<case>` still works.
- `--cut` / `--destroy` → `--units`; `--tree-value` / `--revenue` → `--unit-value`. The old names still work, with a `FutureWarning`.
- In restore mode, `--units-lost N` sets the starting state (default: `--units`).
- New flags: `--area-ha`, `--carbon-price {scc,ets}`, `--steps-every N`. JSON with more than 10,000 steps is summary-only unless `--steps-every` is given.
- `--with-pricing` can now fail with `Error: ...` and exit status 1. It is ignored, with a warning, in restore mode.
- Text reports start with the `ILLUSTRATIVE` banner, so the title is no longer the first line.

**JSON**

- New top-level `calibration` block (right after `mode`). Strict JSON: a non-finite number is `null` plus `<key>_null_reason`.
- Every money key carries a unit suffix (`_eur_yr`, `_eur_pv`, `_eur`, `_eur_per_ha_yr`, `_eur_per_t`). Renamed keys:
  - `summary.total_private_revenue` → `revenue_eur`
  - `summary.total_externality_cost` → `annual_externality_eur_yr`, plus `pv_externality_eur_pv` and `pv_externality_h{50,100,200}_eur_pv`
  - `summary.net_social_cost` → `net_social_cost_eur_pv` (new definition and sign)
  - restoration `summary.total_recovered_value` / `net_restoration_value` / `total_restoration_cost` → `annual_recovered_value_eur_yr` / `net_restoration_value_eur_pv` / `total_restoration_cost_eur`
  - `npv_analysis.{direct,carbon_release,carbon_foregone,total,horizon}` → `services_eur_pv`, `carbon_release_eur_pv`, `carbon_foregone_eur_pv`, `total_eur_pv`, `horizon_years`; `substrate_damage` → `substrate_unrecoverable_eur_pv` (not added to the total)
  - restoration `npv_analysis.{cost,service_benefits,carbon_benefits,total_benefits,net_present_value}` → the same names with `_eur_pv`; `carbon_breakeven.*_price` → `*_price_eur_per_t`; `maturation.total_maturation_gap` → `maturation_gap_eur_pv`
  - steps: `marginal_cost` / `cumulative_cost` / `private_revenue` → `marginal_externality_eur_yr` / `externality_eur_yr` / `revenue_eur`
  - `ecosystem.agents[].monetary_rate` → `annual_value_eur_per_ha_yr` and `annual_value_eur_yr`; `ecosystem.resource.unit_value` → `unit_value_eur`; `carbon_price_per_tonne` → `carbon_price_eur_per_t` (+ `carbon_price_basis`, `carbon_price_growth`)
  - pricing: `spectral_radius` / `converged` → `spectral_radius_bound` / `convergence_check`, plus `experimental: true`, `status` and `note`; `prices` → `prices_eur_yr`
- Removed keys: `prevention_advantage`, `prevention_advantage_v06`, `substrate.prevention_advantage_with_substrate`, and the per-step discount fields.
- Added keys: `ecosystem.calibration_regime`; `area_ha` and `units_per_ha`; `destroy_then_restore_penalty`; `restoration_cost_ratio`; the per-agent direct/cascade split; `annual_externality_band` (heuristic); the extraction `substrate` block; `npv_analysis.discount`; the carbon tonnes; `units_lost`, `depletion_before` / `depletion_after`, `initial_ecosystem_health` and `annual_damage_reversal_eur_yr`; `steps_every`.

## 0.8.1 and earlier

See `version_specs/` (V01–V081) and the roadmap in `PROJECT_DEFINITION.md`. Those documents describe each version as built; their notes say what the audit fixes changed.
