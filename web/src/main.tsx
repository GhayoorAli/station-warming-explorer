import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage";
import StationPage from "./pages/StationPage";
import "./styles.css";

function App() {
  return (
    <BrowserRouter>
      <header className="site-head no-print">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true" />
          Station Warming Explorer
        </Link>
      </header>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/station/:id" element={<StationPage />} />
        <Route
          path="*"
          element={
            <main className="page">
              <p>Page not found. <Link to="/">Go to start</Link></p>
            </main>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
