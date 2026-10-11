# Ambystoma reference review

Reviewed 12 October 2026. Scope: all eight projects listed in the [official portfolio](https://ambystomatechnologies.github.io/), their public product pages and selected linked source. This is a feature/source review, not runtime validation of every application or independent verification of scientific accuracy.

## Portfolio coverage

| Official project | Main capability | Useful idea for Kinetic |
| --- | --- | --- |
| [2D Wind Tunnel](https://ambystomatechnologies.github.io/wind-tunnel-simulator/) · [source](https://github.com/ambystomatechnologies/wind-tunnel-simulator) | Editable airfoils/obstacles, field views, probes, telemetry, experiment presets and saved scenes. | Direct geometry editing with immediate visual and numerical feedback. |
| [2D Optics](https://ambystomatechnologies.github.io/optic-simulator/) · [source](https://github.com/ambystomatechnologies/optic-simulator) | Geometrical ray tracing, deformable lenses, dispersion and detector plots. | Reuse interaction conventions across labs; make measurements visible beside the experiment. |
| [AnatoCut / 3D Viewer](https://ambystomatechnologies.github.io/visor-3d/) · [source](https://github.com/ambystomatechnologies/visor-3d) | Model import, clipping planes, animated scanning and display modes. | Inspect interiors without modifying imported geometry. Displayed section caps do not establish internal material structure. |
| [Open Galileo](https://github.com/BrandonAntonioSeguraTorres/Open-Galileo/releases/tag/Open-Galileo) · [source](https://github.com/BrandonAntonioSeguraTorres/Open-Galileo) | Focus stacking and low-signal image integration with batch processing. | Explicit processing stages, previews and progress. |
| [ECG Monitor](https://ambystomatechnologies.github.io/Real_Time_ECG_Monitor/) · [release/source](https://github.com/BrandonAntonioSeguraTorres/Real-Time-ECG-Monitor-PyQt5-PyAudio-/releases/tag/ecg_monitor) | Hardware guide, live signal acquisition, filtering, recording and replay. | Probe histories, calibrated axes and replayable experiment evidence. |
| [Cell Count / Axi IA](https://play.google.com/store/apps/details?id=com.cellcount.axiia) | Android image counting, calibrated measurements and analysis history. | Calibration before measurement and editable records; assisted estimates remain distinguishable from verified measurements. |
| [Voice Reader & Transcriptions](https://ambystomatechnologies.github.io/lector-de-voz-y-transcripciones-gratis/) · [source](https://github.com/ambystomatechnologies/lector-de-voz-y-transcripciones-gratis) | Document reading, pronunciation rules, transcription and export. | Accessible guidance and clear import/preview/run/export stages. |
| [PDF Tools Studio](https://ambystomatechnologies.github.io/pdf-tools-ambystoma-studio/) · [source](https://github.com/ambystomatechnologies/pdf-tools-ambystoma-studio) | Visual page selection, merging, splitting and image-to-PDF creation. | Previewable selection and straightforward experiment-report downloads. |

## Wind-tunnel fidelity observations

Source links below pin the reviewed revision, `c14a1ed597fb8e76132f3d1493d4a82ba4b7113f`.

- The controller creates separate 160×90 Navier–Stokes and 200×100 LBM fields. These are distinct execution paths, not interchangeable render styles over identical state. [Initialization](https://github.com/ambystomatechnologies/wind-tunnel-simulator/blob/c14a1ed597fb8e76132f3d1493d4a82ba4b7113f/js/canvas.js#L44).
- LBM telemetry uses fixed reference values `95` for Reynolds number and `22` for coefficients, rather than deriving both from selected geometry. [Telemetry](https://github.com/ambystomatechnologies/wind-tunnel-simulator/blob/c14a1ed597fb8e76132f3d1493d4a82ba4b7113f/js/canvas.js#L952).
- UI controls map displayed physical quantities to lattice parameters; collision floors viscosity and caps speed. This is insufficient evidence of calibrated SI equivalence. [Speed mapping](https://github.com/ambystomatechnologies/wind-tunnel-simulator/blob/c14a1ed597fb8e76132f3d1493d4a82ba4b7113f/js/app.js#L370), [viscosity mapping](https://github.com/ambystomatechnologies/wind-tunnel-simulator/blob/c14a1ed597fb8e76132f3d1493d4a82ba4b7113f/js/app.js#L502), [collision](https://github.com/ambystomatechnologies/wind-tunnel-simulator/blob/c14a1ed597fb8e76132f3d1493d4a82ba4b7113f/js/lbm.js#L252).
- The projection correction is used directly in force integration; pressure extrema receive an additional factor of ten. Our inference: displayed pressure/force requires dimensional and benchmark validation before quantitative reuse. [Projection](https://github.com/ambystomatechnologies/wind-tunnel-simulator/blob/c14a1ed597fb8e76132f3d1493d4a82ba4b7113f/js/physics.js#L424), [integration](https://github.com/ambystomatechnologies/wind-tunnel-simulator/blob/c14a1ed597fb8e76132f3d1493d4a82ba4b7113f/js/physics.js#L806).
- Vorticity confinement is active. A periodic wake-excitation method exists, but the reviewed `step()` does not call it. Method existence and documentation do not prove runtime forcing. [Step and method](https://github.com/ambystomatechnologies/wind-tunnel-simulator/blob/c14a1ed597fb8e76132f3d1493d4a82ba4b7113f/js/physics.js#L198).

Use this reference for interaction and educational presentation, not numerical ground truth or validated engineering coefficients.

## Ideas being applied

The current Kinetic work is applying an obstacle list with NACA/polygon shapes, experiment presets, smoke/speed/vorticity/pressure-correction views, streamlines, a probe and JSON export. This review does not verify those changes; consult [verification](verification.md) for completed checks. The fluid lab remains an educational 2-D solver, separate from MuJoCo rigid-body fluid forces and RL execution.

No product code or assets were copied. We are borrowing workflow ideas and implementing them within Kinetic's existing contracts.

## Visible license status

Wind tunnel and optics advertise MIT, but their reviewed repository trees contain no LICENSE file. No explicit license file was found for the viewer, PDF or voice repositories either. [Open Galileo](https://github.com/BrandonAntonioSeguraTorres/Open-Galileo) states CC BY-NC 4.0. The ECG website says GPL, while its linked repository contains an [MIT LICENSE](https://github.com/BrandonAntonioSeguraTorres/Real-Time-ECG-Monitor-PyQt5-PyAudio-/blob/main/LICENSE). These inconsistencies would need resolving before any future code reuse. No public source license was established for the Android app.
