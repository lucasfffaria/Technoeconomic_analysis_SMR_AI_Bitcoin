# Supplementary material

**Techno-economic assessment of small modular reactors for artificial intelligence data centres and Bitcoin mining: dedicated versus shared supply with conventional and advanced reactor technologies**

This folder holds what is needed to document, check and repeat the results of the article: the supplementary document, the model code, the input data, the result files from which every table and figure is drawn, and a machine-checked proof of the dispatch rule. Paths below are relative to this folder.

## 1. Contents

```
Supplementary_Material.pdf     supplementary document (Sections S1–S7, Tables S1–S13, Figs. S1–S5)
README.md                       this file
code/                           model and analysis scripts (Python)
data/raw/                       input data: hourly electricity prices and daily Bitcoin network data
results/                        result files of all analyses (CSV, JSON)
lean/                           Lean 4 formalisation of the hourly dispatch
```

The supplementary document covers the model formulation (S1), parameters and probability distributions (S2), the electricity price data (S3), the calibration of the mining model (S4), verification (S5, with the formal verification in S5.1), additional results (S6) and reproducibility (S7).

## 2. Code

All scripts are run from `code/`. They read `data/raw/` and `results/` and write to `results/`; no other location is used.

| File | Purpose | Article and supplement |
|---|---|---|
| `model.py` | Parameters of the two reactors, of the economy and of mining (`Tech`, `Econ`, `Mining`, `ipwr()`, `fhr()`); availability and AI-load generators; hourly dispatch; mining netback process; life-cycle evaluation | Sections 3.1–3.7; S1; Tables 2, S1 |
| `markets.py` | Loads the hourly price series, converts them to 2025 USD and defines the market-years; run as a script it writes `results/market_stats.csv` | Section 3.8; S3; Table S3 |
| `prepare_prices.py` | Converts the files downloaded from ERCOT, CCEE and Ember into the compact hourly tables of `data/raw/` | S3 |
| `common.py` | Shared helpers: hourly records, netback paths, expectation over paths, optimisation of mining capacity, random seeds | Section 3.4 |
| `run_base.py` | Base case: all scenarios for both reactors | Section 4.1–4.3; Tables 1, 3, 5; Fig. 3; Fig. S4 |
| `run_firming.py` | Alternative ways of firming an off-grid campus | Section 4.4; Figs. 3, 5 |
| `run_markets.py` | Export and mining outlets in 374 market-years | Section 4.5; Fig. 6; Tables S6, S7 |
| `run_sens.py` | Deterministic sensitivities, two-way maps and design variants (one function per analysis, see Section 5) | Sections 4.6, 4.8; Table 4; Figs. 7–9, 11; Tables S5, S8–S12 |
| `run_mc.py` | Monte Carlo propagation of uncertainty | Section 4.7; Fig. 10; Fig. S5; Table S13 |
| `verify_lp.py` | Compares the closed-form dispatch with the linear programme solved with HiGHS | S5 |
| `export_figure_data.py` | Writes the series plotted in Figs. 2, 4, S1, S2 and S3 | Table S4 |
| `facts.py` | Collects in `results/facts.json` the numbers quoted in the text of the article and of the supplementary document | – |
| `requirements.txt` | Python packages required | – |

Parameter values are defined in `model.py` (data classes `Tech`, `Econ` and `Mining`) and listed in Tables 1 and 2 of the article and Tables S1 and S2 of the supplementary document. The input distributions of the Monte Carlo analysis are in `run_mc.py` (Table S2). Exchange rates and the consumer price index used to convert prices are constants in `markets.py` (Section S3).

## 3. Data

The price data are described in Section S3 and Table S3 of the supplementary document, and the Bitcoin network data in Section S4 and Table S4. The files were retrieved in November 2026.

| File | Content | Source | Terms of use stated by the source |
|---|---|---|---|
| `emda_caiso_lmp.csv`, `emda_ercot_lmp.csv`, `emda_isone_lmp.csv`, `emda_miso_lmp.csv`, `emda_nyiso_lmp.csv`, `emda_pjm_lmp.csv`, `emda_spp_lmp.csv` | Hourly day-ahead prices of seven US ISO/RTOs, January 2017 to November 2021, USD/MWh (nominal); one row per day, 24 hourly columns | COVID-EMDA+ data hub (Ruan et al., Joule 4 (2020) 2322–2337) | Repository under the MIT licence; the prices originate from the ISO/RTOs |
| `ercot_dam_hourly.csv.gz` | Hourly day-ahead settlement point prices of ERCOT hubs and load zones from January 2020, USD/MWh (nominal), hour beginning, local time | ERCOT, report NP4-180-ER "Historical DAM load zone and hub prices" | Public market information; ERCOT terms of use |
| `ccee_pld_hourly.csv.gz` | Hourly spot price (PLD) of the four Brazilian submarkets from January 2021, BRL/MWh (nominal), hour beginning, local time | CCEE, open data portal, dataset "PLD horário" | CC BY 4.0 |
| `ember_europe_hourly.csv.gz` | Hourly day-ahead prices by country from January 2015, EUR/MWh (nominal), UTC | Ember, European wholesale electricity price data | CC BY 4.0 |
| `btc_coinmetrics.csv` | Daily Bitcoin network metrics from January 2009 to May 2026 (miner revenue, hashrate, price and others) | Coin Metrics, community network data | CC BY-NC 4.0 (non-commercial use) |

