/-
Formal verification of the hourly dispatch of Section S1.2 of the Supplementary Material of

  "Techno-economic assessment of small modular reactors for artificial intelligence data centres and
   Bitcoin mining: dedicated versus shared supply with conventional and advanced reactor technologies".

Numbers such as (S3) or (S12) refer to the equations of the Supplementary Material; (15) and (16)
refer to the equations of the article.
-/
import Mathlib

/-!
# Feasibility and optimality of the merit-order dispatch

For every hour the operator of the plant chooses nuclear generation `G`, mining load `m`, grid export `x`,
grid import `g`, a tier-1 firming resource `b1` (gas engines or curtailed AI load) and emergency
generation `b`. The linear programme (S3)–(S11) maximises the operating margin subject to an energy
balance and to capacity limits. No constraint links two hours, so the programme is solved hour by hour,
and the numerical model uses the closed-form rule (S12)–(S20), a merit order.

This file proves, for data in any linearly ordered field (in particular the rational and the real numbers):

* `meritOrder_feasible`: the merit-order dispatch satisfies every constraint;
* `meritOrder_optimal`: no feasible dispatch earns a larger margin in the hour;
* `horizon_optimal`: hence the merit order solves the programme over any set of hours;
* `Feasible.nuclear_only`: in every feasible dispatch, mining and export never coincide with imports,
  tier-1 firming or emergency generation, i.e. the mine and the export use nuclear energy only;
* `mining_only_if_profitable`, `export_only_if_profitable`: conditions (15) and (16) of the article;
* `margin_mono_mining`: the optimal margin of an hour never decreases when mining capacity is added;
* `ordering_condition_needed`: the hypothesis on the cost of the tier-1 resource cannot be dropped.
-/

namespace SMR.Dispatch

/-- Data of one hour, in the notation of Section S1.2. -/
structure Hour (𝕜 : Type*) where
  /-- available nuclear capacity, `P_t^av` -/
  P : 𝕜
  /-- AI load, `L_t` -/
  L : 𝕜
  /-- mining capacity net of downtime, `M̃` -/
  M : 𝕜
  /-- export limit, `X̄` -/
  X : 𝕜
  /-- import limit, `Ḡ` -/
  Gi : 𝕜
  /-- capacity of the tier-1 firming resource, `B̄₁` -/
  B1 : 𝕜
  /-- mining netback, `ν_t` -/
  ν : 𝕜
  /-- wholesale price, `p_t` -/
  p : 𝕜
  /-- charge on exports, `τ_x` -/
  τx : 𝕜
  /-- charge on imports, `τ_g` -/
  τg : 𝕜
  /-- avoidable generation cost, `c^var` -/
  cv : 𝕜
  /-- cost of the tier-1 firming resource, `c₁` -/
  c1 : 𝕜
  /-- cost of emergency generation, `c_b` -/
  cb : 𝕜

/-- A dispatch: the decision variables of one hour. -/
structure Plan (𝕜 : Type*) where
  /-- nuclear generation, `G_t` -/
  G : 𝕜
  /-- mining load, `m_t` -/
  m : 𝕜
  /-- grid export, `x_t` -/
  x : 𝕜
  /-- grid import, `g_t` -/
  g : 𝕜
  /-- tier-1 firming resource, `b_t¹` -/
  b1 : 𝕜
  /-- emergency generation, `b_t` -/
  b : 𝕜

variable {𝕜 : Type*} [Field 𝕜] [LinearOrder 𝕜] [IsStrictOrderedRing 𝕜]

/-! ## The linear programme -/

/-- Shortfall of nuclear capacity against the AI load, `s_t = max (L_t − P_t^av, 0)`. -/
def shortfall (h : Hour 𝕜) : 𝕜 := max (h.L - h.P) 0

/-- The constraints (S4)–(S11) of one hour. -/
structure Feasible (h : Hour 𝕜) (d : Plan 𝕜) : Prop where
  /-- energy balance (S4) -/
  balance : d.G + d.g + d.b1 + d.b = h.L + d.m + d.x
  G_nonneg : 0 ≤ d.G
  /-- generation limit (S5) -/
  G_le : d.G ≤ h.P
  m_nonneg : 0 ≤ d.m
  /-- mining limit (S6) -/
  m_le : d.m ≤ h.M
  x_nonneg : 0 ≤ d.x
  /-- export limit (S7) -/
  x_le : d.x ≤ h.X
  b1_nonneg : 0 ≤ d.b1
  /-- tier-1 limit (S8) -/
  b1_le : d.b1 ≤ h.B1
  g_nonneg : 0 ≤ d.g
  /-- import limit (S9) -/
  g_le : d.g ≤ h.Gi
  /-- (S10) -/
  b_nonneg : 0 ≤ d.b
  /-- non-nuclear supply is reserved for the shortfall of the AI load (S11) -/
  firm_le : d.g + d.b1 + d.b ≤ shortfall h

