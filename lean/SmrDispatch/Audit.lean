/-
Audit of the formalisation: `lake build` prints, for each main theorem, the axioms on which its proof
depends. The expected answer is the three standard axioms of Lean with Mathlib
(`propext`, `Classical.choice`, `Quot.sound`) and nothing else; `sorryAx` must not appear.
-/
import SmrDispatch.Dispatch

open SMR.Dispatch

#print axioms meritOrder_feasible
#print axioms meritOrder_optimal
#print axioms horizon_optimal
#print axioms Feasible.nuclear_only
#print axioms mining_only_if_profitable
#print axioms export_only_if_profitable
#print axioms margin_mono_mining
#print axioms meritOrder_solves_real
#print axioms ordering_condition_needed
