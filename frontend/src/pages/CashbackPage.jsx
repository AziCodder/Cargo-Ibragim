import { useState, useEffect, useMemo } from 'react';
import { shipmentsApi } from '../api';
import NavBar from '../components/NavBar';

const PAYMENT_FILTER = { all: 'Все', paid: 'Оплачено', unpaid: 'Не оплачено' };

function round3(x) {
  if (x == null || Number.isNaN(x)) return 0;
  return Math.round(Number(x) * 1000) / 1000;
}

function matchSearch(s, query) {
  if (!query || !String(query).trim()) return true;
  const q = String(query).trim().toLowerCase();
  const fields = [
    s.tracking,
    s.title,
    s.product_list,
    s.notes,
    s.delivery_date,
    s.dispatch_date,
    s.client_phone,
  ].filter(Boolean).map(String);
  return fields.some((f) => f.toLowerCase().includes(q) || f.toLowerCase() === q);
}

function applyFilters(list, filters) {
  let out = list;
  const { payment, totalOp, totalVal, weightOp, weightVal, trackingSubstr, search } = filters;

  if (payment === 'paid') out = out.filter((s) => s.calculated);
  if (payment === 'unpaid') out = out.filter((s) => !s.calculated);

  if (totalOp && totalVal != null && totalVal !== '') {
    const v = parseFloat(totalVal);
    if (!Number.isNaN(v)) {
      const getTotal = (s) => (s.cashback || 0) * (s.weight || 0);
      if (totalOp === 'gt') out = out.filter((s) => getTotal(s) > v);
      if (totalOp === 'lt') out = out.filter((s) => getTotal(s) < v);
    }
  }

  if (weightOp && weightVal != null && weightVal !== '') {
    const v = parseFloat(weightVal);
    if (!Number.isNaN(v)) {
      const w = (s) => s.weight ?? 0;
      if (weightOp === 'gt') out = out.filter((s) => w(s) > v);
      if (weightOp === 'lt') out = out.filter((s) => w(s) < v);
    }
  }

  if (trackingSubstr && String(trackingSubstr).trim()) {
    const t = String(trackingSubstr).trim().toLowerCase();
    out = out.filter((s) => (s.tracking || '').toLowerCase().includes(t));
  }

  if (search && String(search).trim()) {
    out = out.filter((s) => matchSearch(s, search));
  }

  return out;
}

export default function CashbackPage() {
  const [shipments, setShipments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [paymentFilter, setPaymentFilter] = useState('all');
  const [totalOp, setTotalOp] = useState('');
  const [totalVal, setTotalVal] = useState('');
  const [weightOp, setWeightOp] = useState('');
  const [weightVal, setWeightVal] = useState('');
  const [trackingFilter, setTrackingFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const load = () => {
    setLoading(true);
    shipmentsApi.listCashback()
      .then((r) => setShipments(r.data || []))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleCalculated = (id, calculated) => {
    shipmentsApi.updateCalculated(id, calculated).then(() => load());
  };

  const filtered = useMemo(
    () =>
      applyFilters(shipments, {
        payment: paymentFilter,
        totalOp: totalOp || null,
        totalVal: totalVal,
        weightOp: weightOp || null,
        weightVal: weightVal,
        trackingSubstr: trackingFilter,
        search: searchQuery,
      }),
    [shipments, paymentFilter, totalOp, totalVal, weightOp, weightVal, trackingFilter, searchQuery]
  );

  const total = useMemo(
    () => filtered.reduce((s, x) => s + (x.cashback || 0) * (x.weight || 0), 0),
    [filtered]
  );

  const owed = useMemo(
    () => filtered.filter((x) => !x.calculated).reduce((s, x) => s + (x.cashback || 0) * (x.weight || 0), 0),
    [filtered]
  );
  const received = useMemo(
    () => filtered.filter((x) => x.calculated).reduce((s, x) => s + (x.cashback || 0) * (x.weight || 0), 0),
    [filtered]
  );

  return (
    <>
      <NavBar />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2>Расчёт по кэшбеку</h2>
        <button className="btn" onClick={load}>Обновить</button>
      </div>

      <div className="filters" style={{ marginBottom: '1rem', display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'flex-end' }}>
        <label>
          <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Оплата</span>
          <select value={paymentFilter} onChange={(e) => setPaymentFilter(e.target.value)}>
            {Object.entries(PAYMENT_FILTER).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Итого</span>
          <select value={totalOp} onChange={(e) => setTotalOp(e.target.value)} style={{ width: '4rem' }}>
            <option value="">—</option>
            <option value="gt">&gt;</option>
            <option value="lt">&lt;</option>
          </select>
          <input
            type="number"
            step="0.01"
            placeholder="число"
            value={totalVal}
            onChange={(e) => setTotalVal(e.target.value)}
            style={{ width: '6rem', marginLeft: '0.25rem' }}
          />
        </label>
        <label>
          <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Вес</span>
          <select value={weightOp} onChange={(e) => setWeightOp(e.target.value)} style={{ width: '4rem' }}>
            <option value="">—</option>
            <option value="gt">&gt;</option>
            <option value="lt">&lt;</option>
          </select>
          <input
            type="number"
            step="0.01"
            placeholder="число"
            value={weightVal}
            onChange={(e) => setWeightVal(e.target.value)}
            style={{ width: '6rem', marginLeft: '0.25rem' }}
          />
        </label>
        <label>
          <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Трекинг</span>
          <input
            type="text"
            placeholder="подстрока"
            value={trackingFilter}
            onChange={(e) => setTrackingFilter(e.target.value)}
            style={{ width: '10rem' }}
          />
        </label>
        <label style={{ marginLeft: '0.5rem' }}>
          <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Поиск</span>
          <input
            type="text"
            placeholder="значение в записи (точное или в строке)"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: '18rem' }}
          />
        </label>
      </div>

      {loading ? (
        <p>Загрузка...</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Трекинг</th>
                <th>Дата отправления</th>
                <th>Кэшбек</th>
                <th>Вес</th>
                <th>Дата получения</th>
                <th>Итого</th>
                <th>Рассчитано</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => (
                <tr key={s.id} style={s.calculated ? { opacity: 0.85 } : undefined}>
                  <td>{s.tracking || '—'}</td>
                  <td>{s.dispatch_date || '—'}</td>
                  <td>{s.cashback}</td>
                  <td>{s.weight ?? '—'}</td>
                  <td>{s.delivery_date || '—'}</td>
                  <td><strong>{round3((s.cashback || 0) * (s.weight || 0))}</strong></td>
                  <td>
                    <label>
                      <input
                        type="checkbox"
                        checked={s.calculated}
                        onChange={(e) => handleCalculated(s.id, e.target.checked)}
                      />
                      {' '}Да
                    </label>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length > 0 && (
            <div style={{ padding: '1rem', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
              <span>Показано: {filtered.length} из {shipments.length}. Итог по отфильтрованным: {round3(total)}</span>
              <div style={{ display: 'flex', gap: '1.5rem', fontWeight: 'bold' }}>
                <span style={{ color: 'var(--danger)' }}>{round3(owed)}</span>
                <span style={{ color: 'var(--success)' }}>{round3(received)}</span>
              </div>
            </div>
          )}
          {filtered.length === 0 && !loading && (
            <p style={{ padding: '1rem', color: 'var(--text-muted)' }}>
              {shipments.length === 0 ? 'Нет доставленных накладных.' : 'Нет записей по выбранным фильтрам.'}
            </p>
          )}
        </div>
      )}
    </>
  );
}
