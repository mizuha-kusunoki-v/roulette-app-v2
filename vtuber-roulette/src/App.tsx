import { BrowserRouter, Navigate, Routes, Route } from "react-router-dom";
import AdminApp from "./AdminApp";
import { ResultViewerPage } from "./viewer/ResultViewerPage";

const App = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AdminApp />} />
        <Route path="/viewer" element={<Navigate to="/viewer/result" replace />} />
        <Route path="/viewer/result" element={<ResultViewerPage />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
