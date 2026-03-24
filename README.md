# Vid-Scratch

[![CI](https://github.com/Vid-Scratch-Senior-Project/Vid-Scratch/actions/workflows/ci.yml/badge.svg)](https://github.com/Vid-Scratch-Senior-Project/Vid-Scratch/actions/workflows/ci.yml)

Vid-Scratch is a desktop application for adversarial video poisoning and robustness testing.  
It is designed to generate visually similar but model-disruptive video outputs through a Tauri-based desktop interface connected to a Python processing engine.

---

## Overview

Vid-Scratch combines:
- a **Tauri desktop frontend** for user interaction
- a **Python backend engine** for adversarial video generation
- a workflow for uploading videos, configuring attack settings, previewing outputs, and exporting results

The project focuses on studying how action recognition systems can be affected by sparse perturbations while keeping the result close to the original video for human viewers.

---

## Features

- Upload and process video files
- Configure poisoning or adversarial generation settings
- Generate sparse perturbations on selected frames
- Use spatial transformation and SSIM-based constraints
- Preview processed outputs
- Export generated videos
- Desktop app workflow with Tauri
- Automated testing with GitHub Actions

---

## Project Structure

~~~bash
VID-SCRATCH/
├── .github/
│   └── workflows/
│       └── ci.yml
├── python/
│   ├── attack.py
│   ├── model_wrapper.py
│   ├── spatial_transformer.py
│   ├── ssim.py
│   ├── video_io.py
│   └── vidscratch.py
├── tauri-app/
│   ├── components/
│   ├── public/
│   ├── src/
│   ├── src-tauri/
│   │   ├── capabilities/
│   │   ├── engine/
│   │   ├── icons/
│   │   ├── src/
│   │   ├── Cargo.toml
│   │   ├── build.rs
│   │   └── tauri.conf.json
│   ├── package.json
│   ├── vite.config.ts
│   ├── vitest.config.ts
│   └── README.md
├── LICENSE
├── main.js
├── package.json
├── preload.js
└── index.html
~~~

---

## Tech Stack

### Frontend
- React
- TypeScript
- Vite
- Tauri

### Backend
- Python
- PyTorch
- OpenCV
- NumPy
- SciPy

### Testing / DevOps
- Pytest
- Vitest
- GitHub Actions

---

## Installation

### 1. Clone the repository

~~~bash
git clone https://github.com/Vid-Scratch-Senior-Project/Vid-Scratch
cd VID-SCRATCH
~~~

### 2. Install Python dependencies

Go to the Python folder and install the required packages.

~~~bash
cd python
pip install -r requirements.txt
~~~

If there is no `requirements.txt` yet, install the main dependencies manually.

~~~bash
pip install torch numpy opencv-python scipy pytest
~~~

### 3. Install Tauri app dependencies

Go to the Tauri application folder and install Node.js packages.

~~~bash
cd ../tauri-app
npm install
~~~

### 4. Make sure Tauri prerequisites are installed

Before running the app, make sure your machine already has:
- Node.js and npm
- Rust and Cargo
- Tauri system prerequisites for your OS

---

## Running the Application

From the `tauri-app` folder, start the desktop app in development mode:

~~~bash
npm run tauri dev
~~~

This is the main way to run the system during development.

---

## Running Tests

### Python tests

~~~bash
cd python
python -m pytest -q
~~~

### Frontend tests

~~~bash
cd ../tauri-app
npm test
~~~

If your frontend test script is different, use the script defined in `tauri-app/package.json`.

---

## How It Works

The general workflow is:

1. Launch the Tauri desktop application
2. Upload a video file
3. Configure poisoning or adversarial settings
4. Start the generation process
5. Let the Python engine process the video
6. Preview the generated result
7. Export the output video

---

## Example Development Workflow

~~~bash
cd python
pip install -r requirements.txt

cd ../tauri-app
npm install
npm run tauri dev
~~~

Run tests:

~~~bash
cd ../python
python -m pytest -q
~~~

---

## GitHub Actions CI

This repository includes GitHub Actions for continuous integration.

The CI workflow automatically runs when code is pushed or when a pull request is opened.

After pushing your code:
1. Open the repository on GitHub
2. Go to the **Actions** tab
3. Check whether the workflow passes successfully

---

## Research Motivation

As AI systems become better at understanding and classifying video content, creators have less control over how their media is interpreted by machine learning models.  
Vid-Scratch explores a practical way to generate adversarial video outputs that remain close to the original for people, while affecting how AI models interpret them.

This project can be used for:
- adversarial machine learning experiments
- robustness evaluation
- AI security demonstrations
- research on creator-oriented protection tools

---

## Current Status

Vid-Scratch is currently under development.  
The desktop interface, processing pipeline, and testing workflow are actively being integrated and improved.

---

## Roadmap

- Improve desktop app usability
- Add better attack parameter presets
- Improve preview and export workflow
- Extend support for more evaluation settings
- Improve packaging and release flow
- Add more experiment and benchmark results

---

## Contributing

Contributions, issues, and suggestions are welcome.  
Feel free to fork the repository and open a pull request.

---

## License

This project is released under the license provided in this repository.

---

## Author

**Pichayoot Tanasinanan**  
Kasetsart University  
Software and Knowledge Engineering
