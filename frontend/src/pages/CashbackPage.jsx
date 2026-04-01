import { useState, useEffect, useMemo, useCallback } from 'react';
import { shipmentsApi, clientsApi } from '../api';
import NavBar from '../components/NavBar';

const PAYMENT_FILTER = { all: 'Все', paid: 'Оплачено', unpaid: 'Не оплачено' };

function round3(x) {
  if (x == null || Number.isNaN(x)) return 0;
  return Math.round(Number(x));
}

function matchSearch(s, query) {
  if (!query || !String(query).trim()) return true;
  const q = String(query).trim().toLowerCase();
  const fields = [
    s.tracking, s.title, s.product_list, s.notes,
    s.delivery_date, s.dispatch_date, s.client_phone, s.client_name,
  ].filter(Boolean).map(String);
  return fields.some((f) => f.toLowerCase().includes(q));
}

function applyFilters(list, filters) {
  let out = list;
  const { payment, totalOp, totalVal, weightOp, weightVal, trackingSubstr, search, clientId } = filters;

  if (clientId) out = out.filter((s) => s.client_id === clientId);
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
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Локальные галочки (Set из id)
  const [localChecked, setLocalChecked] = useState(new Set());

  const [paymentFilter, setPaymentFilter] = useState('all');
  const [clientFilter, setClientFilter] = useState('');
  const [totalOp, setTotalOp] = useState('');
  const [totalVal, setTotalVal] = useState('');
  const [weightOp, setWeightOp] = useState('');
  const [weightVal, setWeightVal] = useState('');
  const [trackingFilter, setTrackingFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([shipmentsApi.listCashback(), clientsApi.list()])
      .then(([shRes, clRes]) => {
        const sh = shRes.data || [];
        setShipments(sh);
        setClients(clRes.data || []);
        // Инициализируем локальные галочки из БД
        setLocalChecked(new Set(sh.filter((s) => s.calculated).map((s) => s.id)));
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const toggleChecked = (id) => {
    setLocalChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Сохраняем в БД только те, что изменились
  const handleConfirm = async () => {
    const changed = shipments.filter((s) => {
      const wasChecked = s.calculated;
      const isChecked = localChecked.has(s.id);
      return wasChecked !== isChecked;
    });
    if (changed.length === 0) {
      alert('Нет изменений для сохранения');
      return;
    }
    setSaving(true);
    try {
      await Promise.all(
        changed.map((s) => shipmentsApi.updateCalculated(s.id, localChecked.has(s.id)))
      );
      await load();
    } finally {
      setSaving(false);
    }
  };

  const filtered = useMemo(
    () =>
      applyFilters(shipments, {
        payment: paymentFilter,
        clientId: clientFilter || null,
        totalOp: totalOp || null,
        totalVal,
        weightOp: weightOp || null,
        weightVal,
        trackingSubstr: trackingFilter,
        search: searchQuery,
      }),
    [shipments, paymentFilter, clientFilter, totalOp, totalVal, weightOp, weightVal, trackingFilter, searchQuery]
  );

  // Суммы на основе локальных галочек
  const checkedTotal = useMemo(
    () => filtered.filter((s) => localChecked.has(s.id)).reduce((sum, s) => sum + (s.cashback || 0) * (s.weight || 0), 0),
    [filtered, localChecked]
  );
  const uncheckedTotal = useMemo(
    () => filtered.filter((s) => !localChecked.has(s.id)).reduce((sum, s) => sum + (s.cashback || 0) * (s.weight || 0), 0),
    [filtered, localChecked]
  );

  // Кол-во изменений (подсвечиваем кнопку)
  const changedCount = useMemo(() => {
    return shipments.filter((s) => s.calculated !== localChecked.has(s.id)).length;
  }, [shipments, localChecked]);

  // Итоги по выбранному клиенту
  const clientSummary = useMemo(() => {
    if (!clientFilter) return null;
    const rows = filtered;
    const totalAmt = rows.reduce((s, x) => s + (x.cashback || 0) * (x.weight || 0), 0);
    const paidAmt = rows.filter((x) => localChecked.has(x.id)).reduce((s, x) => s + (x.cashback || 0) * (x.weight || 0), 0);
    const unpaidAmt = rows.filter((x) => !localChecked.has(x.id)).reduce((s, x) => s + (x.cashback || 0) * (x.weight || 0), 0);
    return { totalAmt, paidAmt, unpaidAmt, count: rows.length };
  }, [filtered, clientFilter, localChecked]);

  return (
    <>
      <NavBar />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2>Расчёт по кэшбеку</h2>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          {changedCount > 0 && (
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Изменено: {changedCount}
            </span>
          )}
          <button
            className="btn"
            onClick={handleConfirm}
            disabled={saving || changedCount === 0}
            style={{
              background: changedCount > 0 ? 'var(--success, #22c55e)' : undefined,
              color: changedCount > 0 ? '#fff' : undefined,
              fontWeight: changedCount > 0 ? 'bold' : undefined,
            }}
          >
            {saving ? 'Сохранение...' : 'Подтвердить'}
          </button>
          <button className="btn" onClick={load}>Обновить</button>
        </div>
      </div>

      <div className="filters" style={{ marginBottom: '1rem', display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'flex-end' }}>
        <label>
          <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Клиент</span>
          <select value={clientFilter} onChange={(e) => setClientFilter(e.target.value)} style={{ minWidth: '12rem' }}>
            <option value="">Все клиенты</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>{c.full_name || c.id}</option>
            ))}
          </select>
        </label>
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
          <input type="number" step="0.01" placeholder="число" value={totalVal} onChange={(e) => setTotalVal(e.target.value)} style={{ width: '6rem', marginLeft: '0.25rem' }} />
        </label>
        <label>
          <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Вес</span>
          <select value={weightOp} onChange={(e) => setWeightOp(e.target.value)} style={{ width: '4rem' }}>
            <option value="">—</option>
            <option value="gt">&gt;</option>
            <option value="lt">&lt;</option>
          </select>
          <input type="number" step="0.01" placeholder="число" value={weightVal} onChange={(e) => setWeightVal(e.target.value)} style={{ width: '6rem', marginLeft: '0.25rem' }} />
        </label>
        <label>
          <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Трекинг</span>
          <input type="text" placeholder="подстрока" value={trackingFilter} onChange={(e) => setTrackingFilter(e.target.value)} style={{ width: '10rem' }} />
        </label>
        <label style={{ marginLeft: '0.5rem' }}>
          <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Поиск</span>
          <input type="text" placeholder="значение в записи" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} style={{ width: '16rem' }} />
        </label>
      </div>

      {/* Итоги по клиенту */}
      {clientSummary && (
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', padding: '0.75rem 1rem', marginBottom: '1rem', display: 'flex', gap: '2rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <strong>{clients.find((c) => c.id === clientFilter)?.full_name || 'Клиент'}</strong>
          <span>Накладных: <b>{clientSummary.count}</b></span>
          <span>Итого: <b>{round3(clientSummary.totalAmt)}</b></span>
          <span style={{ color: 'var(--success)' }}>Оплачено: <b>{round3(clientSummary.paidAmt)}</b></span>
          <span style={{ color: 'var(--danger)' }}>Не оплачено: <b>{round3(clientSummary.unpaidAmt)}</b></span>
        </div>
      )}

      {loading ? (
        <p>Загрузка...</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Клиент</th>
                <th>Трекинг</th>
                <th>Дата отправления</th>
                <th>Кэшбек</th>
                <th>Вес</th>
                <th>Дата получения</th>
                <th>Итого</th>
                <th>Оплачено</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => {
                const isChecked = localChecked.has(s.id);
                const wasInDb = s.calculated;
                const changed = isChecked !== wasInDb;
                return (
                  <tr key={s.id} style={{ opacity: isChecked ? 0.75 : 1, background: changed ? 'rgba(234,179,8,0.08)' : undefined }}>
                    <td style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{s.client_name || s.client_phone || '—'}</td>
                    <td>{s.tracking || '—'}</td>
                    <td>{s.dispatch_date || '—'}</td>
                    <td>{s.cashback}</td>
                    <td>{s.weight ?? '—'}</td>
                    <td>{s.delivery_date || '—'}</td>
                    <td><strong>{round3((s.cashback || 0) * (s.weight || 0))}</strong></td>
                    <td>
                      <label style={{ cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleChecked(s.id)}
                        />
                        {' '}Да
                      </label>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {/* Итоги снизу */}
          {filtered.length > 0 && (
            <div style={{ padding: '0.5rem 1rem', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '1.5rem' }}>
              <span style={{ color: 'var(--danger)', fontWeight: 'bold', fontSize: '1.1rem' }}>
                {round3(uncheckedTotal)}
              </span>
              <span style={{ color: 'var(--success)', fontWeight: 'bold', fontSize: '1.1rem' }}>
                {round3(checkedTotal)}
              </span>
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
