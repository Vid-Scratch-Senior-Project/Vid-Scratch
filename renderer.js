const { ipcRenderer, shell } = require('electron');

let selectedImagePath = null;

// Update slider value in real time
document.getElementById("epsSlider").addEventListener("input", (e) => {
  document.getElementById("epsValue").textContent = e.target.value;
});

// Open file dialog
document.getElementById("selectImageButton").addEventListener("click", () => {
  ipcRenderer.send("open-image-dialog");
});

ipcRenderer.on("selected-image", (event, filePath) => {
  if (filePath) {
    selectedImagePath = filePath;
    document.getElementById("selectedFileName").textContent = filePath.split(/[\\/]/).pop();
  } else {
    selectedImagePath = null;
    document.getElementById("selectedFileName").textContent = "No file selected";
  }
});

// Run poisoning
document.getElementById("poisonButton").addEventListener("click", () => {
  const epsilon = parseFloat(document.getElementById("epsSlider").value);
  if (!selectedImagePath) {
    document.getElementById("outputLog").textContent += "❌ No valid image selected.\n";
    return;
  }

  ipcRenderer.send("run-poisoning", {
    imagePath: selectedImagePath,
    epsilon: epsilon
  });
});

// Output results
ipcRenderer.on("poisoning-result", (event, message) => {
  document.getElementById("outputLog").textContent += message + "\n";
});

ipcRenderer.on("poisoning-complete", (event, poisonedPath) => {
  document.getElementById("outputLog").textContent += `✅ Saved to: ${poisonedPath}\n`;
  shell.showItemInFolder(poisonedPath);
});
