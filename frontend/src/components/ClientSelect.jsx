import { useState, useEffect } from 'react';
import { clientsApi } from '../api';

const MANUAL_PHONE = '__manual_phone__';

export default function ClientSelect({ clientId, onClientIdChange, clientPhone, onClientPhoneChange, disabled }) {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [manualMode, setManualMode] = useState(false);

  useEffect(() => {
    clientsApi.list()
      .then((r) => setClients(r.data || []))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!clientId && clientPhone) setManualMode(true);
  }, [clientId, clientPhone]);

  const selectValue = clientId || (manualMode || clientPhone ? MANUAL_PHONE : '');

  const handleSelect = (e) => {
    const v = e.target.value;
    if (v === MANUAL_PHONE) {
      setManualMode(true);
      onClientIdChange(null);
      onClientPhoneChange?.(clientPhone || '');
    } else {
      setManualMode(false);
      onClientIdChange(v || null);
      onClientPhoneChange?.('');
    }
  };

  return (
    <div className="form-group">
      <label>Клиент (за кем закреплена накладная)</label>
      <select value={selectValue} onChange={handleSelect} disabled={loading || disabled}>
        <option value="">— Не выбран</option>
        {clients.map((c) => (
          <option key={c.id} value={c.id}>
            {c.full_name} ({c.city}){c.telegram_chat_id ? ' ✓ TG' : ''}
          </option>
        ))}
        <option value={MANUAL_PHONE}>Ввести телефон вручную (без TG, уведомления недоступны)</option>
      </select>
      {selectValue === MANUAL_PHONE && (
        <input
          type="tel"
          placeholder="Номер телефона"
          value={clientPhone || ''}
          onChange={(e) => onClientPhoneChange?.(e.target.value)}
          disabled={disabled}
          style={{ marginTop: '0.5rem', width: '100%', padding: '0.5rem 0.75rem', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)' }}
        />
      )}
    </div>
  );
}
