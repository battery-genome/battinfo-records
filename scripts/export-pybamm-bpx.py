#!/usr/bin/env python3
"""Export PyBaMM's built-in parameter sets as BPX files, and check each export by simulation.

Each file is the inverse of PyBaMM's own BPX importer (pybamm/parameters/bpx.py), so importing it
gives back the native model as closely as BPX can express it:

- functions of stoichiometry or electrolyte concentration become tables at the reference
  temperature; their temperature dependence becomes an Arrhenius activation energy fitted from
  the function itself;
- the exchange-current density becomes BPX's normalised reaction rate constant;
- electrode conductivity becomes BPX's effective value, sigma * (1 - porosity)^b, since the
  importer sets the solid Bruggeman coefficient to 0; electrolyte Bruggeman coefficients become
  transport efficiencies;
- the stoichiometry window comes from PyBaMM's electrode state-of-health calculation, and the
  initial state of charge from the set's initial concentrations;
- a negative electrode with two particle phases (graphite and silicon) becomes a BPX blended
  electrode, each phase with its own stoichiometry window and its hysteresis branches.

Thermal properties are not exported, so the files run isothermally. A set whose functions BPX
cannot express exactly (a temperature dependence that is not Arrhenius, a thermodynamic factor
other than 1, an exchange-current form other than BPX's) is exported anyway and the difference
shows in the check: the native set and the BPX file run the standard protocol's discharges
(simulation_protocol.py: every standard C-rate, and 1C 20 K warmer), and the voltage and
capacity differences are reported.

    uv run --no-project --with "pybamm[bpx]==26.10.1.1" python scripts/export-pybamm-bpx.py --out ../bpx-exports
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import traceback
from pathlib import Path

import numpy as np
import pybamm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import simulation_protocol as protocol  # noqa: E402

# PyBaMM's parameter sets that already have records in the registry (their half-cell OCP claims, from
# the literature_ocv library). Ai2020 is exported for its check only: BPX has no thermodynamic factor.
SETS = {
    "Chen2020": {"citation": "10.1149/1945-7111/ab9050", "model": "DFN",
                 "about": "an LG M50 cell (Chen et al. 2020)"},
    "Chen2020_composite": {"citation": "10.1016/j.jpowsour.2022.231142", "references": ("10.1149/1945-7111/ab9050",),
                           "model": "DFN", "phases": {"negative": ("Graphite", "Silicon")},
                           "about": "an LG M50 cell with a graphite and silicon negative electrode (Ai et al. 2022, "
                                    "after Chen et al. 2020)"},
    "Mohtat2020": {"citation": "10.1149/1945-7111/aba5d1", "model": "DFN", "initial_soc": 1.0,
                   "about": "a graphite/NMC532 pouch cell (Mohtat et al. 2020)"},
    "Ai2020": {"citation": "10.1149/2.0122001JES", "model": "DFN",
               "about": "an Enertech graphite/LCO pouch cell (Ai et al. 2020)"},
    "Prada2013": {"citation": "10.1149/2.053304jes", "model": "DFN",
                  "about": "an LFP cell (Prada et al. 2013), with Chen2020's graphite OCP and exchange-current density"},
}
PHASES = ("Primary: ", "Secondary: ")  # PyBaMM's prefixes for the two phases of a blended electrode
ELECTRODE_KEYS = ("Thickness [m]", "Conductivity [S.m-1]", "Porosity", "Transport efficiency")
WARM_CHECK = 20.0  # K above the reference temperature, for one 1C run that tests the activation energies
WINDOW_MARGIN = 0.05  # functions of stoichiometry are tabled over the stoichiometry window plus this margin
OCP_BOUNDS = {"negative": (0.0, 3.0), "positive": (2.0, 5.0)}  # V; plausible open-circuit potentials vs Li
C_E = np.linspace(1.0, 4000.0, 300)
DELTA_T = 10.0  # K above the reference temperature, to fit activation energies
R = 8.314462618


def digits(values) -> list[float]:
    return [float(f"{v:.10g}") for v in np.asarray(values, dtype=float).ravel()]


def evaluate(pv: pybamm.ParameterValues, name: str, *args) -> np.ndarray:
    """A parameter at numeric arguments (arrays broadcast), whether it is a number, a table or a function."""
    value = pv[name]
    shape = np.broadcast(*[np.asarray(a) for a in args]).shape if args else ()
    if isinstance(value, (int, float)):
        return np.full(shape, float(value))
    if isinstance(value, tuple):  # (name, (x, y)) interpolant data, one input
        x, y = value[1]
        x = np.asarray(x[0] if isinstance(x, (tuple, list)) and np.ndim(x[0]) else x, dtype=float).ravel()
        return np.interp(np.asarray(args[0], dtype=float), x, np.asarray(y, dtype=float).ravel())
    symbols = [pybamm.Vector(np.asarray(a, dtype=float).ravel()) if np.ndim(a) else pybamm.Scalar(float(a)) for a in args]
    out = value(*symbols)
    if isinstance(out, pybamm.Symbol):
        out = pv.process_symbol(out).evaluate()
    out = np.asarray(out, dtype=float).ravel()
    return np.broadcast_to(out if out.size > 1 else float(out[0]), shape).copy()


def scalar(pv: pybamm.ParameterValues, name: str, notes: list[str], at: dict) -> float:
    """A parameter BPX holds as one number. A function is taken at the reference conditions, with a note."""
    value = pv[name]
    if isinstance(value, (int, float)):
        return float(value)
    if callable(value):
        import inspect

        args = [at[arg] for arg in inspect.signature(value).parameters]
        result = float(evaluate(pv, name, *args))
        where = ", ".join(f"{k} = {at[k]:g}" for k in inspect.signature(value).parameters)
        notes.append(f"PyBaMM's {name} is a function; the file holds its value at {where}.")
        return result
    return float(pv.evaluate(pybamm.Parameter(name)))


def first(pv: pybamm.ParameterValues, *names: str) -> str:
    for name in names:
        if name in pv.keys():
            return name
    raise KeyError(names[0])


def function_of_one(pv, name, grid, T_ref, extra_args=()):
    """Table (or constant) at T_ref plus an Arrhenius activation energy; the spread says how well that fits."""
    at_ref = evaluate(pv, name, grid, *extra_args, T_ref)
    hot = evaluate(pv, name, grid, *extra_args, T_ref + DELTA_T)
    finite = np.isfinite(at_ref) & np.isfinite(hot) & (at_ref > 0) & (hot > 0)
    ratios = np.log(hot[finite] / at_ref[finite])
    ea_values = R * ratios / (1 / T_ref - 1 / (T_ref + DELTA_T))
    ea = float(np.median(ea_values)) if len(ea_values) else 0.0
    spread = float(np.ptp(ea_values)) if len(ea_values) else 0.0
    if np.allclose(at_ref, at_ref[0], rtol=1e-9, atol=0):
        return float(f"{at_ref[0]:.10g}"), ea, spread
    keep = np.isfinite(at_ref) & (at_ref > 0)
    return {"x": digits(grid[keep]), "y": digits(at_ref[keep])}, ea, spread


def cell_geometry(pv: pybamm.ParameterValues, notes: list[str]) -> tuple[float, float]:
    """Cooling surface and volume; derived from the electrode stack when the set has none."""
    keys = pv.keys()
    if "Cell cooling surface area [m2]" in keys and "Cell volume [m3]" in keys:
        return float(pv["Cell cooling surface area [m2]"]), float(pv["Cell volume [m3]"])
    area = float(pv["Electrode height [m]"]) * float(pv["Electrode width [m]"])
    pairs = float(pv["Number of electrodes connected in parallel to make a cell"])
    layers = ["Negative electrode thickness [m]", "Separator thickness [m]", "Positive electrode thickness [m]",
              "Negative current collector thickness [m]", "Positive current collector thickness [m]"]
    stack = sum(float(pv[name]) for name in layers if name in keys)
    notes.append("The cell surface area and volume are not in the PyBaMM set. They are derived from the "
                 "electrode stack, and only thermal models use them.")
    return float(f"{2 * area * pairs:.10g}"), float(f"{area * stack * pairs:.10g}")


def electrode(pv, side: str, T_ref: float, c_e0: float, windows: list[tuple[float, float]], notes: list[str],
              labels: tuple[str, ...] = ()) -> dict:
    """One electrode; given phase labels, a blended electrode whose particle phases carry those names."""
    if not labels:
        return electrode_phase(pv, side, "", side, T_ref, c_e0, windows[0], notes)
    phases = [electrode_phase(pv, side, prefix, f"{side} {label.lower()}", T_ref, c_e0, window, notes)
              for prefix, label, window in zip(PHASES, labels, windows, strict=True)]
    out = {key: phases[0][key] for key in ELECTRODE_KEYS}
    out["Particle"] = {label: {k: v for k, v in phase.items() if k not in ELECTRODE_KEYS}
                       for label, phase in zip(labels, phases)}
    return out


def electrode_phase(pv, side: str, phase: str, label: str, T_ref: float, c_e0: float,
                    window: tuple[float, float], notes: list[str]) -> dict:
    """An electrode with one particle phase (phase "" when it has only one); label names it in notes."""
    Side = side.capitalize()
    electrode_prefix = f"{Side} electrode "
    prefix = f"{phase}{Side} electrode "
    c_max = float(pv[f"{phase}Maximum concentration in {side} electrode [mol.m-3]"])
    porosity = float(pv[f"{electrode_prefix}porosity"])
    radius = float(pv[f"{phase}{Side} particle radius [m]"])
    am_fraction = float(pv[f"{prefix}active material volume fraction"])
    b_e = float(pv[f"{electrode_prefix}Bruggeman coefficient (electrolyte)"])
    b_s = float(pv[f"{electrode_prefix}Bruggeman coefficient (electrode)"])
    sto = np.linspace(max(0.0, window[0] - WINDOW_MARGIN), min(1.0, window[1] + WINDOW_MARGIN), 401)

    # OCP at the reference temperature; the importer adds (T - T_ref) * entropic change.
    ocp_name = f"{prefix}OCP [V]"
    try:
        ocp = evaluate(pv, ocp_name, sto)
    except TypeError:
        ocp = evaluate(pv, ocp_name, sto, T_ref)
    # Fitted OCP functions diverge near 0 or 1, outside their validity: keep the stretch around the
    # window where the OCP stays plausible for the electrode.
    low, high = OCP_BOUNDS[side]
    plausible = np.isfinite(ocp) & (ocp > low) & (ocp < high)
    centre = int(np.argmin(np.abs(sto - (window[0] + window[1]) / 2)))
    if not plausible[centre]:
        raise ValueError(f"{label} OCP is outside {low}-{high} V in the middle of its stoichiometry window")
    first_kept, last_kept = centre, centre
    while first_kept > 0 and plausible[first_kept - 1]:
        first_kept -= 1
    while last_kept < len(sto) - 1 and plausible[last_kept + 1]:
        last_kept += 1
    if sto[first_kept] > window[0] or sto[last_kept] < window[1]:
        notes.append(f"The {label} OCP stays within {low}-{high} V only from {sto[first_kept]:.3f} to {sto[last_kept]:.3f}.")
    keep = np.zeros(len(sto), dtype=bool)
    keep[first_kept:last_kept + 1] = True
    out = {
        "Particle radius [m]": radius,
        "Thickness [m]": float(pv[f"{electrode_prefix}thickness [m]"]),
        "OCP [V]": {"x": digits(sto[keep]), "y": digits(ocp[keep])},
        "Conductivity [S.m-1]": float(
            f"{scalar(pv, f'{electrode_prefix}conductivity [S.m-1]', notes, {'sto': 0.5, 'T': T_ref}) * (1 - porosity) ** b_s:.10g}"
        ),
        "Surface area per unit volume [m-1]": float(f"{3 * am_fraction / radius:.10g}"),
        "Porosity": porosity,
        "Transport efficiency": float(f"{porosity ** b_e:.10g}"),
        "Minimum stoichiometry": window[0],
        "Maximum stoichiometry": window[1],
        "Maximum concentration [mol.m-3]": c_max,
    }
    # Hysteresis branches, over the OCP's stoichiometries. The standard runs use the OCP above; the
    # branches are for a hysteresis model.
    for branch, bpx_name in (("lithiation", "OCP (lithiation) [V]"), ("delithiation", "OCP (delithiation) [V]")):
        if f"{prefix}{branch} OCP [V]" in pv.keys():
            values = evaluate(pv, f"{prefix}{branch} OCP [V]", sto[keep])
            if not np.all(np.isfinite(values)):
                raise ValueError(f"the {label} {branch} OCP is not finite over the OCP's stoichiometries")
            out[bpx_name] = {"x": digits(sto[keep]), "y": digits(values)}

    # Always written: PyBaMM's importer needs it, and a set without one has none (0).
    out["Entropic change coefficient [V.K-1]"] = 0.0
    entropic_name = f"{prefix}OCP entropic change [V.K-1]"
    if entropic_name in pv.keys():
        try:
            entropic = evaluate(pv, entropic_name, sto)
        except TypeError:
            entropic = evaluate(pv, entropic_name, sto, c_max)
        if np.any(np.abs(entropic[np.isfinite(entropic)]) > 0):
            keep = np.isfinite(entropic)
            out["Entropic change coefficient [V.K-1]"] = {"x": digits(sto[keep]), "y": digits(entropic[keep])}

    diffusivity_name = first(pv, f"{phase}{Side} particle diffusivity [m2.s-1]", f"{prefix}diffusivity [m2.s-1]")
    diffusivity, ea_d, spread = function_of_one(pv, diffusivity_name, sto, T_ref)
    out["Diffusivity [m2.s-1]"] = diffusivity
    out["Diffusivity activation energy [J.mol-1]"] = float(f"{ea_d:.10g}")
    if spread > 1:
        notes.append(f"The {label} diffusivity does not follow an Arrhenius law (activation energies spread over {spread:.0f} J/mol).")

    # Exchange-current density j0(c_e, c_s, c_max, T) -> BPX k_norm, with the importer's
    # j0 = k_norm * F / (c_max * sqrt(c_e0)) * arrhenius * sqrt(c_e * c_s * (c_max - c_s)).
    j0_name = f"{prefix}exchange-current density [A.m-2]"
    c_s = c_max * np.linspace(0.05, 0.95, 19)
    shape = np.sqrt(c_e0 * c_s * (c_max - c_s))
    j0_ref = evaluate(pv, j0_name, c_e0, c_s, c_max, T_ref)
    j0_hot = evaluate(pv, j0_name, c_e0, c_s, c_max, T_ref + DELTA_T)
    k_values = j0_ref / shape
    k = float(np.median(k_values))
    k_half = evaluate(pv, j0_name, c_e0 / 2, c_s, c_max, T_ref) / np.sqrt(c_e0 / 2 * c_s * (c_max - c_s))
    k_values = np.concatenate([k_values, k_half])
    if np.ptp(k_values) > 1e-6 * abs(k):
        notes.append(f"The {label} exchange-current density is not of BPX's form (its rate constant varies by {np.ptp(k_values) / abs(k):.1%}).")
    ea_k = float(np.median(R * np.log(j0_hot / j0_ref) / (1 / T_ref - 1 / (T_ref + DELTA_T))))
    out["Reaction rate constant [mol.m-2.s-1]"] = float(f"{k * c_max * math.sqrt(c_e0) / pybamm.constants.F.value:.10g}")
    out["Reaction rate constant activation energy [J.mol-1]"] = float(f"{ea_k:.10g}")
    return out


def export(name: str) -> tuple[dict, list[str]]:
    pv = pybamm.ParameterValues(name)
    notes: list[str] = []
    T_ref = float(pv["Reference temperature [K]"])
    c_e0 = float(pv["Initial concentration in electrolyte [mol.m-3]"])
    labels = SETS[name].get("phases", {})
    if labels.get("positive"):
        raise NotImplementedError("only the negative electrode can have two particle phases")
    c_p0 = float(pv["Initial concentration in positive electrode [mol.m-3]"])
    if labels.get("negative"):
        # Each phase's window from PyBaMM's composite state-of-health calculation: the stoichiometries
        # at which the phases share one potential at 0% and at 100% state of charge.
        options = {"particle phases": ("2", "1")}
        full = pv.set_initial_state(1.0, options=options, inplace=False)
        empty = pv.set_initial_state(0.0, options=options, inplace=False)

        def sto(values, phase, side):
            c = float(values[f"{phase}Initial concentration in {side} electrode [mol.m-3]"])
            return float(f"{c / float(values[f'{phase}Maximum concentration in {side} electrode [mol.m-3]']):.7g}")

        negative_windows = [(sto(empty, phase, "negative"), sto(full, phase, "negative")) for phase in PHASES]
        y100, y0 = sto(full, "", "positive"), sto(empty, "", "positive")
        # The phases' initial concentrations need not share one potential, so the state of charge is
        # read from the single-phase positive electrode.
        soc = (y0 - c_p0 / float(pv["Maximum concentration in positive electrode [mol.m-3]"])) / (y0 - y100)
    else:
        x0, x100, y100, y0 = (float(f"{v:.7g}") for v in pybamm.lithium_ion.get_min_max_stoichiometries(pv))
        negative_windows = [(x0, x100)]
        c_n0 = float(pv["Initial concentration in negative electrode [mol.m-3]"])
        soc = (c_n0 / float(pv["Maximum concentration in negative electrode [mol.m-3]"]) - x0) / (x100 - x0)
        soc_p = (y0 - c_p0 / float(pv["Maximum concentration in positive electrode [mol.m-3]"])) / (y0 - y100)
        if abs(soc - soc_p) > 0.01:
            notes.append(f"The electrodes give different initial states of charge ({soc:.3f} and {soc_p:.3f}); the negative's is used.")
    if not 0.0 <= soc <= 1.0:
        notes.append(f"PyBaMM's initial concentrations give a state of charge of {soc:.4f}, clipped to [0, 1].")
    soc = min(1.0, max(0.0, soc))
    if "initial_soc" in SETS[name]:
        notes.append(f"PyBaMM's {name} starts at a state of charge of {soc:.4f}. The file starts it at "
                     f"{SETS[name]['initial_soc']:g}, so that the standard discharges have charge to deliver.")
        soc = SETS[name]["initial_soc"]

    thermodynamic_factor = pv["Thermodynamic factor"] if "Thermodynamic factor" in pv.keys() else 1.0
    if not (isinstance(thermodynamic_factor, (int, float)) and float(thermodynamic_factor) == 1.0):
        notes.append("PyBaMM's thermodynamic factor is not 1, and BPX assumes 1.")

    conductivity, ea_sigma, spread_sigma = function_of_one(pv, "Electrolyte conductivity [S.m-1]", C_E, T_ref)
    diffusivity, ea_de, spread_de = function_of_one(pv, "Electrolyte diffusivity [m2.s-1]", C_E, T_ref)
    for label, spread in (("electrolyte conductivity", spread_sigma), ("electrolyte diffusivity", spread_de)):
        if spread > 1:
            notes.append(f"The {label} does not follow an Arrhenius law (activation energies spread over {spread:.0f} J/mol).")

    separator_porosity = float(pv["Separator porosity"])
    if separator_porosity >= 1.0:
        # PyBaMM's BPX importer takes log(transport efficiency) / log(porosity), so porosity 1 fails.
        separator_porosity = 1 - 1e-9
        notes.append("The separator porosity is 1 in PyBaMM. It is written as 1 - 1e-9 because PyBaMM's BPX importer "
                     "divides by its logarithm.")
    geometry = cell_geometry(pv, notes)
    bpx = {
        "Header": {
            "BPX": "1.1.0",
            "Title": f"{name} (PyBaMM)",
            "Description": (
                f"PyBaMM {pybamm.__version__}'s {name} parameter set, for {SETS[name]['about']}. "
                "Exported to BPX by battinfo-records (scripts/export-pybamm-bpx.py)."
            ),
            "References": ", ".join(
                f"https://doi.org/{doi}" for doi in (SETS[name]["citation"], *SETS[name].get("references", ()))
            ),
            "Model": SETS[name]["model"],
        },
        "Parameterisation": {
            "Cell": {
                "Electrode area [m2]": float(f"{float(pv['Electrode height [m]']) * float(pv['Electrode width [m]']):.10g}"),
                "External surface area [m2]": geometry[0],
                "Volume [m3]": geometry[1],
                "Number of electrode pairs connected in parallel to make a cell": int(
                    pv["Number of electrodes connected in parallel to make a cell"]
                ),
                "Lower voltage cut-off [V]": float(pv["Lower voltage cut-off [V]"]),
                "Upper voltage cut-off [V]": float(pv["Upper voltage cut-off [V]"]),
                "Nominal cell capacity [A.h]": float(pv["Nominal cell capacity [A.h]"]),
                "Reference temperature [K]": T_ref,
            },
            "Electrolyte": {
                "Cation transference number": float(
                    f"{scalar(pv, 'Cation transference number', notes, {'c_e': c_e0, 'T': T_ref}):.10g}"
                ),
                "Conductivity [S.m-1]": conductivity,
                "Conductivity activation energy [J.mol-1]": float(f"{ea_sigma:.10g}"),
                "Diffusivity [m2.s-1]": diffusivity,
                "Diffusivity activation energy [J.mol-1]": float(f"{ea_de:.10g}"),
            },
            "Negative electrode": electrode(pv, "negative", T_ref, c_e0, negative_windows, notes,
                                           labels.get("negative", ())),
            "Positive electrode": electrode(pv, "positive", T_ref, c_e0, [(y100, y0)], notes),
            "Separator": {
                "Thickness [m]": float(pv["Separator thickness [m]"]),
                "Porosity": separator_porosity,
                "Transport efficiency": float(
                    f"{separator_porosity ** float(pv['Separator Bruggeman coefficient (electrolyte)']):.10g}"
                ),
            },
        },
        "State": {
            "Initial conditions": {
                "Initial state-of-charge": float(f"{soc:.7g}"),
                "Initial temperature [K]": float(pv["Initial temperature [K]"]),
                "Initial electrolyte concentration [mol.m-3]": c_e0,
            },
            "Thermal environment": {"Ambient temperature [K]": float(pv["Ambient temperature [K]"])},
        },
    }
    return bpx, list(dict.fromkeys(notes))  # a blended electrode's phases can repeat an electrode-level note


def discharge(parameter_values, model: str, options: dict, rate: float, current: float, lower: float,
              temperature: float | None = None):
    """One of the standard protocol's constant-current discharges (simulation_protocol.py)."""
    if temperature is not None:
        parameter_values = parameter_values.copy()
        parameter_values.update({"Ambient temperature [K]": temperature, "Initial temperature [K]": temperature})
    step = protocol.experiment_step({"c_rate": rate, "current_A": current}, lower)
    sim = pybamm.Simulation(protocol.model_for(model, options, False), parameter_values=parameter_values,
                            experiment=pybamm.Experiment([step]))
    solution = sim.solve()
    return solution["Discharge capacity [A.h]"].entries, solution["Voltage [V]"].entries


