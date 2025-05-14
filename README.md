# Vid-Scratch

**Vid-Scratch** is a senior project focused on developing a system that defends against unauthorized AI training by poisoning visual datasets, specifically targeting AI generative and classification models. The ultimate goal is to apply adversarial poisoning to videos, making them appear unchanged to humans but unusable for AI training.

## Project Overview

**Image Poisoning Proof-of-Concept**: Utilizing the Fast Gradient Sign Method (FGSM) from the Adversarial Robustness Toolbox (ART) to poison a labeled image dataset (Cats vs Dogs) and evaluating the effect on AI classification performance.

## Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/Vid-Scratch-Senior-Project/Vid-Scratch.git
   cd Vid-Scratch

2. **Install dependencies**:
   - Python dependencies:
      ```bash
      pip install -r requirements.txt
   - Node.js dependencies:
      ```bash
      npm install

3. **Run the application**:
   ```bash
   npm start


## How to use
1. Click “📂 Select Image” to choose a .jpg or .png file from your computer.
2. Adjust the epsilon (ε) slider to control the intensity of the perturbation.
   - A small value (e.g., 0.01) introduces slight, stealthy noise (recommended).
   - A higher value (e.g., 0.1–1.0) introduces stronger but possibly more visible noise.
3. Click “Poison Image” to apply the adversarial attack using FGSM.
4. The poisoned image will be saved automatically to your Downloads folder.