The three compressed tables were written by `prepare_prices.py` from the files published by the sources (yearly ERCOT reports, yearly CCEE files and the Ember country files). Those original downloads are not included; they can be obtained from the sources cited in the reference list of the article and, once the compressed archives are extracted, converted with

```
python prepare_prices.py <folder with the downloaded files> ../data/raw
```

The analyses use the price series up to October 2026; later hours present in the files are not used. Redistribution of the data files is subject to the terms of each source; the Coin Metrics data are licensed for non-commercial use only.

## 4. Results

Every number, table and figure of the article and of the supplementary document is drawn from the files below.

| File | Written by | Used in |
|---|---|---|
| `base_results.csv` | `run_base.py` | Tables 1, 3 and 5; Fig. 3 |
| `base_M_curves.csv` | `run_base.py` | Fig. S4 |
| `Mstar_base.json` | `run_base.py` | Table 1 (optimal mining capacity); read by the other analysis scripts |
| `firming.csv` | `run_firming.py` | Fig. 5 |
| `firming_flex_sweep.csv` | `run_firming.py` | Figs. 3 and 5 |
| `markets_iPWR.csv`, `markets_FHR.csv` | `run_markets.py iPWR`, `run_markets.py FHR` | Fig. 6; Tables S6 and S7 |
| `market_stats.csv` | `markets.py` | Table S3; Fig. 7 |
| `sens_oneway.csv` | `run_sens.py oneway` | Fig. 8; Table S8 |
| `map_occ_wacc.csv` | `run_sens.py occ_wacc_map` | Fig. 9 |
| `map_outlet.csv` | `run_sens.py outlet_map` | Fig. 7 |
| `granularity.csv` | `run_sens.py granularity` | Fig. 11a; Table S11 |
| `rampup.csv` | `run_sens.py rampup` | Fig. 11b; Table S12 |
| `breakeven_btc.csv` | `run_sens.py breakeven_btc` | Section 4.2 |
| `policy.csv` | `run_sens.py policy` | Table 4 |
| `export_cap.csv` | `run_sens.py export_cap` | Table S10 |
| `mining_policy.csv` | `run_sens.py mining_policy` | Table S5 |
| `stress.csv` | `run_sens.py stress` | Table S9 |
| `threshold_check.csv` | `run_sens.py threshold_check` | Section S4 |
| `mc.csv` | `run_mc.py 5000` | Fig. 10; Fig. S5; Table S13 |
| `verify_lp.json` | `verify_lp.py` | Section S5 |
| `hashprice_frontier.csv` | `export_figure_data.py` | Fig. 2; Fig. S2; Table S4 |
| `fig04_dispatch_series.csv` | `export_figure_data.py` | Fig. 4 |
| `figS1_price_series.csv` | `export_figure_data.py` | Fig. S1 |
| `figS3_availability_shares.csv`, `figS3_ai_load.csv` | `export_figure_data.py` | Fig. S3 |
| `facts.json` | `facts.py` | Numbers quoted in the text |

Fig. 1 is a schematic and uses no result file. Units are MW, MWh and constant 2025 USD. In the result tables, `lcai` is the break-even AI price (USD/MWh), `lcoe` the levelised cost of electricity, `npv` the net present value, `M` the mining capacity (MW), and columns starting with `E_` are annual energies; the scenario codes are those of Table 1 of the article.

## 5. Repeating the analyses

**Software.** The results were produced with Python 3.13.18, NumPy 2.5.3, SciPy 1.18.1 and pandas 3.0.5. `openpyxl` is needed only by `prepare_prices.py`. To install the packages:

```
pip install -r code/requirements.txt
```

**Commands.** From `code/`, in this order (`run_base.py` must come first, because the other scripts read `Mstar_base.json` and `base_results.csv`):

