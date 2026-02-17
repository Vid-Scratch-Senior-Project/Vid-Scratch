import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import "./App.css";
import PoisoningProcessor from '../components/PoisoningPage/PoisoningProcessor';

function App() {

  return (
    <main className="container">
      <PoisoningProcessor />
    </main>
  );
}

export default App;
