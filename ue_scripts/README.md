# Unreal Engine Scripts (Sprint 4)

These scripts are intended to be run inside the Unreal Editor Python environment (UE 5.x) with the relevant plugins enabled:
- **Camera Calibration** / **Lens Distortion** (Lens File assets, Brown-Conrady distortion)
- **Alembic Importer** (Alembic import)
- **Level Sequencer** (binding animation to CineCamera + Level Sequence)

Because Unreal’s Python API can differ across minor versions, the scripts use capability checks (`hasattr`) and will print clear errors if a specific API is unavailable.

Scripts:
- `ue_scripts/s4_1_create_lens_file.py`
- `ue_scripts/s4_2_import_alembic_and_bind.py`