```
python markets.py
python run_base.py
python run_firming.py
python run_markets.py iPWR
python run_markets.py FHR
python run_sens.py oneway occ_wacc_map outlet_map granularity rampup breakeven_btc policy export_cap mining_policy stress threshold_check
python run_mc.py 5000
python verify_lp.py
python export_figure_data.py
python facts.py
```

`run_markets.py` takes the reactor as argument and writes `markets_iPWR.csv` or `markets_FHR.csv`. `run_sens.py` runs the analyses named on the command line, so that any of them can be repeated alone. `run_mc.py` takes the number of draws and uses two processes.

**Running time.** On a two-core machine the whole sequence takes about 55 minutes: `run_markets.py` about 13 minutes for each reactor, `run_sens.py` about 15 minutes in total (`oneway` 4 minutes, `rampup` and `outlet_map` 3 minutes each, the other analyses about a minute or less), `run_mc.py 5000` about 8 minutes, `run_firming.py` 3 minutes, `run_base.py` under 2 minutes and the remaining scripts a few seconds each.

**Exactness.** Random seeds are fixed (`common.py`, `run_mc.py`), so that a rerun with the versions above returns the same files. With other versions of the libraries, differences in the last digits are possible.

**Other price series.** To use other hourly prices, add to `markets.py` a loader that returns an array of 8,760 prices in 2025 USD/MWh and rerun `run_markets.py`.

## 6. Formal verification (`lean/`)

Section S5.1 of the supplementary document reports a proof, checked by the Lean 4 kernel, that the merit-order dispatch (S12)–(S20) is feasible and solves the linear programme (S3)–(S11).

| File | Content |
|---|---|
| `SmrDispatch/Dispatch.lean` | Definitions (hour, dispatch, constraints, operating margin, merit order) and the proofs |
| `SmrDispatch/Audit.lean` | Prints the axioms on which each main theorem depends |
| `SmrDispatch.lean` | Root of the library |
| `lakefile.toml`, `lean-toolchain`, `lake-manifest.json` | Project configuration: Lean 4.35.0 and Mathlib v4.35.0, with the revision of every dependency |
| `check_statements.py` | Tests the statements on random instances with exact rational arithmetic and against the linear programme (Python; independent of Lean) |

To check the proofs, install Lean with `elan` and run, from `lean/`:

```
lake exe cache get
lake build
```

The first command downloads the compiled Mathlib library (several gigabytes, written to `lean/.lake/`, which is not part of this package). The build must end without errors. `Audit.lean` then lists, for each theorem, the axioms `propext`, `Classical.choice` and `Quot.sound` (two theorems use only `propext` and `Quot.sound`); `sorryAx` must not appear. The build prints style warnings from the Mathlib linter (an unused instance argument and deprecated lemma names), which do not affect the proofs.

The statements hold for data in any linearly ordered field, in particular the rational and the real numbers.

| Theorem | Statement |
|---|---|
| `meritOrder_feasible` | With non-negative capacities and AI load, the merit order satisfies (S4)–(S11) |
| `meritOrder_optimal` | Under `Hour.Ordered`, no feasible dispatch earns a larger margin in the hour |
| `horizon_optimal` | The same for the sum over any set of hours, the objective (S3) |
| `Feasible.nuclear_only` | In every feasible dispatch, mining and export never coincide with imports, tier-1 firming or emergency generation |
| `mining_only_if_profitable`, `export_only_if_profitable` | Conditions (15) and (16) of the article |
| `margin_mono_mining` | The optimal margin of an hour never decreases when mining capacity is added |
| `meritOrder_solves_real` | Feasibility and optimality stated for real numbers |
| `ordering_condition_needed` | Counterexample: without the condition on the tier-1 resource the rule is not optimal |

`Hour.Ordered` is the hypothesis of the optimality theorem (Section S1.2): the tier-1 firming resource costs no more than emergency generation (`c1 ≤ cb`) and, where it is available together with grid imports, no more than imports (`B1 = 0 ∨ Gi = 0 ∨ c1 ≤ p + τg`).

`check_statements.py` tests the statements, not the proofs. On 60,000 random hours the merit order is feasible in all of them and equals the optimum of the linear programme in every hour that satisfies `Hour.Ordered`; when the condition on the tier-1 resource fails, the rule is suboptimal in about 30 % of the hours. It is run with `python check_statements.py` from `lean/` and takes one to two minutes.

## 7. Limitations

The package ends at the result files: the drawing of the figures and the typesetting of the documents are not part of it. The original files downloaded from the market operators are not redistributed (Section 3). The proof concerns the dispatch rule as written in Section S1.2 of the supplementary document; that the code implements this rule is checked numerically by `verify_lp.py`. Results for the FHR rest on assumed cost and performance parameters, as discussed in Section 5.3 of the article.
