import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { shipmentsApi, recipientsApi, groupsApi, clientsApi } from '../api';
import NavBar from '../components/NavBar';
import ShipmentForm from '../components/ShipmentForm';

// По убыванию срока: сначала 20-30, затем 15-20, затем 1-7
const SHIPPING_OPTIONS = [
  { value: '20_30_days', label: '20-30 дней' },
  { value: '15_20_days', label: '15-20 дней' },
  { value: '1_7_days', label: '1-7 дней' },
];

const STATUS_OPTIONS = [
  { value: 'in_transit', label: 'В дороге' },
  { value: 'delivered', label: 'Доставлено' },
  { value: 'cancelled', label: 'Отмена' },
];

export default function CreateShipment() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    title: 'Отправка товара',
    tracking: '',
    product_list: '',
    notes: '',
    dispatch_date: new Date().toISOString().split('T')[0],
    delivery_date: '',
    status: 'in_transit',
    shipping_type: '20_30_days',
    weight: 0,
    amount_to_pay: 0,
    cashback: 0,
    calculated: false,
    client_id: null,
    client_phone: '',
  });
  const [saving, setSaving] = useState(false);
  const [files, setFiles] = useState([]);

  // Получатели уведомлений
  const [groups, setGroups] = useState([]);
  const [clients, setClients] = useState([]);
  const [recipients, setRecipients] = useState([]); // [{chat_id, label}]
  const [recType, setRecType] = useState('group');
  const [recGroupId, setRecGroupId] = useState('');
  const [recClientId, setRecClientId] = useState('');
  const [recManualId, setRecManualId] = useState('');
  const [recLabel, setRecLabel] = useState('');

  useEffect(() => {
    groupsApi.list().then((r) => setGroups(r.data || [])).catch(() => {});
    clientsApi.list().then((r) => setClients(r.data || [])).catch(() => {});
  }, []);

  const handleAddRecipient = () => {
    let chatId = '';
    let label = recLabel.trim();
    if (recType === 'group') {
      const g = groups.find((x) => x.chat_id === recGroupId);
      if (!g) { alert('Выберите группу'); return; }
      chatId = g.chat_id;
      if (!label) label = g.title;
    } else if (recType === 'client') {
      const c = clients.find((x) => x.id === recClientId);
      if (!c) { alert('Выберите клиента'); return; }
      if (!c.telegram_chat_id) { alert('У клиента нет Telegram Chat ID'); return; }
      chatId = c.telegram_chat_id;
      if (!label) label = c.full_name || c.phone || c.id;
    } else {
      chatId = recManualId.trim();
      if (!chatId) { alert('Введите Chat ID'); return; }
      if (!label) label = chatId;
    }
    if (recipients.find((r) => r.chat_id === chatId)) { alert('Уже добавлен'); return; }
    setRecipients((prev) => [...prev, { chat_id: chatId, label }]);
    setRecLabel('');
    setRecManualId('');
  };

  const removeRecipient = (chatId) => setRecipients((prev) => prev.filter((r) => r.chat_id !== chatId));

  const handleSubmit = (e) => {
    e.preventDefault();
    setSaving(true);
    const payload = {
      ...form,
      delivery_date: form.delivery_date || null,
      client_id: form.client_id || null,
      client_phone: form.client_phone || null,
    };
    shipmentsApi.create(payload)
      .then(async (r) => {
        const id = r.data.id;
        if (files.length) {
          const fd = new FormData();
          files.slice(0, 3).forEach((f, i) => fd.append(`file${i + 1}`, f));
          await shipmentsApi.uploadFiles(id, fd);
        }
        // Сохраняем получателей
        if (recipients.length) {
          await Promise.all(recipients.map((rec) => recipientsApi.add(id, rec)));
        }
        return id;
      })
      .then((id) => navigate(`/shipments/${id}`))
      .catch((e) => alert(e.response?.data?.detail || 'Ошибка'))
      .finally(() => setSaving(false));
  };

  return (
    <>
      <NavBar showBack backTo="/" />
      <h2 style={{ marginBottom: '1rem' }}>Создать накладную</h2>
      <form onSubmit={handleSubmit}>
        {/* Получатели уведомлений */}
        <div style={{ marginBottom: '1.5rem', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', padding: '1rem' }}>
          <h3 style={{ marginTop: 0, marginBottom: '0.5rem', fontSize: '1rem' }}>Получатели уведомлений</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
            Кому отправлять SMS при отправке и прибытии товара (помимо клиента накладной).
          </p>

          {/* Текущие получатели */}
          {recipients.length > 0 && (
            <div style={{ marginBottom: '0.75rem', display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
              {recipients.map((r) => (
                <span key={r.chat_id} style={{
                  display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
                  background: 'var(--bg)', border: '1px solid var(--border)',
                  borderRadius: '20px', padding: '3px 10px', fontSize: '0.85rem'
                }}>
                  {r.label}
                  <button onClick={() => removeRecipient(r.chat_id)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--danger)', fontWeight: 'bold', padding: '0 2px' }}>×</button>
                </span>
              ))}
            </div>
          )}

          {/* Форма добавления */}
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <select value={recType} onChange={(e) => setRecType(e.target.value)} style={{ minWidth: '130px' }}>
              <option value="group">Группа</option>
              <option value="client">Клиент</option>
              <option value="manual">Chat ID вручную</option>
            </select>

            {recType === 'group' && (
              <select value={recGroupId} onChange={(e) => setRecGroupId(e.target.value)} style={{ minWidth: '200px' }}>
                <option value="">— выберите группу —</option>
                {groups.map((g) => <option key={g.chat_id} value={g.chat_id}>{g.title} ({g.member_count} уч.)</option>)}
              </select>
            )}
            {recType === 'client' && (
              <select value={recClientId} onChange={(e) => setRecClientId(e.target.value)} style={{ minWidth: '200px' }}>
                <option value="">— выберите клиента —</option>
                {clients.filter((c) => c.telegram_chat_id).map((c) => (
                  <option key={c.id} value={c.id}>{c.full_name || c.phone || c.id}</option>
                ))}
              </select>
            )}
            {recType === 'manual' && (
              <input type="text" placeholder="Chat ID" value={recManualId}
                onChange={(e) => setRecManualId(e.target.value)} style={{ width: '160px' }} />
            )}
            <input type="text" placeholder="Подпись (необязательно)" value={recLabel}
              onChange={(e) => setRecLabel(e.target.value)} style={{ width: '180px' }} />
            <button type="button" className="btn" onClick={handleAddRecipient}>+ Добавить</button>
          </div>
        </div>

        <ShipmentForm
          form={form}
          setForm={setForm}
          shippingOptions={SHIPPING_OPTIONS}
          statusOptions={STATUS_OPTIONS}
        />
        <div className="form-group">
          <label>Файлы (до 3)</label>
          <input
            type="file"
            multiple
            onChange={(e) => setFiles(Array.from(e.target.files || []))}
          />
        </div>
        <div className="actions" style={{ marginTop: '1rem' }}>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? '...' : 'Сохранить'}
          </button>
        </div>
      </form>
    </>
  );
}
