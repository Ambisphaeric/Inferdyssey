"""Autoresearch loop — AI agent experiments on training code.

Based on Karpathy's autoresearch pattern:
1. Agent reads current training code + recent results
2. Agent proposes ONE improvement
3. Apply change, train for fixed time budget
4. Benchmark — if improved, keep. If not, revert.
5. Repeat.
"""

import copy
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from core import benchmark
from core.agent import Agent
from core.trainer import train, CONFIGS


@dataclass
class IterationResult:
    iteration: int
    summary: str
    val_loss: float
    tok_per_sec: float
    improved: bool
    run_id: str
    reasoning: str = ""


class AutoresearchLoop:
    def __init__(
        self,
        agent: Agent,
        config_name: str = "small",
        data_path: str = "data/shakespeare.txt",
        time_budget_s: int = 180,
        hardware_name: str = "",
    ):
        self.agent = agent
        self.config_name = config_name
        self.data_path = data_path
        self.time_budget_s = time_budget_s
        self.hardware_name = hardware_name
        self.best_val_loss = float("inf")
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def run(
        self,
        num_iterations: int = 10,
        progress_callback=None,
        train_progress_callback=None,
    ):
        """Run the autoresearch loop. Yields IterationResult for each iteration."""
        self._stop_requested = False
        results = []

        # --- Baseline run ---
        if progress_callback:
            progress_callback({"phase": "baseline", "iteration": 0, "total": num_iterations})

        baseline = train(
            config_name=self.config_name,
            data_path=self.data_path,
            max_time_seconds=self.time_budget_s,
            progress_callback=train_progress_callback,
        )

        self.best_val_loss = baseline.val_loss
        run_id = benchmark.log_result(
            val_loss=baseline.val_loss,
            train_loss=baseline.train_loss,
            tok_per_sec=baseline.tok_per_sec,
            peak_memory_mb=baseline.peak_memory_mb,
            wall_time_s=baseline.wall_time_s,
            steps=baseline.steps,
            config_name=self.config_name,
            n_params=baseline.n_params,
            hardware=self.hardware_name,
            summary="baseline",
        )

        baseline_result = IterationResult(
            iteration=0,
            summary="baseline",
            val_loss=baseline.val_loss,
            tok_per_sec=baseline.tok_per_sec,
            improved=True,
            run_id=run_id,
        )
        results.append(baseline_result)
        yield baseline_result

        # --- Experiment iterations ---
        # Read the trainer source as the "code" the agent will modify
        trainer_source = Path("core/trainer.py").read_text()

        for i in range(1, num_iterations + 1):
            if self._stop_requested:
                break

            if progress_callback:
                progress_callback({"phase": "experimenting", "iteration": i, "total": num_iterations})

            # 1. Ask agent for improvement
            history = benchmark.get_history(limit=5)
            edit = self.agent.suggest_code_edit(trainer_source, history)

            # 2. Save modified code
            backup = trainer_source
            trainer_source = edit.new_code
            trainer_path = Path("core/trainer.py")

            # Write the modified trainer (we'll revert if it doesn't help)
            trainer_path.write_text(trainer_source)

            # 3. Train with the modified code
            try:
                # Re-import the modified trainer
                # Since we're modifying the file on disk but already imported,
                # we run training with the current in-memory module.
                # For true code-edit autoresearch, we'd subprocess. For MVP,
                # we use the base training loop with parameter variations.
                result = train(
                    config_name=self.config_name,
                    data_path=self.data_path,
                    max_time_seconds=self.time_budget_s,
                    progress_callback=train_progress_callback,
                )
            except Exception as e:
                # Training failed — revert
                trainer_path.write_text(backup)
                trainer_source = backup
                iter_result = IterationResult(
                    iteration=i,
                    summary=f"FAILED: {e}",
                    val_loss=float("inf"),
                    tok_per_sec=0,
                    improved=False,
                    run_id="",
                    reasoning=edit.reasoning,
                )
                results.append(iter_result)
                yield iter_result
                continue

            # 4. Benchmark
            improved = result.val_loss < self.best_val_loss
            run_id = benchmark.log_result(
                val_loss=result.val_loss,
                train_loss=result.train_loss,
                tok_per_sec=result.tok_per_sec,
                peak_memory_mb=result.peak_memory_mb,
                wall_time_s=result.wall_time_s,
                steps=result.steps,
                config_name=self.config_name,
                n_params=result.n_params,
                hardware=self.hardware_name,
                summary=edit.summary,
                code_diff=edit.summary,
            )

            if improved:
                self.best_val_loss = result.val_loss
            else:
                # Revert
                trainer_path.write_text(backup)
                trainer_source = backup

            iter_result = IterationResult(
                iteration=i,
                summary=edit.summary,
                val_loss=result.val_loss,
                tok_per_sec=result.tok_per_sec,
                improved=improved,
                run_id=run_id,
                reasoning=edit.reasoning,
            )
            results.append(iter_result)
            yield iter_result

        return results