/-- Operating margin of one hour: the summand of the objective (S3). -/
def margin (h : Hour 𝕜) (d : Plan 𝕜) : 𝕜 :=
  h.ν * d.m + (h.p - h.τx) * d.x - h.cv * d.G - (h.p + h.τg) * d.g - h.c1 * d.b1 - h.cb * d.b

/-- Capacities and the AI load are non-negative. -/
structure Hour.Valid (h : Hour 𝕜) : Prop where
  P_nonneg : 0 ≤ h.P
  L_nonneg : 0 ≤ h.L
  M_nonneg : 0 ≤ h.M
  X_nonneg : 0 ≤ h.X
  Gi_nonneg : 0 ≤ h.Gi
  B1_nonneg : 0 ≤ h.B1

/-- Order of the firming resources under which the merit order is optimal: the tier-1 resource costs
no more than emergency generation and, if it is available together with grid imports, no more than
imports. In every configuration of the article the two are never available together. -/
def Hour.Ordered (h : Hour 𝕜) : Prop :=
  h.c1 ≤ h.cb ∧ (h.B1 = 0 ∨ h.Gi = 0 ∨ h.c1 ≤ h.p + h.τg)

/-! ## The merit-order rule (S12)–(S20) -/

/-- Tier-1 firming resource (S12). -/
def tier1 (h : Hour 𝕜) : 𝕜 := min (shortfall h) h.B1

/-- Grid imports, used when they cost no more than emergency generation (S13). -/
def imports (h : Hour 𝕜) : 𝕜 :=
  if h.p + h.τg ≤ h.cb then min (shortfall h - tier1 h) h.Gi else 0

/-- Emergency generation (S14). -/
def emergency (h : Hour 𝕜) : 𝕜 := shortfall h - tier1 h - imports h

/-- Surplus of nuclear capacity over the AI load served by the plant (S15). -/
def surplus (h : Hour 𝕜) : 𝕜 := h.P - (h.L - shortfall h)

/-- Mining when it is served first (S16). -/
def mineFirst (h : Hour 𝕜) : 𝕜 := if h.cv < h.ν then min (surplus h) h.M else 0

/-- Export of what mining leaves (S17). -/
def exportAfter (h : Hour 𝕜) : 𝕜 :=
  if h.cv < h.p - h.τx then min (surplus h - mineFirst h) h.X else 0

/-- Export when it is served first (S18). -/
def exportFirst (h : Hour 𝕜) : 𝕜 := if h.cv < h.p - h.τx then min (surplus h) h.X else 0

/-- Mining of what export leaves (S19). -/
def mineAfter (h : Hour 𝕜) : 𝕜 :=
  if h.cv < h.ν then min (surplus h - exportFirst h) h.M else 0

/-- Mining load of the merit order: mining is served first if it pays at least as much as export. -/
def mined (h : Hour 𝕜) : 𝕜 := if h.p - h.τx ≤ h.ν then mineFirst h else mineAfter h

/-- Grid export of the merit order. -/
def exported (h : Hour 𝕜) : 𝕜 := if h.p - h.τx ≤ h.ν then exportAfter h else exportFirst h

/-- The merit-order dispatch (S12)–(S20). -/
def meritOrder (h : Hour 𝕜) : Plan 𝕜 where
  G := h.L - shortfall h + mined h + exported h
  m := mined h
  x := exported h
  g := imports h
  b1 := tier1 h
  b := emergency h

theorem meritOrder_G (h : Hour 𝕜) :
    (meritOrder h).G = h.L - shortfall h + mined h + exported h := rfl
theorem meritOrder_m (h : Hour 𝕜) : (meritOrder h).m = mined h := rfl
theorem meritOrder_x (h : Hour 𝕜) : (meritOrder h).x = exported h := rfl
theorem meritOrder_g (h : Hour 𝕜) : (meritOrder h).g = imports h := rfl
theorem meritOrder_b1 (h : Hour 𝕜) : (meritOrder h).b1 = tier1 h := rfl
theorem meritOrder_b (h : Hour 𝕜) : (meritOrder h).b = emergency h := rfl

/-! ## Two outlets and one budget

The three lemmas below are the arithmetic core of the proof. Two outlets with unit values `α` and `β`
and capacities `U` and `V` share a budget `S`. Serving the more valuable outlet first is optimal. The
same lemmas are used twice: for mining and export, which share the nuclear surplus, and for the
firming resources, which share the shortfall. -/

/-- Both outlets pay, the first at least as much as the second: fill the first, then the second. -/
theorem greedy_both {α β U V S u v : 𝕜} (hβ : 0 ≤ β) (hαβ : β ≤ α) (hV : 0 ≤ V)
    (hu : u ≤ U) (hv0 : 0 ≤ v) (hv : v ≤ V) (huv : u + v ≤ S) :
    α * u + β * v ≤ α * min S U + β * min (S - min S U) V := by
  have hα : 0 ≤ α := le_trans hβ hαβ
  rcases le_total S U with hSU | hUS
  · -- the budget is exhausted by the first outlet
    rw [min_eq_left hSU, sub_self, min_eq_left hV, mul_zero, add_zero]
    nlinarith [mul_nonneg (sub_nonneg.2 hαβ) hv0, mul_nonneg hα (sub_nonneg.2 huv)]
  · rw [min_eq_right hUS]
    rcases le_total (S - U) V with hSV | hVS
    · -- the first outlet is full and the second takes the rest of the budget
      rw [min_eq_left hSV]
      nlinarith [mul_nonneg (sub_nonneg.2 hαβ) (sub_nonneg.2 hu), mul_nonneg hβ (sub_nonneg.2 huv)]
    · -- both outlets are full
      rw [min_eq_right hVS]
      nlinarith [mul_nonneg hα (sub_nonneg.2 hu), mul_nonneg hβ (sub_nonneg.2 hv)]

