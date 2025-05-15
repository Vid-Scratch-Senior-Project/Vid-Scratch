const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron');
const path = require('path');
const os = require('os');
const fs = require('fs');
const axios = require('axios');
const FormData = require('form-data');

function createWindow () {
  const win = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  win.loadFile('index.html');

  // Image selection
  ipcMain.on("open-image-dialog", async (event) => {
    const result = await dialog.showOpenDialog({
      properties: ['openFile'],
      filters: [{ name: 'Images', extensions: ['jpg', 'jpeg', 'png'] }]
    });

    if (!result.canceled && result.filePaths.length > 0) {
      event.reply("selected-image", result.filePaths[0]);
    } else {
      event.reply("selected-image", null);
    }
  });

  // Poisoning via FastAPI
  ipcMain.on("run-poisoning", async (event, args) => {
    const { imagePath, epsilon } = args;

    if (!imagePath || imagePath === "undefined") {
      event.reply("poisoning-result", "❌ No valid image selected.");
      return;
    }

    try {
      const imageBuffer = fs.readFileSync(imagePath);
      const formData = new FormData();
      formData.append("file", fs.createReadStream(imagePath));
      formData.append("eps", epsilon.toString());
      formData.append("threshold", "0.4"); // You can let user set this too

      // Use axios + form data
      const res = await axios.post("http://127.0.0.1:8000/poison", formData, {
        responseType: 'arraybuffer',
        headers: formData.getHeaders()
      });

      // Save poisoned image to Downloads folder
      const downloadsDir = path.join(os.homedir(), "Downloads");
      const originalName = path.basename(imagePath);
      const outputName = "poison_" + originalName.replace(/\.[^/.]+$/, "") + ".png";
      const outputPath = path.join(downloadsDir, outputName);

      fs.writeFileSync(outputPath, res.data);
      event.reply("poisoning-result", "✅ Poisoned image saved.");
      event.reply("poisoning-complete", outputPath);
      shell.showItemInFolder(outputPath);

    } catch (err) {
      event.reply("poisoning-result", `❌ Error during poisoning: ${err.message}`);
    }
  });
}

app.whenReady().then(createWindow);
