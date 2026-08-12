import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AdminClientsPage } from "./pages/AdminClientsPage";
import { AdminPage } from "./pages/AdminPage";
import { ConsentPage } from "./pages/ConsentPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { VerifyEmailPage } from "./pages/VerifyEmailPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/consent" element={<ConsentPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/admin/clients" element={<AdminClientsPage />} />
        <Route path="/" element={<DashboardPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
