import { useState, useEffect, useMemo } from 'react';
import { shipmentsApi } from '../api';
import NavBar from '../components/NavBar';
import ShipmentTable from '../components/ShipmentTable';

const STATUS_FILTER_CLOSED = { '': 'Все', delivered: 'Доставлено', cancelled: 'Отмена' };

function matchSearch(s, query) {
  if (!query || !String(query).trim()) return true;
  const q = String(query).trim().toLowerCase();
  const fields = [s.tracking, s.title, s.product_list, s.notes, s.delivery_date, s.dispatch_date, s.client_phone, s.client_name].filter(Boolean).map(String);
  return fields.some((f) => f.toLowerCase().includes(q) || f.toLowerCase() === q);
}

export default function ClosedPage() {
  const [shipments, setShipments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState('dispatch_date');
  const [order, setOrder] = useState('desc');
  const [statusFilter, setStatusFilter] = useState('');
  const [trackingFilter, setTrackingFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const load = () => {
    setLoading(true);
    shipmentsApi.listClosed({ sort, order })
      .then((r) => setShipments(r.data || []))
      .finally(() => setLoading(false));
  };

  useEffect(load, [sort, order]);

  const handleSort = (col) => {
    if (sort === col) setOrder((o) => (o === 'desc' ? 'asc' : 'desc'));
    else setSort(col);
  };

  const filtered = useMemo(() => {
    let list = shipments;
    if (statusFilter) list = list.filter((s) => s.status === statusFilter);
    if (trackingFilter && String(trackingFilter).trim()) {
      const t = String(trackingFilter).trim().toLowerCase();
      list = list.filter((s) => (s.tracking || '').toLowerCase().includes(t));
    }
    if (searchQuery && String(searchQuery).trim()) {
      list = list.filter((s) => matchSearch(s, searchQuery));
    }
    return list;
  }, [shipments, statusFilter, trackingFilter, searchQuery]);

  return (
    <>
      <NavBar />
      <h2 style={{ marginBottom: '1rem' }}>Закрытые накладные</h2>
      <div className="filters" style={{ marginBottom: '1rem', display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'flex-end' }}>
        <label>
          <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Статус</span>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            {Object.entries(STATUS_FILTER_CLOSED).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Трекинг</span>
          <input type="text" placeholder="подстрока" value={trackingFilter} onChange={(e) => setTrackingFilter(e.target.value)} style={{ width: '10rem' }} />
        </label>
        <label>
          <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Поиск</span>
          <input type="text" placeholder="по записи" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} style={{ width: '14rem' }} />
        </label>
      </div>
      {loading ? <p>Загрузка...</p> : (
        <ShipmentTable shipments={filtered} sort={sort} order={order} onSort={handleSort} />
      )}
      {!loading && filtered.length !== shipments.length && (
        <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>Показано: {filtered.length} из {shipments.length}</p>
      )}
    </>
  );
}
