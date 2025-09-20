import React from 'react'
import ReactDOM from 'react-dom/client'

// Import the Tailwind + global styles
import './index.css'

// Import your main app component
import App from './App' // must resolve to src/App.tsx

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
