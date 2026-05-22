from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = PROJECT_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from extract_rod_profile import (  # type: ignore
    auto_detect_rod_roi,
    build_rod_datasets,
    save_outputs,
)


def make_synthetic_frames():
    frame_count = 12
    height = 62
    width = 80
    frames = np.full((frame_count, height, width), 25.0, dtype=np.float32)

    for frame_idx in range(frame_count):
        alpha = frame_idx / (frame_count - 1)

        # Simulate the heated support block in the lower-left corner.
        frames[frame_idx, 40:62, 0:28] = 60.0 + 20.0 * alpha
        frames[frame_idx, 40:48, 16:28] = 66.0 + 18.0 * alpha

        # Simulate a horizontal blackened rod above the support block.
        rod_profile = np.linspace(44.0, 34.0, 56, dtype=np.float32) * alpha + 27.0
        frames[frame_idx, 28:32, 18:74] = rod_profile

    return frames


class AutoDetectRodRoiTests(unittest.TestCase):
    def test_auto_detect_picks_horizontal_rod_band_not_hot_support(self):
        frames = make_synthetic_frames()

        roi = auto_detect_rod_roi(
            frames,
            start_frame=2,
            cold_frame_count=2,
            hot_frame_count=3,
            search_y_max=40,
            band_half_height=2,
            min_delta_c=2.0,
        )

        self.assertEqual(roi["heat_side"], "left")
        self.assertLessEqual(roi["y_min"], 29)
        self.assertGreaterEqual(roi["y_max"], 31)
        self.assertLessEqual(roi["x_min"], 20)
        self.assertGreaterEqual(roi["x_max"], 70)


class BuildRodDatasetsTests(unittest.TestCase):
    def test_build_datasets_returns_consistent_xyt_and_xt_outputs(self):
        frames = make_synthetic_frames()
        roi = {"x_min": 18, "x_max": 74, "y_min": 28, "y_max": 32, "heat_side": "left"}

        datasets = build_rod_datasets(
            frames,
            fps=10.0,
            roi=roi,
            start_frame=2,
            end_frame=8,
            mm_per_px=0.5,
        )

        self.assertEqual(datasets["roi_frames"].shape, (6, 4, 56))
        self.assertEqual(datasets["xyt_inputs"].shape, (6 * 4 * 56, 3))
        self.assertEqual(datasets["xyt_targets"].shape, (6 * 4 * 56, 1))
        self.assertEqual(datasets["xt_grid_c"].shape, (6, 56))
        self.assertEqual(datasets["time_axis_sec"].shape, (6,))
        self.assertEqual(datasets["x_axis_mm"].shape, (56,))
        self.assertTrue(np.allclose(datasets["xt_grid_c"], datasets["roi_frames"].mean(axis=1)))
        self.assertAlmostEqual(float(datasets["x_axis_mm"][1] - datasets["x_axis_mm"][0]), 0.5)

    def test_save_outputs_writes_expected_artifacts(self):
        frames = make_synthetic_frames()
        roi = {"x_min": 18, "x_max": 74, "y_min": 28, "y_max": 32, "heat_side": "left"}
        datasets = build_rod_datasets(frames, fps=10.0, roi=roi, start_frame=0, end_frame=6)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            paths = save_outputs(
                output_dir=output_dir,
                dat_path=PROJECT_ROOT / "data" / "raw" / "synthetic.dat",
                fps=10.0,
                roi=roi,
                datasets=datasets,
                metadata_extra={"sample_id": "synthetic"},
            )

            for path in paths.values():
                self.assertTrue(path.exists(), f"{path} should exist")

            self.assertTrue(paths["meta"].read_text(encoding="utf-8"))
            with np.load(paths["xt_npz"]) as xt_npz:
                self.assertIn("x_axis_mm", xt_npz.files)


if __name__ == "__main__":
    unittest.main()
