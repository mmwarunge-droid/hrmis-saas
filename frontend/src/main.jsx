import React from 'react';
import ReactDOM from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import App from './App.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';
import { AuthProvider } from './context/AuthContext.jsx';
import { TenantProvider } from './context/TenantContext.jsx';
import { ToastProvider } from './context/ToastContext.jsx';
import './styles/index.css';

const router = createBrowserRouter([{ path: '*', element: (
  <ErrorBoundary><AuthProvider>
    <TenantProvider>
      <ToastProvider><App /></ToastProvider>
    </TenantProvider>
  </AuthProvider></ErrorBoundary>
) }]);

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary><RouterProvider router={router} /></ErrorBoundary>
  </React.StrictMode>,
);
