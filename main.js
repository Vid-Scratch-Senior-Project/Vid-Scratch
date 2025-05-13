const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron');
const path = require('path');
const os = require('os');
const fs = require('fs');
const { spawn } = require('child_process');

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

  // Select image dialog
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

  // Run poisoning
  ipcMain.on("run-poisoning", (event, args) => {
    const { imagePath, epsilon } = args;

    if (!imagePath || imagePath === "undefined") {
      event.reply("poisoning-result", "❌ No valid image selected.");
      return;
    }

    const downloadsDir = path.join(os.homedir(), "Downloads");
    const originalName = path.basename(imagePath);
    const outputName = "poison_" + originalName.replace(/\.[^/.]+$/, "") + ".png";
    const outputPath = path.join(downloadsDir, outputName);

    const script = spawn('python', ['backend/poison.py', imagePath, epsilon, outputPath]);

    script.stdout.on('data', (data) => {
      event.reply("poisoning-result", data.toString());
    });

    script.stderr.on('data', (data) => {
      event.reply("poisoning-result", `❌ Error: ${data.toString()}`);
    });

    script.on('close', (code) => {
      if (code === 0) {
        event.reply("poisoning-complete", outputPath);
      } else {
        event.reply("poisoning-result", `❌ Script exited with code ${code}`);
      }
    });
  });
}

app.whenReady().then(createWindow);
