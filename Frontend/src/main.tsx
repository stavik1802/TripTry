import React from "react";
import ReactDOM from "react-dom/client";
import UI from "../UI.jsx"; // adjust path if needed

// This replaces the default Vite main.tsx to render your UI.jsx instead of App.tsx
ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <UI />
  </React.StrictMode>
);
