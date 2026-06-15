import itertools
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SweepTask:
    material: str
    time_length_s: float
    space_length_mm: float
    noise_sigma_c: float
    data_seed: int
    pinn_seed: int

    @property
    def case_id(self):
        noise = f"{self.noise_sigma_c:g}".replace(".", "p")
        return (
            f"{self.material}_t{self.time_length_s:g}_l{self.space_length_mm:g}"
            f"_n{noise}_data{self.data_seed}"
        )

    @property
    def task_id(self):
        return f"{self.case_id}_pinn{self.pinn_seed}"


def load_config(path):
    with open(Path(path), "r", encoding="utf-8") as handle:
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
