

# dissmodel/executor/utils.py

def default_output_uri(experiment_id: str, ext: str) -> str:
    """
    Returns an s3:// URI when MinIO is reachable, a local path otherwise.

    Intended for use in ModelExecutor.save() implementations when
    output_path is not provided in the experiment record.

    Parameters
    ----------
    experiment_id : str
        Unique experiment identifier — used as the output directory name.
    ext : str
        File extension without the dot (e.g. 'tif', 'gpkg').

    Returns
    -------
    str
        's3://dissmodel-outputs/experiments/{id}/output.{ext}'
        or './outputs/{id}/output.{ext}' if MinIO is not reachable.
    """
    from dissmodel.io._storage import get_default_client
    try:
        get_default_client()
        return f"s3://dissmodel-outputs/experiments/{experiment_id}/output.{ext}"
    except Exception:  # noqa: BLE001 — MinIO client can fail for many reasons (unset config, unreachable host); any failure means "fall back to local storage"
        return f"./outputs/{experiment_id}/output.{ext}"