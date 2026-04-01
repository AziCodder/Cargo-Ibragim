import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import MainPage from './pages/MainPage';
import ClosedPage from './pages/ClosedPage';
import CashbackPage from './pages/CashbackPage';
import ClientsPage from './pages/ClientsPage';
import UsersPage from './pages/UsersPage';
import GroupsPage from './pages/GroupsPage';
import ShipmentDetail from './pages/ShipmentDetail';
import CreateShipment from './pages/CreateShipment';
import './App.css';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <div className="app">
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<ProtectedRoute><MainPage /></ProtectedRoute>} />
            <Route path="/closed" element={<ProtectedRoute><ClosedPage /></ProtectedRoute>} />
            <Route path="/cashback" element={<ProtectedRoute adminOnly><CashbackPage /></ProtectedRoute>} />
            <Route path="/clients" element={<ProtectedRoute adminOnly><ClientsPage /></ProtectedRoute>} />
            <Route path="/users" element={<ProtectedRoute adminOnly><UsersPage /></ProtectedRoute>} />
            <Route path="/groups" element={<ProtectedRoute adminOnly><GroupsPage /></ProtectedRoute>} />
            <Route path="/shipments/new" element={<ProtectedRoute adminOnly><CreateShipment /></ProtectedRoute>} />
            <Route path="/shipments/:id" element={<ProtectedRoute><ShipmentDetail /></ProtectedRoute>} />
          </Routes>
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
