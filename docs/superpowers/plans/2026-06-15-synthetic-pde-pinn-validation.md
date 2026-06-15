# Synthetic PDE PINN Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible H59/6061 synthetic forward-PDE benchmark that generates PINN-compatible blind datasets, runs resumable inverse sweeps, and reports the time-length, space-length, and noise region where the current PINN recovers conductivity reliably.

**Architecture:** A SciPy finite-difference forward solver produces one high-resolution truth field per material, then exports cropped/noisy observation datasets plus separate truth sidecars. A sweep runner invokes the existing `train_pinn_1d.py` as an isolated subprocess with `material_preset=custom`, while an analyzer joins sidecars and PINN summaries only after training to calculate errors and select multi-seed refinement cases.

**Tech Stack:** Python 3, NumPy, SciPy `solve_ivp(BDF)`, PyTorch PINN subprocess, Matplotlib, JSON/CSV, `unittest`.

---

## File Map

- Create `configs/synthetic_pinn_h59_6061.json`: canonical benchmark physics, grid, scan axes, PINN baseline, and refinement rules.
- Create `code/generate_synthetic_pde_data.py`: forward PDE, observation cropping, Gaussian noise, `.npz` export, and truth sidecar export.
- Create `code/run_synthetic_pinn_sweep.py`: deterministic task expansion, subprocess commands, status manifests, resume behavior, and refinement execution.
- Create `code/analyze_synthetic_sweep.py`: result parsing, blind-stability checks, error metrics, refinement selection, CSV tables, and figures.
- Create `tests/test_generate_synthetic_pde_data.py`: physics, reproducibility, grid convergence, and PINN dataset compatibility.
- Create `tests/test_synthetic_pinn_sweep.py`: task expansion, truth isolation, command construction, resume behavior, and analysis metrics.
- Modify `README.md`: concise commands for smoke, coarse sweep, refinement, and analysis.
- Do not modify `code/train_pinn_1d.py` until the baseline benchmark is complete.

### Task 1: Configuration Schema and Deterministic Task Model

**Files:**
- Create: `configs/synthetic_pinn_h59_6061.json`
- Create: `code/run_synthetic_pinn_sweep.py`
- Create: `tests/test_synthetic_pinn_sweep.py`

- [ ] **Step 1: Write failing tests for config loading and the 300 coarse tasks**

```python
class SweepConfigTests(unittest.TestCase):
    def test_default_config_expands_to_300_coarse_tasks(self):
        config = load_config(PROJECT_ROOT / "configs" / "synthetic_pinn_h59_6061.json")
        tasks = expand_coarse_tasks(config)
        self.assertEqual(len(tasks), 300)
        self.assertEqual({task.material for task in tasks}, {"h59", "6061"})

    def test_task_id_is_stable_and_contains_both_seed_types(self):
        task = SweepTask("h59", 120.0, 70.0, 0.2, data_seed=1003, pinn_seed=42)
        self.assertEqual(task.task_id, task.task_id)
        self.assertIn("data1003", task.task_id)
        self.assertIn("pinn42", task.task_id)
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
python -m unittest tests.test_synthetic_pinn_sweep.SweepConfigTests -v
```

Expected: import failure because `run_synthetic_pinn_sweep.py` and its functions do not exist.

- [ ] **Step 3: Add the canonical JSON configuration**

