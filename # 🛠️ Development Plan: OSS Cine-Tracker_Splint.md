# 🛠️ Development Plan: OSS Cine-Tracker (Sprints)

## Sprint 1: Foundation & Core COLMAP Integration

**Goal:** Establish the development environment and achieve a successful, basic command-line execution of the SfM process for both modes.

| Task ID | Description | Output / Success Criteria | Responsible Module |
| :--- | :--- | :--- | :--- |
| **S1.1** | **Environment Setup** | Python environment (venv/conda) with initial dependencies (`numpy`, `scipy`, `PySide6`) installed. | Setup |
| **S1.2** | **FFmpeg Wrapper** | Python function to reliably extract an image sequence from any input video file (`.mp4`, `.mov`). | I/O (FFmpeg) |
| **S1.3** | **COLMAP CLI Wrapper** | Python functions to execute core COLMAP commands (`feature_extractor`, `mapper`) using `subprocess`. | Core |
| **S1.4** | **Basic Calibration Test (F-01)** | Run a full SfM process on test chessboard data and confirm COLMAP outputs (`cameras.bin`) are created. | Core |
| **S1.5** | **Bin Data Reader** | Develop a script using `numpy`/PyCOLMAP to read and parse the essential data from the COLMAP binary files. | I/O (Data Processing) |

## Sprint 2: Calibration & Tracking Logic (The Hard Part)

**Goal:** Implement the critical logic for parameter reading/writing and finalize the high-precision tracking pipeline.

| Task ID | Description | Output / Success Criteria | Responsible Module |
| :--- | :--- | :--- | :--- |
| **S2.1** | **JSON & Parameter Export** | Finalize the logic to extract the specific `OPENCV` parameters ($f_x, c_x, k_1, k_2, ...$) and write them to the final **`lens_calibration_data.json`**. | I/O |
| **S2.2** | **Parameter Injection Logic** | Develop the script to inject the fixed intrinsic parameters from the JSON into the COLMAP database before running the mapper for F-02. | Core |
| **S2.3** | **Tracking Test (F-02)** | Execute the full tracking pipeline with **fixed intrinsic parameters** and confirm that COLMAP successfully optimizes only the camera poses (extrinsics). | Core |
| **S2.4** | **Alembic Conversion** | Implement the core `PyAlembic` logic to convert the optimized camera poses (position/rotation) into a time-based `.abc` camera track. | I/O (Alembic) |

## Sprint 3: GUI & Packaging

**Goal:** Build the user-facing application interface and prepare the application for distribution.

| Task ID | Description | Output / Success Criteria | Responsible Module |
| :--- | :--- | :--- | :--- |
| **S3.1** | **UI Layout** | Design and implement the main PySide window with input fields for video/JSON and separate start buttons for F-01 and F-02 modes. | UI |
| **S3.2** | **Input Handling** | Implement drag-and-drop and file dialogs for input files. | UI |
| **S3.3** | **Progress Reporting** | Implement a mechanism to stream and display the COLMAP console output and progress status in the GUI. | UI / Core |
| **S3.4** | **Packaging** | Create executable binaries (e.g., using PyInstaller or similar) for target platforms (Windows/macOS) bundling Python and dependencies. | Deployment |

## Sprint 4: Unreal Engine Integration & Final Testing

**Goal:** Validate the end-to-end workflow by integrating the outputs into UE5 using Python scripting.

| Task ID | Description | Output / Success Criteria | Responsible Module |
| :--- | :--- | :--- | :--- |
| **S4.1** | **UE Script: Lens File** | Develop the UE Python script to read the **`lens_calibration_data.json`** and automatically create a native **Lens File Asset** with the correct Brown-Conrady parameters.  | UE Integration |
| **S4.2** | **UE Script: Alembic Import** | Integrate the script to import the **`camera_path.abc`** and bind the track to a new Cine Camera Actor within a Level Sequence. | UE Integration |
| **S4.3** | **End-to-End Validation** | Test the full pipeline: Input video $\rightarrow$ App processing $\rightarrow$ UE Import $\rightarrow$ **Composure composite is visually seamless**. | Testing |
| **S4.4** | **Documentation** | Finalize project documentation, usage guide, and troubleshooting tips. | Documentation |

This structured approach ensures that the high-risk technical challenges (parameter injection and Alembic conversion) are tackled early, leading to a robust and deliverable product.