import csv
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np


CODE_DIR = Path(__file__).resolve().parents[1] / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from convert_roi_ymean_csv import build_dataset, load_roi_ymean_csv


class ConvertRoiYmeanCsvTests(unittest.TestCase):
    def test_load_and_build_dataset(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "sample.csv"
            with open(csv_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["frame_index", "x_1", "x_2", "x_3"])
                writer.writerow([0, 30, 29, 28])
                writer.writerow([1, 31, 30, 29])
                writer.writerow([2, 32, 31, 30])

            frame_indices, temperatures, columns = load_roi_ymean_csv(csv_path)
            dataset = build_dataset(
                frame_indices,
                temperatures,
                fps=2.0,
                length_mm=10.0,
                duration_sec=0.5,
            )

        self.assertEqual(columns, ["x_1", "x_2", "x_3"])
        self.assertEqual(dataset["xt_grid_c"].shape, (2, 3))
        np.testing.assert_allclose(dataset["time_axis_sec"], [0.0, 0.5])
        np.testing.assert_allclose(dataset["x_axis_mm"], [0.0, 5.0, 10.0])
        np.testing.assert_allclose(dataset["boundary_temperature_c"], [30.0, 31.0])


if __name__ == "__main__":
    unittest.main()