```json
{
  "schema_version": 1,
  "materials": {
    "h59": {"rho": 8500.0, "cp": 380.0, "true_k": 100.0},
    "6061": {"rho": 2700.0, "cp": 900.0, "true_k": 160.0}
  },
  "physics": {
    "true_h": 10.0,
    "diameter_mm": 8.0,
    "emissivity": 0.95,
    "sigma_sb": 5.67e-8,
    "t_inf_c": 25.0,
    "left_delta_t_c": 70.0,
    "left_tau_s": 20.0,
    "domain_length_mm": 120.0
  },
  "sampling": {
    "internal_dx_mm": 0.75,
    "observation_dx_mm": 1.5,
    "observation_fps": 6.0,
    "rtol": 1e-7,
    "atol": 1e-9
  },
  "coarse_scan": {
    "time_lengths_s": [30, 60, 120, 240, 480],
    "space_lengths_mm": [30, 50, 70, 90, 110],
    "noise_sigma_c": [0, 0.05, 0.1, 0.2, 0.5, 1.0],
    "data_seed": 1003,
    "pinn_seeds": [42]
  },
  "refinement": {
    "pinn_seeds": [42, 43, 44, 45, 46],
    "near_error_threshold_margin": 0.03,
    "best_cases_per_material": 3
  },
  "pinn": {
    "epochs": 2000,
    "lr": 0.001,
    "hidden_width": 64,
    "hidden_depth": 4,
    "collocation_points": 2048,
    "data_weight": 10.0,
    "pde_weight": 1.0,
    "bc_weight": 3.0,
    "ic_weight": 3.0,
    "alpha_init": 2.5e-5,
    "h_init": 12.0,
    "right_bc_mode": "none",
    "initial_mode": "measured",
    "measured_initial_frame_count": 5,
    "device": "auto"
  }
}
```

- [ ] **Step 4: Implement config loading and immutable task expansion**

```python
@dataclass(frozen=True)
class SweepTask:
    material: str
    time_length_s: float
    space_length_mm: float
    noise_sigma_c: float
    data_seed: int
    pinn_seed: int

    @property
    def task_id(self):
        noise = str(self.noise_sigma_c).replace(".", "p")
        return (
            f"{self.material}_t{int(self.time_length_s)}"
            f"_l{int(self.space_length_mm)}_n{noise}"
            f"_data{self.data_seed}_pinn{self.pinn_seed}"
        )


def load_config(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def expand_coarse_tasks(config):
    scan = config["coarse_scan"]
    return [
        SweepTask(material, time_s, length_mm, noise, scan["data_seed"], pinn_seed)
        for material, time_s, length_mm, noise, pinn_seed in itertools.product(
            config["materials"],
            scan["time_lengths_s"],
            scan["space_lengths_mm"],
            scan["noise_sigma_c"],
            scan["pinn_seeds"],
        )
    ]
```

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
python -m unittest tests.test_synthetic_pinn_sweep.SweepConfigTests -v
git add configs/synthetic_pinn_h59_6061.json code/run_synthetic_pinn_sweep.py tests/test_synthetic_pinn_sweep.py
git commit -m "feat: 添加合成PINN扫描配置"
```

Expected: 2 tests pass; commit contains only these three files.

### Task 2: Independent Forward PDE Solver

**Files:**
- Create: `code/generate_synthetic_pde_data.py`
- Create: `tests/test_generate_synthetic_pde_data.py`

- [ ] **Step 1: Write failing tests for material truth, boundary curve, and solver shape**

```python
class ForwardSolverTests(unittest.TestCase):
    def test_material_alpha_is_derived_from_true_k(self):
        material = MaterialConfig("h59", rho=8500.0, cp=380.0, true_k=100.0)
        self.assertAlmostEqual(material.alpha, 100.0 / (8500.0 * 380.0))

    def test_left_boundary_starts_at_ambient_and_rises_smoothly(self):
        physics = make_test_physics()
        self.assertAlmostEqual(left_boundary_c(0.0, physics), physics.t_inf_c)
        self.assertGreater(left_boundary_c(60.0, physics), left_boundary_c(10.0, physics))

    def test_forward_solution_is_finite_and_has_expected_shape(self):
        solution = solve_forward_field(make_test_material(), make_test_physics(), make_test_sampling(), 10.0)
        self.assertEqual(solution.temperature_c.shape, (solution.time_s.size, solution.x_m.size))
        self.assertTrue(np.isfinite(solution.temperature_c).all())
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
python -m unittest tests.test_generate_synthetic_pde_data.ForwardSolverTests -v
```

Expected: import failure because the generator module does not exist.

- [ ] **Step 3: Implement typed physics records and the left boundary**

```python
@dataclass(frozen=True)
class MaterialConfig:
    name: str
    rho: float
    cp: float
    true_k: float

    @property
    def alpha(self):
        return self.true_k / (self.rho * self.cp)


