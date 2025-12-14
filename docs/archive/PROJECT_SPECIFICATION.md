# 📝 Project Specification: OSS Cine-Tracker

## 1. Project Goal

To create a cross-platform desktop application using open-source tools (COLMAP, Python) that automatically generates high-precision **Camera Path Animation (.abc)** and **Lens Calibration Data (JSON)** from smartphone video footage, designed specifically for seamless integration into the **Unreal Engine 5 Composure** Virtual Production workflow.

## 2. Core Feature Modes

The application will operate in two distinct modes to ensure robust and accurate results:

| Mode | Input | Output | Purpose |
| :--- | :--- | :--- | :--- |
| **Calibration Mode (F-01)** | Chessboard Pattern Footage | `lens_calibration_data.json` | Estimates the camera's fixed intrinsic parameters (focal length, principal point, and distortion coefficients) with high accuracy by optimizing all parameters using the **`OPENCV`** model. |
| **Tracking Mode (F-02)** | Main Scene Footage | `camera_path.abc` | Uses the fixed parameters from **F-01** and only optimizes the camera's extrinsic parameters (position and rotation) for stable, precise 3D camera tracking. |

## 3. Technical Stack & Dependencies

| Category | Component | Technology / Library | Purpose |
| :--- | :--- | :--- | :--- |
| **Language** | Core Development | Python 3.x | Main development language for scripting and logic. |
| **GUI** | User Interface | PyQt / PySide | Cross-platform desktop interface. |
| **SfM Core** | 3D Reconstruction | **COLMAP** (C++ Binary) | The primary engine for feature tracking and parameter estimation. |
| **Video I/O** | Frame Extraction | **FFmpeg** (Binary) | Fast and accurate extraction of image sequences from video files. |
| **Data I/O** | Data Handling | NumPy, PyCOLMAP | Reading COLMAP binary outputs and matrix manipulations. |
| **Export** | Camera Path Export | **PyAlembic** | Writing the final camera animation data to the industry-standard `.abc` format. |
| **Output** | Lens Data Export | Standard Python `json` | Writing the estimated intrinsic parameters for UE import. |

## 4. Pipeline Execution Summary

### **A. Calibration Mode Pipeline (F-01)**

1.  **Input**: User specifies Chessboard video file.
2.  **Processing**: FFmpeg extracts frames $\rightarrow$ COLMAP executes `feature_extractor` and `geometric_verifier`.
3.  **SfM Execution**: COLMAP `mapper` runs with **ALL intrinsic parameters refined (`BA_refine_extra_params = true`)** using the `OPENCV` camera model.
4.  **Output**: Python extracts the final intrinsic parameters from `cameras.bin` and writes them to **`lens_calibration_data.json`**. 

### **B. Tracking Mode Pipeline (F-02)**

1.  **Input**: User specifies Main Scene video file and **`lens_calibration_data.json`** (required).
2.  **Pre-processing**: Python script injects the fixed intrinsic parameters from the JSON file into the COLMAP database.
3.  **SfM Execution**: COLMAP `mapper` runs with **ONLY extrinsic parameters refined (`BA_refine_extra_params = false`, `BA_refine_extrinsics = true`)**.
4.  **Output**: Python reads the resulting camera positions/rotations $\rightarrow$ PyAlembic converts this data into a time-based animation $\rightarrow$ **`camera_path.abc`** is saved.

## 5. Unreal Engine (UE) Integration (Final Task)

To complete the workflow, a dedicated Python script must be developed for the Unreal Engine editor.

| Output File | UE Script Action | UE Target | UE API Used |
| :--- | :--- | :--- | :--- |
| **`camera_path.abc`** | Imports the file and binds the resulting camera animation track to a new Level Sequence. | New Cine Camera Actor, Level Sequence | `unreal.AssetToolsNew.import_asset_tasks()` |
| **`lens_calibration_data.json`** | Reads the $k_1, k_2, f_x, ...$ parameters and uses them to **automatically create a Lens File asset** in the project content. | Lens File Asset, Cine Camera Component | `unreal.LensFile.create_new_asset()`, `unreal.BrownConradyModel` |

**Final Workflow:** The Cine Camera in the Sequencer (tracking the Alembic path) automatically uses the assigned Lens File asset, ensuring the CG elements are rendered with the **exact same lens distortion** as the original iPhone footage, making the Composure composite seamless. 

---

## 6. Initial Task List (Development Sprints)

| Sprint / Task | Description | Priority | Responsible Module |
| :--- | :--- | :--- | :--- |
| **Setup-01** | Set up Python environment (venv/conda), install PyQt/PySide and initial dependencies (NumPy, etc.). | High | UI / I/O Modules |
| **FFMPEG-02** | Implement a stable Python wrapper for FFmpeg to extract video frames into an image sequence. | High | I/O Module |
| **COLMAP-03** | Implement Python wrappers for calling the core COLMAP CLI commands (`feature_extractor`, `mapper`). | High | Core Module |
| **F-01-CAL** | Implement the full Calibration Mode pipeline, focusing on reading the final `cameras.bin` and outputting the `lens_calibration_data.json`. | High | Core / I/O Modules |
| **F-02-TRK** | Implement the parameter injection logic for Tracking Mode (F-02) and execute the SfM with fixed intrinsic parameters. | High | Core Module |
| **ABC-04** | Implement the PyAlembic conversion logic to convert the COLMAP tracking data into a time-based `.abc` camera track. | High | I/O Module |
| **UE-05** | Develop the final Unreal Engine Python import script to handle both JSON (Lens File) and Alembic (Camera Path). | High | UE Integration |
| **UI-06** | Develop the PyQt/PySide GUI allowing input selection and process initiation for both F-01 and F-02 modes. | Medium | UI Module |
