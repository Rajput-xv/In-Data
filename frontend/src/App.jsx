import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import NavBar from "./components/NavBar.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import UploadPage from "./pages/UploadPage.jsx";
import BatchesPage from "./pages/BatchesPage.jsx";
import ReviewPage from "./pages/ReviewPage.jsx";
import { isAuthed } from "./auth.js";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route element={<Protected />}>
        <Route path="/batches" element={<BatchesPage />} />
        <Route path="/review" element={<ReviewPage />} />
        <Route path="/upload" element={<UploadPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

// Wraps the three real pages with the navbar / footer chrome and
// bounces unauthenticated visitors back to the login screen.
function Protected() {
  if (!isAuthed()) return <Navigate to="/" replace />;
  return (
    <div className="min-h-full flex flex-col">
      <NavBar />
      <main className="flex-1 mx-auto w-full max-w-7xl px-6 py-8">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}

function Footer() {
  return (
    <footer className="border-t border-stone-200 bg-white">
      <div className="mx-auto max-w-7xl flex flex-wrap items-center justify-between gap-2 px-6 py-3 text-[11px] text-stone-500">
        <div className="flex items-center gap-3">
          <span className="font-mono">In-Data</span>
          <span className="text-stone-300">·</span>
          <span>Three sources, one activity table, one review surface.</span>
        </div>
      </div>
    </footer>
  );
}