def left_boundary_c(time_s, physics):
    return physics.t_inf_c + physics.left_delta_t_c * (
        1.0 - np.exp(-np.asarray(time_s) / physics.left_tau_s)
    )
```

- [ ] **Step 4: Implement the method-of-lines right-hand side and BDF solve**

Use a state vector for all nodes except the prescribed left node. For interior nodes:

```python
laplacian = (full_t[:-2] - 2.0 * full_t[1:-1] + full_t[2:]) / dx_m**2
temperature_k = full_t[1:-1] + 273.15
ambient_k = physics.t_inf_c + 273.15
loss = (
    4.0 * physics.true_h / (material.rho * material.cp * diameter_m)
    * (full_t[1:-1] - physics.t_inf_c)
    + 4.0 * physics.emissivity * physics.sigma_sb
    / (material.rho * material.cp * diameter_m)
    * (temperature_k**4 - ambient_k**4)
)
dtemperature_dt[:-1] = material.alpha * laplacian - loss
```

At the physical right end, eliminate a ghost node using the Robin flux:

```python
q_loss = physics.true_h * (t_right - physics.t_inf_c) + physics.emissivity * physics.sigma_sb * (
    (t_right + 273.15) ** 4 - ambient_k**4
)
ghost_right = t_before - 2.0 * dx_m * q_loss / material.true_k
laplacian_right = (t_before - 2.0 * t_right + ghost_right) / dx_m**2
```

Call:

```python
solve_ivp(rhs, (0.0, duration_s), initial_state, t_eval=time_s, method="BDF", rtol=rtol, atol=atol)
```

Raise `RuntimeError` when `solution.success` is false or any temperature is non-finite.

- [ ] **Step 5: Add numerical-quality tests**

```python
def test_left_boundary_is_exact_in_solution(self):
    solution = solve_forward_field(...)
    expected = left_boundary_c(solution.time_s, physics)
    np.testing.assert_allclose(solution.temperature_c[:, 0], expected, atol=1e-8)

def test_refined_grid_changes_observations_by_less_than_point_zero_five_c(self):
    coarse = solve_forward_field(... internal_dx_mm=0.75 ...)
    fine = solve_forward_field(... internal_dx_mm=0.375 ...)
    difference = compare_on_common_observation_grid(coarse, fine, dx_mm=1.5, fps=6.0)
    self.assertLess(float(np.max(np.abs(difference))), 0.05)
```

- [ ] **Step 6: Run tests and commit**

Run:

```powershell
python -m unittest tests.test_generate_synthetic_pde_data.ForwardSolverTests -v
git add code/generate_synthetic_pde_data.py tests/test_generate_synthetic_pde_data.py
git commit -m "feat: 实现独立一维导热正向求解器"
```

Expected: all forward-solver tests pass.

### Task 3: Observation Export, Gaussian Noise, and Truth Isolation

**Files:**
- Modify: `code/generate_synthetic_pde_data.py`
- Modify: `tests/test_generate_synthetic_pde_data.py`

- [ ] **Step 1: Write failing tests for deterministic noise and PINN-compatible export**

```python
class SyntheticExportTests(unittest.TestCase):
    def test_same_seed_produces_identical_noisy_grid(self):
        first = build_observation_dataset(solution, 60.0, 50.0, 0.2, seed=1003)
        second = build_observation_dataset(solution, 60.0, 50.0, 0.2, seed=1003)
        np.testing.assert_array_equal(first["xt_grid_c"], second["xt_grid_c"])

    def test_training_npz_contains_no_true_parameter_keys(self):
        write_synthetic_case(case_dir, dataset, truth)
        with np.load(case_dir / "observations.npz") as data:
            self.assertTrue(REQUIRED_PINN_KEYS.issubset(data.files))
            self.assertFalse(any(key.startswith("true_") for key in data.files))

    def test_existing_pinn_loader_reads_export(self):
        loaded = load_xt_dataset(case_dir / "observations.npz")
        self.assertEqual(loaded["xt_grid_c"].shape, dataset["xt_grid_c"].shape)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
