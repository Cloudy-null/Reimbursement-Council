# 012: EasyOCR on the GPU, taking turns with the model

Date: 2026-11-25. Status: accepted.

## Context

With the local model reader, a new photo took 13.855 seconds per claim through the website, most
of it EasyOCR on the CPU (the PyTorch build was CPU only). The owner asked for the CUDA build.

## Options

1. Keep the CPU build and read in parallel with the model (13.855 s).
2. CUDA build, EasyOCR and the model at the same time on the one 12 GB GPU.
3. CUDA build, EasyOCR and the model one after the other.

## Choice

Option 3. PyTorch 2.14.1+cu130 is pinned in the ocr extra, from the PyTorch CUDA 13.0 index on
Windows only (tool.uv.sources); other platforms get the normal build. The driver supports CUDA
13.1. EasyOCR uses the GPU when ocr.use_gpu is true and CUDA is there, else the CPU.

Option 2 ran out of GPU memory (11.8 of 12.3 GB) and was far slower, with model timeouts.
Option 3 measured 8.057 s per claim on the stand-in set (EXPERIMENTS, core day 4b).

## Trade-off

torch moved down from 2.15.0 to 2.14.1 (the newest version with a CUDA 13.0 wheel for Windows).
The wheel is large (about 2.5 GB); the uv cache is on D: (UV_CACHE_DIR). A laptop without an
NVIDIA GPU still works: the CUDA build falls back to the CPU.
