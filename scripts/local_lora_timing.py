"""Local LoRA training of Qwen3.5-4B with mlx-lm on this Mac (2C.3): time per epoch and peak memory.

mlx-lm's own trainer runs a short LoRA on a timing set of seeded pool articles, each with the
short instruction and a placeholder answer of a teacher label's length; only lengths matter, so
no teacher label and no dev or gold article is needed. Its log gives seconds per iteration,
tokens per second and peak memory, and an epoch of 3,000 examples is projected from them. The
adapter is thrown away. Writes eval/results/phase2c/local_lora_timing.json.

  uv run --group local python scripts/local_lora_timing.py DATA_DIR [ITERS] [BATCH]
"""

import json
import re
import subprocess
import sys
import tempfile
import time

from label_gold import ROOT

MODEL = "Qwen/Qwen3.5-4B"
RESULT = ROOT / "eval" / "results" / "phase2c" / "local_lora_timing.json"
EXAMPLES = 3000
LINE = re.compile(
    r"Iter (\d+): Train loss [\d.]+.*?It/sec ([\d.]+).*?Tokens/sec ([\d.]+).*?Peak mem ([\d.]+) GB"
)


def main(data: str, iters: int = 40, batch: int = 4) -> None:
    with tempfile.TemporaryDirectory() as adapters:
        started = time.time()
        log = subprocess.run(
            [
                sys.executable,
                "-m",
                "mlx_lm",
                "lora",
                "--model",
                MODEL,
                "--train",
                "--data",
                data,
                "--iters",
                str(iters),
                "--batch-size",
                str(batch),
                "--num-layers",
                "16",
                "--max-seq-length",
                "2048",
                "--steps-per-report",
                "10",
                "--steps-per-eval",
                "100000",
                "--adapter-path",
                adapters,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        wall = time.time() - started
    reports = [
        tuple(map(float, m.groups())) for m in LINE.finditer(log.stdout + log.stderr)
    ]
    if not reports:
        sys.exit(
            "no training report in mlx-lm's log:\n" + (log.stdout + log.stderr)[-2000:]
        )
    steady = reports[1:] or reports  # the first report includes the warm-up
    it_per_sec = sum(r[1] for r in steady) / len(steady)
    epoch = EXAMPLES / batch / it_per_sec
    found = {
        "model": MODEL,
        "iterations": iters,
        "batch": batch,
        "lora_layers": 16,
        "wall_seconds": round(wall, 1),
        "iterations_per_second": round(it_per_sec, 3),
        "tokens_per_second": round(sum(r[2] for r in steady) / len(steady)),
        "peak_memory_gb": max(r[3] for r in reports),
        "epoch_of_3000_hours": round(epoch / 3600, 2),
        "reports": reports,
    }
    RESULT.write_text(json.dumps(found, indent=1) + "\n")
    print(json.dumps({k: v for k, v in found.items() if k != "reports"}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], *map(int, sys.argv[2:]))