python -m unittest tests.test_generate_synthetic_pde_data.SyntheticExportTests -v
```

Expected: missing `build_observation_dataset` and `write_synthetic_case`.

- [ ] **Step 3: Implement observation sampling and noise**

```python
def build_observation_dataset(solution, duration_s, length_mm, noise_sigma_c, seed, observation_dx_mm, fps):
    time_axis = np.arange(0.0, duration_s + 0.5 / fps, 1.0 / fps)
    x_axis_mm = np.arange(0.0, length_mm + 0.5 * observation_dx_mm, observation_dx_mm)
    clean = RegularGridInterpolator(
        (solution.time_s, solution.x_m * 1000.0),
        solution.temperature_c,
    )(observation_mesh(time_axis, x_axis_mm)).reshape(time_axis.size, x_axis_mm.size)
    rng = np.random.default_rng(seed)
    noisy = clean + rng.normal(0.0, noise_sigma_c, clean.shape)
    noisy[:, 0] = clean[:, 0]
    return {
        "xt_grid_c": noisy.astype(np.float32),
        "clean_xt_grid_c": clean.astype(np.float32),
        "time_axis_sec": time_axis.astype(np.float32),
        "x_axis_heat_px": np.arange(x_axis_mm.size, dtype=np.float32),
        "x_axis_mm": x_axis_mm.astype(np.float32),
        "boundary_temperature_c": clean[:, 0].astype(np.float32),
        "far_end_temperature_c": noisy[:, -1].astype(np.float32),
    }
```

Keep the prescribed left boundary noise-free because the current PINN treats it as a measured Dirichlet boundary. Noise applies to the remaining observation field.

- [ ] **Step 4: Export observations and truth to separate files**

Write:

```text
data/derived/synthetic_pinn/<batch_id>/forward_fields/<material>_<config_hash>.npz
data/derived/synthetic_pinn/<batch_id>/datasets/<case_id>/observations.npz
data/derived/synthetic_pinn/<batch_id>/truth/<case_id>.json
```

The forward-field cache is solved once per material at the maximum configured duration and full physical length. Every time/space/noise case is derived from that immutable cached field. Before reusing it, verify its material and forward-physics hash.

The `.npz` contains only PINN-readable arrays. The truth JSON contains:

```json
{
  "case_id": "...",
  "material": "h59",
  "true_k": 100.0,
  "true_alpha": 3.0959752321981426e-05,
  "true_h": 10.0,
  "time_length_s": 60.0,
  "space_length_mm": 50.0,
  "noise_sigma_c": 0.2,
  "data_seed": 1003,
  "config_hash": "..."
}
```

- [ ] **Step 5: Add a command-line single-case generator**

Support:

```powershell
python code\generate_synthetic_pde_data.py `
  --config configs\synthetic_pinn_h59_6061.json `
  --material h59 --duration-s 60 --length-mm 50 `
  --noise-sigma-c 0.2 --seed 1003 --batch-id smoke
```

Print the absolute observation and truth paths.

- [ ] **Step 6: Run compatibility tests and commit**

Run:

```powershell
python -m unittest tests.test_generate_synthetic_pde_data -v
python code\generate_synthetic_pde_data.py --config configs\synthetic_pinn_h59_6061.json --material h59 --duration-s 10 --length-mm 30 --noise-sigma-c 0 --seed 1003 --batch-id plan_smoke
python code\train_pinn_1d.py data\derived\synthetic_pinn\plan_smoke\datasets\h59_t10_l30_n0_data1003\observations.npz --skip-train --material-preset custom --rho 8500 --cp 380 --diameter-mm 8 --t-inf-c 25 --calibration-mode manual --mm-per-px 1.5
git add code/generate_synthetic_pde_data.py tests/test_generate_synthetic_pde_data.py
git commit -m "feat: 导出盲测合成温度数据"
```

