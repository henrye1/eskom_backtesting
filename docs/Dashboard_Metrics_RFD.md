# Request for Decision (RFD) — Dashboard Metrics, Interpretation, and Export Outputs

**Document Version:** 1.0
**Date:** 2026-03-31
**Prepared by:** Anchor Point Risk (Pty) Ltd
**Framework:** LGD Development Factor Backtesting Framework (IFRS 9)
**Reference Entity:** Eskom (Non-Metro Municipalities, RR basis)
**Status:** For Audit Review

---

## 1. Purpose of This RFD

This RFD presents the audit team with the key decisions required regarding the metrics, interpretation, and outputs produced by the LGD Development Factor Backtesting Framework. Each section describes the current implementation, the rationale, alternatives considered, and the decision required.

---

## 2. Background

The framework generates three categories of output:

- **Interactive HTML Dashboard** — 10 Plotly charts + summary KPIs + scenario comparison table
- **Summary Excel Workbooks** — single-window and multi-scenario value-based exports
- **Full Audit Trail Workbooks** — live Excel formulas replicating every intermediate calculation step per vintage

All three export channels are generated from the same computational engine. The outputs have been validated to machine precision (max_abs_diff = 0.0 across 276 residuals at 60-month window) against the client's reference Excel workbook.

---

## 3. Decisions Required

### Decision 1: Composite Score Weighting

**Current implementation:**

| Component | Weight | Metric |
|-----------|--------|--------|
| Bias ratio | 20% | \|mean_error\| / MAE |
| RMSE | 35% | Root mean squared error |
| MAE | 25% | Mean absolute error |
| Tail severity | 20% | max_abs_error / std_error |

**Impact:** Determines which min-observation window is recommended as optimal. Current weights recommend 18-month window (score 0.6465) over 60-month (0.6680) and 24-month (0.6882).

**Rationale:** Equal treatment of precision (RMSE+MAE = 60%), bias (20%), and tail risk (20%). RMSE weighted higher than MAE because large errors are disproportionately costly for provisioning.

**Alternatives:**
- (A) Equal weights across all four components (25% each)
- (B) Precision-dominant: RMSE 50%, MAE 20%, Bias 15%, Tail 15%
- (C) Regulatory-conservative: Bias 40%, RMSE 25%, MAE 15%, Tail 20%

**Recommendation:** Retain current weights unless the institution's risk appetite specifically favours conservatism (option C) or precision (option B).

**Decision required:** Approve or modify the composite score weights.

---

### Decision 2: LGD Cap at 100%

**Current implementation:** LGD cap is set to None (uncapped). The latest vintage at the 60-month window produces LGD values exceeding 100% at TID 42-49 (maximum ~102.9%).

**Cause:** The 15% annual discount rate penalises very late recoveries. When discounted cumulative recoveries at long horizons are minimal, the resulting LGD = 1 - (small discounted recovery sum) can exceed 1.0.

**Impact on exports:**
- HTML Chart 1 (LGD Term Structure) will show values above the 100% line at long TIDs
- Excel LGD Term Structure Summary will contain values > 1.0
- Weighted LGD calculations are affected if large-EAD cohorts sit at high TIDs

**Alternatives:**
- (A) **Cap at 1.0** — set `lgd_cap=1.0`. LGD never exceeds 100%. Simpler for downstream systems. May mask information about discount rate suitability.
- (B) **Uncapped (current)** — preserve economic LGD. More informative about the discount rate assumption. Requires downstream systems to handle values > 1.0.
- (C) **Cap at 1.0 with override flag** — cap by default but log instances where uncapped LGD > 1.0 as a diagnostic warning.

**Recommendation:** Option C provides the safest regulatory posture while preserving diagnostic information.

**Decision required:** Approve LGD cap policy and document rationale.

---

### Decision 3: Monotone LGD Enforcement

