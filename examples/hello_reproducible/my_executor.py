# my_executor.py
from dissmodel.core import Environment
from dissmodel.executor import ExperimentRecord, ModelExecutor
from dissmodel.executor.cli import run_cli
from dissmodel.io import load_dataset, save_dataset

from forest_fire_model import ForestFire


class ForestFireExecutor(ModelExecutor):
    name = "forest_fire"
    output_suffix = ".tif"

    def load(self, record: ExperimentRecord):
        (backend, _meta), checksum = load_dataset(record.source.uri)
        record.source.checksum = checksum
        return backend

    def run(self, data, record: ExperimentRecord):
        p = record.parameters
        env = Environment(end_time=p.get("end_time", 60))
        ForestFire(backend=data, prob_spread=p.get("prob_spread", 0.4), seed=p.get("seed", 42))
        env.run()
        return data

    def save(self, result, record: ExperimentRecord) -> ExperimentRecord:
        uri = record.output_path or "output.tif"
        record.output_sha256 = save_dataset(result, uri)
        record.output_path = uri
        record.status = "completed"
        return record


if __name__ == "__main__":
    run_cli(ForestFireExecutor)