Expected: tests pass; PINN prints dataset shape and `mm_per_px: 1.5`.

### Task 4: Resumable PINN Sweep Runner

**Files:**
- Modify: `code/run_synthetic_pinn_sweep.py`
- Modify: `tests/test_synthetic_pinn_sweep.py`

- [ ] **Step 1: Write failing tests for blind command construction and resume decisions**

```python
class SweepRunnerTests(unittest.TestCase):
    def test_command_uses_custom_material_and_never_passes_truth_range(self):
        command = build_pinn_command(task, config, observations_path, output_stem="case")
        joined = " ".join(command)
        self.assertIn("--material-preset custom", joined)
        self.assertNotIn("--expected-k-min", joined)
        self.assertNotIn("--expected-k-max", joined)
        self.assertNotIn("true_k", joined)

    def test_completed_matching_task_is_skipped(self):
        write_status(task_dir, "completed", config_hash="abc", summary_path="summary.json")
        self.assertEqual(decide_task_action(task_dir, "abc"), "skip")

    def test_hash_mismatch_creates_new_batch_instead_of_overwriting(self):
        write_status(task_dir, "completed", config_hash="old", summary_path="summary.json")
        self.assertEqual(decide_task_action(task_dir, "new"), "new_batch")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
python -m unittest tests.test_synthetic_pinn_sweep.SweepRunnerTests -v
```

Expected: missing command/status functions.

- [ ] **Step 3: Implement the exact PINN command**

```python
def build_pinn_command(task, config, observations_path, output_stem):
    material = config["materials"][task.material]
    physics = config["physics"]
    pinn = config["pinn"]
    return [
        sys.executable, str(PROJECT_ROOT / "code" / "train_pinn_1d.py"), str(observations_path),
        "--epochs", str(pinn["epochs"]),
        "--lr", str(pinn["lr"]),
        "--hidden-width", str(pinn["hidden_width"]),
        "--hidden-depth", str(pinn["hidden_depth"]),
        "--collocation-points", str(pinn["collocation_points"]),
        "--data-weight", str(pinn["data_weight"]),
        "--pde-weight", str(pinn["pde_weight"]),
        "--bc-weight", str(pinn["bc_weight"]),
        "--ic-weight", str(pinn["ic_weight"]),
        "--material-preset", "custom",
        "--rho", str(material["rho"]),
        "--cp", str(material["cp"]),
        "--diameter-mm", str(physics["diameter_mm"]),
        "--emissivity", str(physics["emissivity"]),
        "--t-inf-c", str(physics["t_inf_c"]),
        "--alpha-init", str(pinn["alpha_init"]),
        "--h-init", str(pinn["h_init"]),
        "--right-bc-mode", str(pinn["right_bc_mode"]),
        "--initial-mode", str(pinn["initial_mode"]),
        "--measured-initial-frame-count", str(pinn["measured_initial_frame_count"]),
        "--calibration-mode", "manual",
        "--mm-per-px", str(config["sampling"]["observation_dx_mm"]),
        "--seed", str(task.pinn_seed),
        "--device", str(pinn["device"]),
        "--output-stem", output_stem,
    ]
```

- [ ] **Step 4: Implement status manifests and subprocess execution**

Store each run under:

```text
outputs/synthetic_pinn/<batch_id>/tasks/<task_id>/status.json
outputs/models/<output_stem>/<output_stem>_summary.json
```

Write `running` before `subprocess.run()`, then atomically replace with `completed` or `failed`. Include command, timestamps, return code, config hash, observation path, summary path, and log path. Redirect stdout/stderr to the task log.

Before starting PINN, call the generator API to create missing observations. The generator must reuse the per-material full forward-field cache instead of solving the PDE for every scan combination.