def check(name: str, bpx: dict) -> dict:
    """The standard protocol's discharges on the native set and on the file: voltage and capacity differences.

    The native set starts from its own initial concentrations, or, when the file starts it elsewhere,
    from the file's state of charge. PyBaMM's own concentrations need not put the phases of a blended
    electrode at one potential, while the file's state of charge does; both hold the same lithium.
    """
    model, _ = protocol.model_choice(bpx)
    options = protocol.model_options(bpx)
    native = pybamm.ParameterValues(name)
    if "initial_soc" in SETS[name]:
        native.set_initial_state(float(SETS[name]["initial_soc"]), options=options)
    imported = protocol.parameter_values(json.dumps(bpx).encode())
    cell = bpx["Parameterisation"]["Cell"]
    lower, nominal = float(cell["Lower voltage cut-off [V]"]), float(cell["Nominal cell capacity [A.h]"])
    warm = float(cell["Reference temperature [K]"]) + WARM_CHECK
    results = []
    for rate, temperature in [(rate, None) for rate in protocol.STANDARD_C_RATES] + [(1.0, warm)]:
        entry = {"c_rate": rate, **({"temperature_K": warm} if temperature else {})}
        current = round(rate * nominal, 6)
        try:
            q_native, v_native = discharge(native, model, options, rate, current, lower, temperature)
            q_bpx, v_bpx = discharge(imported, model, options, rate, current, lower, temperature)
        except Exception as exc:  # noqa: BLE001 - a run that fails is part of the check's result
            entry["error"] = f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"
            results.append(entry)
            continue
        common = np.linspace(0, min(q_native[-1], q_bpx[-1]), 200)[:-2]  # stop short of the cut-off knee
        difference = np.interp(common, q_bpx, v_bpx) - np.interp(common, q_native, v_native)
        entry.update(
            native_capacity_Ah=round(float(q_native[-1]), 5),
            bpx_capacity_Ah=round(float(q_bpx[-1]), 5),
            capacity_difference_percent=round((float(q_bpx[-1]) - float(q_native[-1])) / float(q_native[-1]) * 100, 3),
            voltage_rms_difference_mV=round(float(np.sqrt(np.mean(difference ** 2))) * 1000, 2),
            voltage_max_difference_mV=round(float(np.max(np.abs(difference))) * 1000, 2),
        )
        results.append(entry)
    return {"model": model, "options": options, "runs": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--only", nargs="*", help="set names, e.g. Chen2020 Mohtat2020")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    print(f"PyBaMM {pybamm.__version__}")
    failures = 0
    for name in args.only or SETS:
        try:
            bpx, notes = export(name)
            comparison = check(name, bpx)
            results = comparison["runs"]
        except Exception as exc:  # noqa: BLE001 - one set must not stop the others
            failures += 1
            where = traceback.extract_tb(exc.__traceback__)[-1]
            print(f"{name}: FAILED {type(exc).__name__}: {str(exc)[:200]} (line {where.lineno}: {where.line})")
            continue
        path = args.out / f"{name.lower()}--pybamm.bpx.json"
        path.write_text(json.dumps(bpx, indent=2) + "\n", encoding="utf-8", newline="\n")
        report = {"set": name, "pybamm": pybamm.__version__, "file": path.name, "notes": notes,
                  "model": comparison["model"], "model_options": comparison["options"], "check": results}
        (args.out / f"{name.lower()}--pybamm.check.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        summary = ", ".join(
            f"{r['c_rate']:g}C{' warm' if 'temperature_K' in r else ''}: "
            f"{r['voltage_rms_difference_mV']} mV / {r['capacity_difference_percent']:+}%"
            if "error" not in r else f"{r['c_rate']:g}C: {r['error'][:60]}"
            for r in results
        )
        print(f"{name}: {summary}")
        for note in notes:
            print(f"   note: {note}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