**Current implementation:** `monotone_lgd=True` — enforces LGD(t) >= LGD(t-1) so the term structure never decreases.

**Rationale:** Economically, LGD should not decrease as time in default increases, because the remaining recovery potential diminishes. Without monotonicity, numerical noise in the recovery triangle can produce dips.

**Impact:** Affects all LGD values in all exports. With monotonicity off, some intermediate TIDs may show slightly lower LGD than the preceding TID.

**Alternatives:**
- (A) **Monotone on (current)** — cleaner term structure, consistent with economic intuition
- (B) **Monotone off** — preserves raw model output, may reveal data quality issues

**Decision required:** Confirm monotonicity enforcement is appropriate for the audit context.

---

### Decision 4: Confidence Interval Method and Percentile

**Current implementation:** Binomial CI with vintage x term-point scaling:

```
Upper(i,t) = MIN(1, Forecast_oldest[t] + z x StdDev[t] x sqrt(H_i / min(t, n_v-1)))
Lower(i,t) = MAX(0, Forecast_oldest[t] - z x StdDev[t] x sqrt(H_i / min(t, n_v-1)))
```

Where:
- Centre = oldest vintage's forecast (NOT the column mean)
- H_i = hindsight (i+1 for oldest vintage)
- t = TID (capped at n_v - 1)
- z = NORMSINV(ci_percentile)
- Default percentile: 75% (z = 0.6745)

**Key properties:**
- Bands widen at longer horizons (sqrt(H/t) increases)
- Each (vintage, TID) cell has a unique CI value
- Staircase pattern: vintage i has CI from TID = i+1 onwards
- TID 0 has no CI for any vintage
- 275 non-NaN CI cells (not 276)

**Impact:** The CI bands appear in Chart 4, the Upper/Lower CI Excel sheets, and the audit trail backtest summary. Coverage statistics are reported in the summary.

**Known limitation:** Residuals are non-normal (JB and Chi-Sq both reject). The z-based CI assumes normality. This means the stated coverage percentile is approximate --- actual coverage may differ.

**Alternatives:**
- (A) **Current SEM-scaled method** — matches reference workbook to machine precision
- (B) **Empirical quantiles** — use actual residual percentiles. No normality assumption. Requires sufficient residual count per TID.
- (C) **Bootstrap CI** — resample vintage LGD term structures (10,000 iterations, seed=42). Most robust but computationally intensive and not replicable in Excel.
- (D) **t-distribution CI** — use t(df=n_v-1) instead of normal. Accounts for small-sample uncertainty.

**Recommendation:** Retain method (A) for consistency with the validated workbook. Document the normality limitation. Consider adding empirical coverage statistics as a supplementary check.

**Decision required:** Approve CI method, default percentile, and disclosure of normality limitation.

---

### Decision 5: Discount Rate

**Current implementation:** 15% annual rate, applied as monthly compounding: DF = 1/(1+0.15)^((c+1-r)/12).

**IFRS 9 reference:** Paragraph B5.5.44 requires discounting at the original effective interest rate of the financial instrument.

**Impact:** The discount rate directly affects all LGD values. A higher rate produces higher LGD (future recoveries are worth less). This is the single most impactful parameter.

**Known issue:** The reference workbook's "Latest" vintage sheet uses discount_rate=0.0 instead of 0.15 (linking error in the workbook). The Python implementation correctly uses 15% for all vintages. This causes a ~4.5pp difference in LGD at TID 0 (0.2464 at 0% vs 0.2919 at 15%).

**Decision required:** Confirm 15% is the approved EIR proxy for this entity. Document the workbook discrepancy.

---

### Decision 6: Residual Sign Convention

**Current implementation:** Residual = Actual - Forecast.

| Sign | Meaning | Provisioning Impact |
|------|---------|-------------------|
| Positive (+) | Model underestimated LGD (too optimistic) | Provisions may be understated |
| Negative (-) | Model overestimated LGD (too conservative) | Provisions may be overstated |