- [ ] **Step 5: Add bounded execution modes**

Support:

```powershell
python code\run_synthetic_pinn_sweep.py --config ... --batch-id baseline --mode list
python code\run_synthetic_pinn_sweep.py --config ... --batch-id baseline --mode coarse --limit 2 --max-workers 1
python code\run_synthetic_pinn_sweep.py --config ... --batch-id baseline --mode single --task-id <id>
python code\run_synthetic_pinn_sweep.py --config ... --batch-id baseline --mode refinement --refinement-file <json>
```

Default `max-workers=1`; refuse values greater than the detected CUDA device count when `device=cuda`, and cap CPU mode at a user-provided value without guessing available memory.

- [ ] **Step 6: Run tests and commit**

Run:

```powershell
python -m unittest tests.test_synthetic_pinn_sweep.SweepRunnerTests -v
python code\run_synthetic_pinn_sweep.py --config configs\synthetic_pinn_h59_6061.json --batch-id baseline --mode list
git add code/run_synthetic_pinn_sweep.py tests/test_synthetic_pinn_sweep.py
git commit -m "feat: 添加可续跑PINN扫描器"
```

Expected: tests pass; list mode reports 300 tasks without starting training.

### Task 5: Blind Result Analysis and Refinement Selection

**Files:**
- Create: `code/analyze_synthetic_sweep.py`
- Modify: `tests/test_synthetic_pinn_sweep.py`

- [ ] **Step 1: Write failing tests for result source, errors, Fo/SNR, and refinement**

```python
class SweepAnalysisTests(unittest.TestCase):
    def test_rejected_summary_uses_final_estimate_but_marks_not_stable(self):
        row = analyze_case(summary=rejected_summary(), truth=truth_record(), clean=clean, noisy=noisy)
        self.assertEqual(row["estimate_source"], "final")
        self.assertFalse(row["blind_stability_pass"])

    def test_error_and_dimensionless_metrics(self):
        row = analyze_case(summary_with_k(110.0), truth_record(true_k=100.0), clean, noisy_sigma_point_two)
        self.assertAlmostEqual(row["k_relative_error"], 0.10)
        self.assertGreater(row["fourier_number"], 0.0)
        self.assertGreater(row["snr"], 0.0)

    def test_refinement_includes_threshold_and_best_cases(self):
        selected = select_refinement_cases(make_boundary_rows(), config)
        self.assertTrue(any(case["selection_reason"] == "near_10_percent" for case in selected))
        self.assertTrue(any(case["selection_reason"] == "best_case" for case in selected))
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
python -m unittest tests.test_synthetic_pinn_sweep.SweepAnalysisTests -v
```

Expected: import failure because analyzer functions do not exist.

- [ ] **Step 3: Implement truth-independent estimate selection**

Do not use expected material ranges. Select:

```python
def select_blind_estimate(summary):
    best = summary.get("best_physical", {})
    if summary.get("quality_checks", {}).get("parameters_stable"):
        return "final", summary["thermal_conductivity_w_mk"], summary["alpha_m2_s"], summary["h_w_m2k"]
    if best.get("found"):
        return "stable_plateau", best["thermal_conductivity_w_mk"], best["alpha_m2_s"], best["h_w_m2k"]
    return "final", summary["thermal_conductivity_w_mk"], summary["alpha_m2_s"], summary["h_w_m2k"]
```

Set `blind_stability_pass` only from step count, alpha/h tail stability, finite losses, and non-exploding PDE loss. Ignore `expected_k_in_range` because synthetic runs have no expected range.

- [ ] **Step 4: Implement metrics and CSV output**

