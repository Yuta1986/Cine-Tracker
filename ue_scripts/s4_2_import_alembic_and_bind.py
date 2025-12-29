"""
S4.2 — Alembic Import and Binding

Imports `camera_path.abc` and binds animation to a CineCameraActor in a Level Sequence.

Important:
- UE Alembic Python APIs vary across versions. This script uses best-effort calls and prints
  available helper functions when a direct API is missing.
"""

from __future__ import annotations

from pathlib import Path

import unreal


def import_alembic_asset(abc_path: str, destination_path: str) -> list[unreal.Object]:
    abc_path = str(Path(abc_path))

    task = unreal.AssetImportTask()
    task.filename = abc_path
    task.destination_path = destination_path
    task.automated = True
    task.save = True
    task.replace_existing = True

    # If Alembic import options are available, attach them (version-specific).
    if hasattr(unreal, "AbcImportSettings"):
        opts = unreal.AbcImportSettings()
        task.options = opts

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    return list(task.imported_object_paths or [])


def get_or_create_cine_camera() -> unreal.CineCameraActor:
    actors = unreal.EditorLevelLibrary.get_all_level_actors_of_class(unreal.CineCameraActor)
    if actors:
        return actors[0]
    loc = unreal.Vector(0, 0, 0)
    rot = unreal.Rotator(0, 0, 0)
    return unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.CineCameraActor, loc, rot)


def assign_lens_file(cine_camera: unreal.CineCameraActor, lens_file_asset: unreal.Object) -> None:
    comp = cine_camera.get_cine_camera_component()
    for method in ["set_lens_file", "set_editor_property"]:
        if hasattr(comp, "set_lens_file"):
            comp.set_lens_file(lens_file_asset)
            return
    if comp.has_editor_property("lens_file"):
        comp.set_editor_property("lens_file", lens_file_asset)
        return
    unreal.log_warning("Could not assign LensFile to CineCameraComponent (API not found).")


def get_or_create_level_sequence(dest_path: str, name: str = "LS_CineTracker") -> unreal.LevelSequence:
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    asset = tools.create_asset(name, dest_path, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    return asset


def bind_actor_to_sequence(seq: unreal.LevelSequence, actor: unreal.Actor) -> unreal.MovieSceneBindingProxy:
    subsys = unreal.get_editor_subsystem(unreal.LevelSequenceEditorSubsystem)
    binding = subsys.add_actor_to_sequence(seq, actor)
    return binding


def main(
    abc_path: str,
    lens_file_asset_path: str,
    destination_path: str = "/Game/VP/Imported",
) -> None:
    # 1) Import Alembic
    imported = import_alembic_asset(abc_path, destination_path)
    unreal.log(f"Imported Alembic objects: {imported}")

    # 2) Resolve LensFile asset
    lens_file = unreal.load_asset(lens_file_asset_path)
    if not lens_file:
        raise RuntimeError(f"Lens file asset not found: {lens_file_asset_path}")

    # 3) Find / create CineCamera actor and assign lens file
    cam = get_or_create_cine_camera()
    assign_lens_file(cam, lens_file)
    unreal.log(f"Using CineCameraActor: {cam.get_name()}")

    # 4) Create Level Sequence and bind actor
    seq = get_or_create_level_sequence(destination_path)
    bind_actor_to_sequence(seq, cam)

    unreal.EditorAssetLibrary.save_loaded_asset(seq)
    unreal.log(f"Created LevelSequence: {seq.get_path_name()}")

    unreal.log_warning(
        "Alembic-to-camera binding is UE-version dependent. If UE does not create a camera animation track from Alembic,\n"
        "consider importing transforms directly (keyframing) or verifying the Alembic camera schema in your build."
    )


# Example (run from UE python console):
# main(r\"C:\\path\\to\\camera_path.abc\", \"/Game/VP/CalibratedLens/LensFile_CineTracker.LensFile_CineTracker\")

