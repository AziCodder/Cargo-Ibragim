import { BrowserRouter, Routes, Route } from 'react-router-dom';
import MainPage from './pages/MainPage';
import ClosedPage from './pages/ClosedPage';
import CashbackPage from './pages/CashbackPage';
import ClientsPage from './pages/ClientsPage';
import ShipmentDetail from './pages/ShipmentDetail';
import CreateShipment from './pages/CreateShipment';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <Routes>
          <Route path="/" element={<MainPage />} />
          <Route path="/closed" element={<ClosedPage />} />
          <Route path="/cashback" element={<CashbackPage />} />
          <Route path="/clients" element={<ClientsPage />} />
          <Route path="/shipments/new" element={<CreateShipment />} />
          <Route path="/shipments/:id" element={<ShipmentDetail />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