```python
k_relative_error = abs(k_est - truth["true_k"]) / truth["true_k"]
alpha_relative_error = abs(alpha_est - truth["true_alpha"]) / truth["true_alpha"]
h_relative_error = abs(h_est - truth["true_h"]) / truth["true_h"]
fourier_number = truth["true_alpha"] * truth["time_length_s"] / (truth["space_length_mm"] * 1e-3) ** 2
snr = math.inf if truth["noise_sigma_c"] == 0 else float(
    np.max(clean_xt_grid_c - clean_xt_grid_c[0]) / truth["noise_sigma_c"]
)
```

Write:

```text
outputs/synthetic_pinn/<batch_id>/analysis/case_results.csv
outputs/synthetic_pinn/<batch_id>/analysis/refinement_cases.json
outputs/synthetic_pinn/<batch_id>/analysis/summary.json
```

- [ ] **Step 5: Implement deterministic refinement rules**

Select the unique base case `(material, time, length, noise, data_seed)` when:

- `abs(k_relative_error - 0.10) <= 0.03`
- `abs(k_relative_error - 0.20) <= 0.03`
- a neighboring time/space/noise grid point changes `k_relative_error <= 0.20` to `> 0.20`
- it is among the three lowest-error blind-stable cases for that material
- it is a representative drift/rejection case

Expand each selected base case to PINN seeds `[42, 43, 44, 45, 46]`, deduplicate seed 42, and include `selection_reason`.

- [ ] **Step 6: Generate benchmark figures**

Create:

```text
<material>_noise_<sigma>_k_error_heatmap.png
<material>_success_rate_heatmap.png
fo_snr_scatter.png
representative_parameter_trajectories.png
```

Use `NaN` for missing/failed tasks and annotate cells with relative error or success fraction.

- [ ] **Step 7: Run tests and commit**

Run:

```powershell
python -m unittest tests.test_synthetic_pinn_sweep.SweepAnalysisTests -v
git add code/analyze_synthetic_sweep.py tests/test_synthetic_pinn_sweep.py
git commit -m "feat: 分析合成PINN适用域"
```

Expected: analysis tests pass and generated test artifacts stay in temporary directories.

### Task 6: End-to-End Smoke Benchmark

**Files:**
- Modify: `tests/test_synthetic_pinn_sweep.py`
- Modify only if a smoke test exposes an interface defect:
  - `code/generate_synthetic_pde_data.py`
  - `code/run_synthetic_pinn_sweep.py`
  - `code/analyze_synthetic_sweep.py`

- [ ] **Step 1: Add a subprocess smoke test with a tiny PINN configuration**

```python
def test_end_to_end_one_case_creates_analyzable_result(self):
    config = tiny_config(epochs=2, collocation_points=32, duration_s=5, length_mm=15)
    batch_dir = run_one_case_in_temp_dir(config)
    row = analyze_batch(batch_dir, config)[0]
    self.assertEqual(row["material"], "h59")
    self.assertTrue(math.isfinite(row["k_est"]))
    self.assertIn(row["task_status"], {"completed"})
```

- [ ] **Step 2: Run the smoke test and fix only concrete interface failures**

Run:

```powershell
python -m unittest tests.test_synthetic_pinn_sweep.EndToEndSmokeTests -v
```

Expected: one two-step PINN run completes and produces a parsed result. Do not assert physical accuracy at two steps.

- [ ] **Step 3: Run the complete unit suite**

Run:

```powershell
$env:PYTHONUTF8='1'
python -m unittest discover -s tests -v
```

Expected: all existing and new tests pass.

- [ ] **Step 4: Run a real but bounded two-material smoke batch**

Create an ignored temporary smoke config under `outputs/synthetic_pinn/`:

```powershell
New-Item -ItemType Directory -Force outputs\synthetic_pinn | Out-Null
$config = Get-Content -Raw configs\synthetic_pinn_h59_6061.json | ConvertFrom-Json
$config.coarse_scan.time_lengths_s = @(30)
$config.coarse_scan.space_lengths_mm = @(50)
$config.coarse_scan.noise_sigma_c = @(0, 0.2)
$config.coarse_scan.pinn_seeds = @(42)
$config.pinn.epochs = 50
$config.pinn.collocation_points = 256
$config | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 outputs\synthetic_pinn\smoke_config.json
```