/-- Only the first outlet pays: fill it and leave the second empty. -/
theorem greedy_first {α β U S u v : 𝕜} (hα : 0 ≤ α) (hβ : β ≤ 0)
    (hu : u ≤ U) (hv0 : 0 ≤ v) (huv : u + v ≤ S) :
    α * u + β * v ≤ α * min S U := by
  have hu' : u ≤ min S U := le_min (by linarith) hu
  nlinarith [mul_nonneg hα (sub_nonneg.2 hu'), mul_nonneg (neg_nonneg.2 hβ) hv0]

/-- Neither outlet pays: nothing can be gained. -/
theorem greedy_none {α β u v : 𝕜} (hα : α ≤ 0) (hβ : β ≤ 0) (hu0 : 0 ≤ u) (hv0 : 0 ≤ v) :
    α * u + β * v ≤ 0 := by
  nlinarith [mul_nonneg (neg_nonneg.2 hα) hu0, mul_nonneg (neg_nonneg.2 hβ) hv0]

/-- An outlet that takes `min S U` when a condition holds and nothing otherwise stays within its
capacity `U` and within the budget `S`. -/
theorem take_bounds (c : Prop) [Decidable c] {S U : 𝕜} (hS : 0 ≤ S) (hU : 0 ≤ U) :
    0 ≤ (if c then min S U else 0) ∧ (if c then min S U else 0) ≤ U ∧
      (if c then min S U else 0) ≤ S := by
  split_ifs
  · exact ⟨le_min hS hU, min_le_right _ _, min_le_left _ _⟩
  · exact ⟨le_refl _, hU, hS⟩

/-! ## Shortfall and surplus -/

theorem shortfall_nonneg (h : Hour 𝕜) : 0 ≤ shortfall h := le_max_right _ _

theorem shortfall_of_le {h : Hour 𝕜} (hLP : h.L ≤ h.P) : shortfall h = 0 := by
  unfold shortfall
  exact max_eq_right (sub_nonpos.2 hLP)

theorem shortfall_of_lt {h : Hour 𝕜} (hPL : h.P < h.L) : shortfall h = h.L - h.P := by
  unfold shortfall
  exact max_eq_left (sub_nonneg.2 hPL.le)

theorem surplus_of_le {h : Hour 𝕜} (hLP : h.L ≤ h.P) : surplus h = h.P - h.L := by
  unfold surplus
  rw [shortfall_of_le hLP, sub_zero]

theorem surplus_of_lt {h : Hour 𝕜} (hPL : h.P < h.L) : surplus h = 0 := by
  unfold surplus
  rw [shortfall_of_lt hPL]
  ring

theorem surplus_nonneg (h : Hour 𝕜) : 0 ≤ surplus h := by
  rcases lt_or_ge h.P h.L with hPL | hLP
  · exact le_of_eq (surplus_of_lt hPL).symm
  · rw [surplus_of_le hLP]
    exact sub_nonneg.2 hLP

theorem tier1_le_shortfall (h : Hour 𝕜) : tier1 h ≤ shortfall h := min_le_left _ _

/-! ## Feasibility of the merit order -/

/-- Mining and export of the merit order respect their limits and never exceed the surplus. -/
theorem outlets_bounds (h : Hour 𝕜) (hM : 0 ≤ h.M) (hX : 0 ≤ h.X) :
    0 ≤ mined h ∧ mined h ≤ h.M ∧ 0 ≤ exported h ∧ exported h ≤ h.X ∧
      mined h + exported h ≤ surplus h := by
  have hS := surplus_nonneg h
  unfold mined exported
  split_ifs
  · -- mining first
    have h1 : 0 ≤ mineFirst h ∧ mineFirst h ≤ h.M ∧ mineFirst h ≤ surplus h :=
      take_bounds (h.cv < h.ν) hS hM
    have h2 : 0 ≤ exportAfter h ∧ exportAfter h ≤ h.X ∧ exportAfter h ≤ surplus h - mineFirst h :=
      take_bounds (h.cv < h.p - h.τx) (sub_nonneg.2 h1.2.2) hX
    exact ⟨h1.1, h1.2.1, h2.1, h2.2.1, by linarith [h2.2.2]⟩
  · -- export first
    have h1 : 0 ≤ exportFirst h ∧ exportFirst h ≤ h.X ∧ exportFirst h ≤ surplus h :=
      take_bounds (h.cv < h.p - h.τx) hS hX
    have h2 : 0 ≤ mineAfter h ∧ mineAfter h ≤ h.M ∧ mineAfter h ≤ surplus h - exportFirst h :=
      take_bounds (h.cv < h.ν) (sub_nonneg.2 h1.2.2) hM
    exact ⟨h2.1, h2.2.1, h1.1, h1.2.1, by linarith [h2.2.2]⟩

/-- The firming resources of the merit order respect their limits. -/
theorem firming_bounds (h : Hour 𝕜) (hGi : 0 ≤ h.Gi) (hB1 : 0 ≤ h.B1) :
    0 ≤ tier1 h ∧ tier1 h ≤ h.B1 ∧ 0 ≤ imports h ∧ imports h ≤ h.Gi ∧ 0 ≤ emergency h := by
  have hs := shortfall_nonneg h
  have ht := tier1_le_shortfall h
  have h2 : 0 ≤ imports h ∧ imports h ≤ h.Gi ∧ imports h ≤ shortfall h - tier1 h :=
    take_bounds (h.p + h.τg ≤ h.cb) (sub_nonneg.2 ht) hGi
  have hE : emergency h = shortfall h - tier1 h - imports h := rfl
  exact ⟨le_min hs hB1, min_le_right _ _, h2.1, h2.2.1, by rw [hE]; linarith [h2.2.2]⟩

/-- **Feasibility.** The merit-order dispatch (S12)–(S20) satisfies the constraints (S4)–(S11). -/
theorem meritOrder_feasible (h : Hour 𝕜) (hv : h.Valid) : Feasible h (meritOrder h) := by
  obtain ⟨hm0, hmM, hx0, hxX, hmx⟩ := outlets_bounds h hv.M_nonneg hv.X_nonneg
  obtain ⟨hb10, hb1B, hg0, hgG, hb0⟩ := firming_bounds h hv.Gi_nonneg hv.B1_nonneg
  have hLs : 0 ≤ h.L - shortfall h := by
    rcases lt_or_ge h.P h.L with hPL | hLP
    · rw [shortfall_of_lt hPL]
      linarith [hv.P_nonneg]
    · rw [shortfall_of_le hLP]
      linarith [hv.L_nonneg]
  have hS : surplus h = h.P - (h.L - shortfall h) := rfl
  have hE : emergency h = shortfall h - tier1 h - imports h := rfl
  refine
    { balance := ?_, G_nonneg := ?_, G_le := ?_, m_nonneg := hm0, m_le := hmM, x_nonneg := hx0,
      x_le := hxX, b1_nonneg := hb10, b1_le := hb1B, g_nonneg := hg0, g_le := hgG,
      b_nonneg := hb0, firm_le := ?_ }
  · show h.L - shortfall h + mined h + exported h + imports h + tier1 h + emergency h
        = h.L + mined h + exported h
    rw [hE]
    ring
  · show 0 ≤ h.L - shortfall h + mined h + exported h
    linarith
  · show h.L - shortfall h + mined h + exported h ≤ h.P
    linarith
  · show imports h + tier1 h + emergency h ≤ shortfall h
    rw [hE]
    linarith

/-! ## Structure of every feasible dispatch -/

/-- In an hour without shortfall no feasible dispatch uses imports, tier-1 firming or emergency
generation. -/
theorem Feasible.firming_zero {h : Hour 𝕜} {d : Plan 𝕜} (hd : Feasible h d) (hLP : h.L ≤ h.P) :
    d.g = 0 ∧ d.b1 = 0 ∧ d.b = 0 := by
  have h1 := hd.firm_le
  rw [shortfall_of_le hLP] at h1
  have h2 := hd.g_nonneg
  have h3 := hd.b1_nonneg
  have h4 := hd.b_nonneg
  exact ⟨by linarith, by linarith, by linarith⟩

/-- In an hour with shortfall every feasible dispatch runs the plant at full available capacity,
serves neither the mine nor the export, and covers exactly the shortfall with the firming resources. -/
theorem Feasible.outlets_zero {h : Hour 𝕜} {d : Plan 𝕜} (hd : Feasible h d) (hPL : h.P < h.L) :
    d.m = 0 ∧ d.x = 0 ∧ d.G = h.P ∧ d.g + d.b1 + d.b = h.L - h.P := by
  have h1 := hd.firm_le
  rw [shortfall_of_lt hPL] at h1
  have h2 := hd.balance
  have h3 := hd.G_le
  have h4 := hd.m_nonneg
  have h5 := hd.x_nonneg
  exact ⟨by linarith, by linarith, by linarith, by linarith⟩

/-- In every feasible dispatch mining and export together never exceed the nuclear surplus. -/
theorem Feasible.outlets_le_surplus {h : Hour 𝕜} {d : Plan 𝕜} (hd : Feasible h d) :
    d.m + d.x ≤ surplus h := by
  have h1 := hd.balance
  have h2 := hd.G_le
  have h3 := hd.firm_le
  have hS : surplus h = h.P - (h.L - shortfall h) := rfl
  linarith

/-- **The mine and the export use nuclear energy only.** In every feasible dispatch, either no
non-nuclear energy is used, or nothing is mined and nothing is exported. -/
theorem Feasible.nuclear_only {h : Hour 𝕜} {d : Plan 𝕜} (hd : Feasible h d) :
    (d.g = 0 ∧ d.b1 = 0 ∧ d.b = 0) ∨ (d.m = 0 ∧ d.x = 0) := by
  rcases lt_or_ge h.P h.L with hPL | hLP
  · exact Or.inr ⟨(hd.outlets_zero hPL).1, (hd.outlets_zero hPL).2.1⟩
  · exact Or.inl (hd.firming_zero hLP)

/-! ## Optimality of the merit order -/

theorem mineFirst_pos {h : Hour 𝕜} (hm : h.cv < h.ν) : mineFirst h = min (surplus h) h.M := by
  unfold mineFirst
  rw [if_pos hm]

theorem mineFirst_neg {h : Hour 𝕜} (hm : ¬h.cv < h.ν) : mineFirst h = 0 := by
  unfold mineFirst
  rw [if_neg hm]

theorem exportAfter_pos {h : Hour 𝕜} (hx : h.cv < h.p - h.τx) :
    exportAfter h = min (surplus h - mineFirst h) h.X := by
  unfold exportAfter
  rw [if_pos hx]

theorem exportAfter_neg {h : Hour 𝕜} (hx : ¬h.cv < h.p - h.τx) : exportAfter h = 0 := by
  unfold exportAfter
  rw [if_neg hx]

theorem exportFirst_pos {h : Hour 𝕜} (hx : h.cv < h.p - h.τx) :
    exportFirst h = min (surplus h) h.X := by
  unfold exportFirst
  rw [if_pos hx]

theorem exportFirst_neg {h : Hour 𝕜} (hx : ¬h.cv < h.p - h.τx) : exportFirst h = 0 := by
  unfold exportFirst
  rw [if_neg hx]

theorem mineAfter_pos {h : Hour 𝕜} (hm : h.cv < h.ν) :
    mineAfter h = min (surplus h - exportFirst h) h.M := by
  unfold mineAfter
  rw [if_pos hm]

theorem mineAfter_neg {h : Hour 𝕜} (hm : ¬h.cv < h.ν) : mineAfter h = 0 := by
  unfold mineAfter
  rw [if_neg hm]

/-- Value of the outlets: no admissible pair `(m, x)` is worth more than the pair of the merit order.
The unit values are the margins over the avoidable generation cost. -/
theorem outlets_value_le (h : Hour 𝕜) (hM : 0 ≤ h.M) (hX : 0 ≤ h.X) {m x : 𝕜}
    (hm0 : 0 ≤ m) (hmM : m ≤ h.M) (hx0 : 0 ≤ x) (hxX : x ≤ h.X) (hmx : m + x ≤ surplus h) :
    (h.ν - h.cv) * m + (h.p - h.τx - h.cv) * x ≤
      (h.ν - h.cv) * mined h + (h.p - h.τx - h.cv) * exported h := by
  unfold mined exported
  split_ifs with hfirst
  · -- mining pays at least as much as export and is served first
    by_cases hm : h.cv < h.ν
    · by_cases hx : h.cv < h.p - h.τx
      · simp only [mineFirst_pos hm, exportAfter_pos hx]
        exact greedy_both (by linarith) (by linarith) hX hmM hx0 hxX hmx
      · simp only [mineFirst_pos hm, exportAfter_neg hx, mul_zero, add_zero]
        exact greedy_first (by linarith) (by linarith [not_lt.1 hx]) hmM hx0 hmx
    · have hx : ¬h.cv < h.p - h.τx := fun hx => hm (lt_of_lt_of_le hx hfirst)
      simp only [mineFirst_neg hm, exportAfter_neg hx, mul_zero, add_zero]
      exact greedy_none (by linarith [not_lt.1 hm]) (by linarith [not_lt.1 hx]) hm0 hx0
  · -- export pays more than mining and is served first
    have hlt : h.ν < h.p - h.τx := not_le.1 hfirst
    by_cases hx : h.cv < h.p - h.τx
    · by_cases hm : h.cv < h.ν
      · simp only [exportFirst_pos hx, mineAfter_pos hm]
        have key := greedy_both (α := h.p - h.τx - h.cv) (β := h.ν - h.cv) (U := h.X) (V := h.M)
          (S := surplus h) (u := x) (v := m) (by linarith) (by linarith) hM hxX hm0 hmM
          (by linarith)
        linarith
      · simp only [exportFirst_pos hx, mineAfter_neg hm, mul_zero, zero_add]
        have key := greedy_first (α := h.p - h.τx - h.cv) (β := h.ν - h.cv) (U := h.X)
          (S := surplus h) (u := x) (v := m) (by linarith) (by linarith [not_lt.1 hm]) hxX hm0
          (by linarith)
        linarith
    · have hm : ¬h.cv < h.ν := fun hm => hx (lt_trans hm hlt)
      simp only [exportFirst_neg hx, mineAfter_neg hm, mul_zero, add_zero]
      exact greedy_none (by linarith [not_lt.1 hm]) (by linarith [not_lt.1 hx]) hm0 hx0

/-- Value of the firming resources: no admissible pair `(b1, g)` saves more emergency generation
cost than the pair of the merit order. The unit values are the savings relative to emergency
generation. -/
theorem firming_value_le (h : Hour 𝕜) (ho : h.Ordered) (hGi : 0 ≤ h.Gi) {b1 g : 𝕜}
    (hb10 : 0 ≤ b1) (hb1B : b1 ≤ h.B1) (hg0 : 0 ≤ g) (hgG : g ≤ h.Gi)
    (hsum : b1 + g ≤ shortfall h) :
    (h.cb - h.c1) * b1 + (h.cb - (h.p + h.τg)) * g ≤
      (h.cb - h.c1) * tier1 h + (h.cb - (h.p + h.τg)) * imports h := by
  obtain ⟨hc, hT⟩ := ho
  have hα : 0 ≤ h.cb - h.c1 := sub_nonneg.2 hc
  have ht := tier1_le_shortfall h
  by_cases hq : h.p + h.τg ≤ h.cb
  · -- imports cost no more than emergency generation
    have hβ : 0 ≤ h.cb - (h.p + h.τg) := sub_nonneg.2 hq
    have hi : imports h = min (shortfall h - tier1 h) h.Gi := by
      unfold imports
      rw [if_pos hq]
    rcases hT with hB | hG | hord
    · -- no tier-1 resource: imports cover the shortfall up to their limit
      have hb1 : b1 = 0 := by
        rw [hB] at hb1B
        linarith
      have ht0 : tier1 h = 0 := by
        unfold tier1
        rw [hB]
        exact min_eq_right (shortfall_nonneg h)
      have hg' : g ≤ min (shortfall h) h.Gi := le_min (by linarith) hgG
      have key := mul_le_mul_of_nonneg_left hg' hβ
      rw [hi, ht0, sub_zero, hb1]
      linarith
    · -- no grid import: the tier-1 resource covers the shortfall up to its limit
      have hg : g = 0 := by
        rw [hG] at hgG
        linarith
      have hi0 : imports h = 0 := by
        rw [hi, hG]
        exact min_eq_right (sub_nonneg.2 ht)
      have hb1' : b1 ≤ tier1 h := le_min (by linarith) hb1B
      have key := mul_le_mul_of_nonneg_left hb1' hα
      rw [hi0, hg]
      linarith
    · -- both are available and the tier-1 resource is the cheaper one
      rw [hi]
      exact greedy_both (α := h.cb - h.c1) (β := h.cb - (h.p + h.τg)) (U := h.B1) (V := h.Gi)
        (S := shortfall h) hβ (by linarith) hGi hb1B hg0 hgG hsum
  · -- imports cost more than emergency generation and are not used
    have hi : imports h = 0 := by
      unfold imports
      rw [if_neg hq]
    rw [hi, mul_zero, add_zero]
    exact greedy_first (α := h.cb - h.c1) (β := h.cb - (h.p + h.τg)) (U := h.B1)
      (S := shortfall h) hα (by linarith [not_le.1 hq]) hb1B hg0 hsum

/-- With no surplus the merit order serves neither the mine nor the export. -/
theorem outlets_of_surplus_zero (h : Hour 𝕜) (hS : surplus h = 0) (hM : 0 ≤ h.M) (hX : 0 ≤ h.X) :
    mined h = 0 ∧ exported h = 0 := by
  have h1 : mineFirst h = 0 := by
    by_cases hm : h.cv < h.ν
    · rw [mineFirst_pos hm, hS]
      exact min_eq_left hM
    · exact mineFirst_neg hm
  have h2 : exportFirst h = 0 := by
    by_cases hx : h.cv < h.p - h.τx
    · rw [exportFirst_pos hx, hS]
      exact min_eq_left hX
    · exact exportFirst_neg hx
  have h3 : exportAfter h = 0 := by
    by_cases hx : h.cv < h.p - h.τx
    · rw [exportAfter_pos hx, hS, h1, sub_zero]
      exact min_eq_left hX
    · exact exportAfter_neg hx
  have h4 : mineAfter h = 0 := by
    by_cases hm : h.cv < h.ν
    · rw [mineAfter_pos hm, hS, h2, sub_zero]
      exact min_eq_left hM
    · exact mineAfter_neg hm
  constructor
  · unfold mined
    split_ifs
    · exact h1
    · exact h4
  · unfold exported
    split_ifs
    · exact h3
    · exact h2

/-- Optimality in an hour without shortfall: the problem reduces to sharing the surplus between
the mine and the export. -/
theorem optimal_of_surplus (h : Hour 𝕜) (hLP : h.L ≤ h.P) {d : Plan 𝕜} (hd : Feasible h d) :
    margin h d ≤ margin h (meritOrder h) := by
  have hM : 0 ≤ h.M := le_trans hd.m_nonneg hd.m_le
  have hX : 0 ≤ h.X := le_trans hd.x_nonneg hd.x_le
  have hGi : 0 ≤ h.Gi := le_trans hd.g_nonneg hd.g_le
  have hB1 : 0 ≤ h.B1 := le_trans hd.b1_nonneg hd.b1_le
  obtain ⟨hg, hb1, hb⟩ := hd.firming_zero hLP
  have hs : shortfall h = 0 := shortfall_of_le hLP
  have hG : d.G = h.L + d.m + d.x := by
    have h1 := hd.balance
    rw [hg, hb1, hb] at h1
    linarith
  -- the merit order uses no firming resource either
  have ht : tier1 h = 0 := by
    unfold tier1
    rw [hs]
    exact min_eq_left hB1
  have hi : imports h = 0 := by
    unfold imports
    by_cases hq : h.p + h.τg ≤ h.cb
    · rw [if_pos hq, hs, ht, sub_zero]
      exact min_eq_left hGi
    · exact if_neg hq
  have he : emergency h = 0 := by
    have hE : emergency h = shortfall h - tier1 h - imports h := rfl
    linarith
  have key := outlets_value_le h hM hX hd.m_nonneg hd.m_le hd.x_nonneg hd.x_le
    hd.outlets_le_surplus
  have e1 : margin h d
      = (h.ν - h.cv) * d.m + (h.p - h.τx - h.cv) * d.x - h.cv * h.L := by
    unfold margin
    rw [hG, hg, hb1, hb]
    ring
  have e2 : margin h (meritOrder h)
      = (h.ν - h.cv) * mined h + (h.p - h.τx - h.cv) * exported h - h.cv * h.L := by
    simp only [margin, meritOrder_G, meritOrder_m, meritOrder_x, meritOrder_g, meritOrder_b1,
      meritOrder_b]
    rw [hs, hi, ht, he]
    ring
  rw [e1, e2]
  linarith

/-- Optimality in an hour with shortfall: the problem reduces to covering the shortfall at the
lowest cost. -/
theorem optimal_of_shortfall (h : Hour 𝕜) (hPL : h.P < h.L) (ho : h.Ordered) {d : Plan 𝕜}
    (hd : Feasible h d) : margin h d ≤ margin h (meritOrder h) := by
  have hM : 0 ≤ h.M := le_trans hd.m_nonneg hd.m_le
  have hX : 0 ≤ h.X := le_trans hd.x_nonneg hd.x_le
  have hGi : 0 ≤ h.Gi := le_trans hd.g_nonneg hd.g_le
  obtain ⟨hm, hx, hG, hsum⟩ := hd.outlets_zero hPL
  have hs : shortfall h = h.L - h.P := shortfall_of_lt hPL
  obtain ⟨hmq, hxq⟩ := outlets_of_surplus_zero h (surplus_of_lt hPL) hM hX
  have hb : d.b = h.L - h.P - d.g - d.b1 := by linarith
  have hsum' : d.b1 + d.g ≤ shortfall h := by
    have h1 := hd.b_nonneg
    rw [hs]
    linarith
  have key := firming_value_le h ho hGi hd.b1_nonneg hd.b1_le hd.g_nonneg hd.g_le hsum'
  have hE : emergency h = shortfall h - tier1 h - imports h := rfl
  have e1 : margin h d
      = (h.cb - h.c1) * d.b1 + (h.cb - (h.p + h.τg)) * d.g - h.cv * h.P - h.cb * (h.L - h.P) := by
    unfold margin
    rw [hm, hx, hG, hb]
    ring
  have e2 : margin h (meritOrder h)
      = (h.cb - h.c1) * tier1 h + (h.cb - (h.p + h.τg)) * imports h - h.cv * h.P
        - h.cb * (h.L - h.P) := by
    simp only [margin, meritOrder_G, meritOrder_m, meritOrder_x, meritOrder_g, meritOrder_b1,
      meritOrder_b]
    rw [hE, hmq, hxq, hs]
    ring
  rw [e1, e2]
  linarith

/-- **Optimality.** Under the order of the firming resources stated in `Hour.Ordered`, no feasible
dispatch earns a larger operating margin than the merit order. Together with `meritOrder_feasible`
this shows that the rule (S12)–(S20) solves the linear programme (S3)–(S11) of the hour. -/
theorem meritOrder_optimal (h : Hour 𝕜) (ho : h.Ordered) {d : Plan 𝕜} (hd : Feasible h d) :
    margin h d ≤ margin h (meritOrder h) := by
  rcases lt_or_ge h.P h.L with hPL | hLP
  · exact optimal_of_shortfall h hPL ho hd
  · exact optimal_of_surplus h hLP hd

/-- **The whole horizon.** No constraint of (S4)–(S11) links two hours, so a dispatch of a set of
hours `T` is feasible exactly when it is feasible hour by hour, and the merit order maximises the
objective (S3), the sum of the hourly margins. -/
theorem horizon_optimal {ι : Type*} (T : Finset ι) (h : ι → Hour 𝕜) (ho : ∀ t ∈ T, (h t).Ordered)
    (d : ι → Plan 𝕜) (hd : ∀ t ∈ T, Feasible (h t) (d t)) :
    ∑ t ∈ T, margin (h t) (d t) ≤ ∑ t ∈ T, margin (h t) (meritOrder (h t)) :=
  Finset.sum_le_sum fun t ht => meritOrder_optimal (h t) (ho t ht) (hd t ht)

/-! ## Consequences used in the article -/

/-- Condition (15) of the article: the merit order mines only when the mining netback exceeds the
avoidable generation cost. -/
theorem mining_only_if_profitable (h : Hour 𝕜) (hm : 0 < (meritOrder h).m) : h.cv < h.ν := by
  by_contra hc
  have h0 : (meritOrder h).m = 0 := by
    rw [meritOrder_m]
    unfold mined
    split_ifs
    · exact mineFirst_neg hc
    · exact mineAfter_neg hc
  rw [h0] at hm
  exact lt_irrefl _ hm

/-- Condition (16) of the article: the merit order exports only when the net export price exceeds
the avoidable generation cost. -/
theorem export_only_if_profitable (h : Hour 𝕜) (hx : 0 < (meritOrder h).x) :
    h.cv < h.p - h.τx := by
  by_contra hc
  have h0 : (meritOrder h).x = 0 := by
    rw [meritOrder_x]
    unfold exported
    split_ifs
    · exact exportAfter_neg hc
    · exact exportFirst_neg hc
  rw [h0] at hx
  exact lt_irrefl _ hx

/-- **Mining capacity never lowers the operating margin.** With more mining capacity the optimal
margin of the hour is at least as large; in particular a plant with a mine never earns less in an
hour than the same plant without it (`h.M = 0`). -/
theorem margin_mono_mining (h : Hour 𝕜) (hv : h.Valid) (ho : h.Ordered) {M' : 𝕜} (hM : h.M ≤ M') :
    margin h (meritOrder h) ≤ margin { h with M := M' } (meritOrder { h with M := M' }) := by
  have hf := meritOrder_feasible h hv
  have hf' : Feasible { h with M := M' } (meritOrder h) :=
    { balance := hf.balance, G_nonneg := hf.G_nonneg, G_le := hf.G_le, m_nonneg := hf.m_nonneg,
      m_le := le_trans hf.m_le hM, x_nonneg := hf.x_nonneg, x_le := hf.x_le,
      b1_nonneg := hf.b1_nonneg, b1_le := hf.b1_le, g_nonneg := hf.g_nonneg, g_le := hf.g_le,
      b_nonneg := hf.b_nonneg, firm_le := hf.firm_le }
  exact meritOrder_optimal { h with M := M' } ho hf'

/-- The statement for real-valued data, in the form used in the Supplementary Material: the
merit-order dispatch is feasible and maximises the operating margin of the hour. -/
theorem meritOrder_solves_real (h : Hour ℝ) (hv : h.Valid) (ho : h.Ordered) :
    Feasible h (meritOrder h) ∧ ∀ d : Plan ℝ, Feasible h d → margin h d ≤ margin h (meritOrder h) :=
  ⟨meritOrder_feasible h hv, fun _ hd => meritOrder_optimal h ho hd⟩

/-! ## The hypothesis on the tier-1 resource is needed -/

/-- If a tier-1 resource is available together with grid imports and costs more than imports, the rule
(S12)–(S14), which always calls the tier-1 resource first, is feasible but not optimal. Example: a
shortfall of 1 MW, a tier-1 resource at 50, imports at 10 and emergency generation at 100 per MWh.
The condition in `Hour.Ordered` can therefore not be dropped. -/
theorem ordering_condition_needed :
    ∃ (h : Hour ℚ) (d : Plan ℚ), h.Valid ∧ h.c1 ≤ h.cb ∧ Feasible h d ∧
      margin h (meritOrder h) < margin h d := by
  refine ⟨{ P := 0, L := 1, M := 0, X := 0, Gi := 1, B1 := 1, ν := 0, p := 10, τx := 0, τg := 0,
            cv := 0, c1 := 50, cb := 100 },
          { G := 0, m := 0, x := 0, g := 1, b1 := 0, b := 0 }, ?_, ?_, ?_, ?_⟩
  · exact
      { P_nonneg := by norm_num, L_nonneg := by norm_num, M_nonneg := by norm_num,
        X_nonneg := by norm_num, Gi_nonneg := by norm_num, B1_nonneg := by norm_num }
  · norm_num
  · exact
      { balance := by norm_num, G_nonneg := by norm_num, G_le := by norm_num,
        m_nonneg := by norm_num, m_le := by norm_num, x_nonneg := by norm_num,
        x_le := by norm_num, b1_nonneg := by norm_num, b1_le := by norm_num,
        g_nonneg := by norm_num, g_le := by norm_num, b_nonneg := by norm_num,
        firm_le := by norm_num [shortfall, max_def] }
  · norm_num [margin, meritOrder, shortfall, surplus, tier1, imports, emergency, mined, exported,
      mineFirst, exportAfter, exportFirst, mineAfter, max_def, min_def]

end SMR.Dispatch