**Reference dataset result:** Mean residual = +0.70% (slightly optimistic on average), std = 9.4%.

**Decision required:** Confirm the sign convention is understood by all downstream consumers of the residual data.

---

### Decision 7: Normality Test Thresholds

**Current implementation:**
- Jarque-Bera: alpha = 0.05, df = 2, critical = 5.991
- Chi-Square GoF: 12 bins from mu-3sigma to mu+3sigma, merge bins with expected < 5, alpha = 0.05

**Reference results:** Both tests reject normality. JB statistic = 13.3 (>> 5.99). Residuals exhibit excess kurtosis (~1.0) indicating heavier-than-normal tails.

**Implication for audit:** Non-normal residuals do not invalidate the model, but they affect the reliability of the z-based CI bounds. The audit report should disclose this finding.

**Decision required:** Confirm alpha = 0.05 is the institution's standard significance level. Document the non-normality finding and its implications.

---

### Decision 8: Dashboard Export Completeness

**Current export channels:**

| Export | Format | Content |
|--------|--------|---------|
| HTML Dashboard | .html (standalone, ~500KB) | 10 interactive charts + summary box + comparison table + methodology notes |
| Single-Window Summary | .xlsx | 6 sheets: Term Structure Summary, Forecast, Actual, Residuals, Normality Tests, Upper/Lower CI |
| Multi-Scenario Summary | .xlsx | Scenario Comparison + per-window Forecast, Residuals, LGD Term sheets |
| Full Audit Trail | .xlsx (per window) | Master data + 23 vintage formula sheets + Backtest Summary with all formulas |
| All Audit Trails | .zip | One full audit trail workbook per tested window size |

**Decision required:** Confirm the export set is sufficient for the audit evidence pack. Identify any additional outputs required (e.g. standalone residual time series, coverage statistics by TID, sensitivity tables).

---

### Decision 9: Min-Observation Window vs Vintage Window

**Current design:** All scenarios use a fixed 60-month vintage window (producing the same 23 vintages). The "window size" parameter in the multi-scenario comparison controls the min-observation window per TID column — how many cohorts contribute to each chain-ladder calculation.

**Why this matters for audit:** The distinction between the vintage window (controls how many backtesting periods exist) and the min-observation window (controls calibration depth per TID) is subtle but critical. A "12-month window" does NOT mean only 12 months of data are used — it means each TID column in the chain-ladder is calibrated from at most 12 cohorts, while the vintage window still spans 60 months.

**Decision required:** Confirm the audit team understands this distinction. Consider adding clarifying labels to the scenario comparison table (e.g. "Min-Obs Window" instead of "Window").

---

## 4. Summary of Decisions

| # | Decision | Current Setting | Recommendation | Status |
|---|----------|----------------|----------------|--------|
| 1 | Composite score weights | 20/35/25/20 | Retain | Pending |
| 2 | LGD cap | Uncapped | Cap at 1.0 with diagnostic flag | Pending |
| 3 | Monotone LGD | On | Retain | Pending |
| 4 | CI method + percentile | SEM-scaled, 75% | Retain with normality disclosure | Pending |
| 5 | Discount rate | 15% | Confirm as approved EIR proxy | Pending |
| 6 | Residual sign convention | Actual - Forecast | Confirm understanding | Pending |
| 7 | Normality test alpha | 0.05 | Confirm as institutional standard | Pending |
| 8 | Export completeness | 5 export types | Confirm sufficiency | Pending |
| 9 | Window terminology | "Window Size" label | Clarify as "Min-Obs Window" | Pending |

---

## 5. Approval

| Role | Name | Decision | Signature | Date |
|------|------|----------|-----------|------|
| Model Developer | | | | |
| Model Validator | | | | |
| Head of Risk | | | | |
| External Auditor | | | | |

---

*Document generated by the LGD Development Factor Backtesting Framework, version March 2026.*