Run:

```powershell
python code\run_synthetic_pinn_sweep.py --config outputs\synthetic_pinn\smoke_config.json --batch-id smoke_20260615 --mode coarse --max-workers 1
python code\analyze_synthetic_sweep.py --config outputs\synthetic_pinn\smoke_config.json --batch-id smoke_20260615
```

Expected: 4 completed tasks, a CSV with 4 rows, and heatmaps for both materials.

- [ ] **Step 5: Commit smoke fixes**

```powershell
git add code/generate_synthetic_pde_data.py code/run_synthetic_pinn_sweep.py code/analyze_synthetic_sweep.py tests/test_generate_synthetic_pde_data.py tests/test_synthetic_pinn_sweep.py
git commit -m "test: 验证合成PINN端到端流程"
```

If no source changes were needed after the prior commits, skip this commit instead of creating an empty commit.

### Task 7: Usage Documentation and Baseline Launch Gate

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add concise benchmark commands**

Document:

```powershell
# List the 300 coarse tasks without running them
python code\run_synthetic_pinn_sweep.py --config configs\synthetic_pinn_h59_6061.json --batch-id baseline_v1 --mode list

# Run a bounded initial check
python code\run_synthetic_pinn_sweep.py --config configs\synthetic_pinn_h59_6061.json --batch-id baseline_v1 --mode coarse --limit 2 --max-workers 1

# Resume the full coarse scan
python code\run_synthetic_pinn_sweep.py --config configs\synthetic_pinn_h59_6061.json --batch-id baseline_v1 --mode coarse --max-workers 1

# Analyze and create refinement cases
python code\analyze_synthetic_sweep.py --config configs\synthetic_pinn_h59_6061.json --batch-id baseline_v1

# Run the selected five-seed refinement
python code\run_synthetic_pinn_sweep.py --config configs\synthetic_pinn_h59_6061.json --batch-id baseline_v1 --mode refinement --refinement-file outputs\synthetic_pinn\baseline_v1\analysis\refinement_cases.json --max-workers 1
```

State explicitly that generated datasets and outputs are ignored by git, while config/code/tests are tracked.

- [ ] **Step 2: Verify commands, tracked scope, and formatting**

Run:

```powershell
python code\run_synthetic_pinn_sweep.py --config configs\synthetic_pinn_h59_6061.json --batch-id baseline_v1 --mode list
git diff --check
git status -sb
```

Expected: 300 listed tasks; no whitespace errors; generated `data/derived` and `outputs` files are not staged.

- [ ] **Step 3: Commit the documentation**

```powershell
git add README.md
git commit -m "docs: 添加合成PINN基准运行说明"
```

- [ ] **Step 4: Establish the immutable baseline before PINN changes**

Run the 2-task gate first:

```powershell
python code\run_synthetic_pinn_sweep.py --config configs\synthetic_pinn_h59_6061.json --batch-id baseline_v1 --mode coarse --limit 2 --max-workers 1
```

Inspect both task manifests and summaries. Only after both complete successfully should the full 300-task coarse scan be started. Do not modify `train_pinn_1d.py` while `baseline_v1` is being established.

## Completion Verification

Before claiming implementation complete:

```powershell
$env:PYTHONUTF8='1'
python -m unittest discover -s tests -v
python code\run_synthetic_pinn_sweep.py --config configs\synthetic_pinn_h59_6061.json --batch-id verification --mode list
git diff --check
git status -sb
```

Required evidence:

- All tests pass.
- List mode reports exactly 300 coarse tasks.
- A generated observation `.npz` loads through `load_xt_dataset()`.
- No `true_*` key exists in the observation `.npz` or PINN command.
- Re-running a completed matching task skips it.
- Config hash mismatch does not overwrite an old batch.
- The smoke analyzer produces CSV and figures for both H59 and 6061.
- Existing unrelated worktree changes remain untouched and unstaged.
