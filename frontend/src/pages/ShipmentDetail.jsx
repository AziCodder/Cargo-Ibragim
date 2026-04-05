import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { shipmentsApi, recipientsApi, groupsApi, clientsApi } from '../api';
import { useAuth } from '../context/AuthContext';
import NavBar from '../components/NavBar';
import ShipmentForm from '../components/ShipmentForm';

const SHIPPING_OPTIONS = [
  { value: '1_7_days', label: '1-7 дней' },
  { value: '15_20_days', label: '15-20 дней' },
  { value: '20_30_days', label: '20-30 дней' },
];

const STATUS_OPTIONS = [
  { value: 'in_transit', label: 'В дороге' },
  { value: 'delivered', label: 'Доставлено' },
  { value: 'cancelled', label: 'Отмена' },
];

export default function ShipmentDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();

  const [shipment, setShipment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({});

  // Для клиентского режима: отдельный select статуса
  const [clientStatus, setClientStatus] = useState('');
  const [savingStatus, setSavingStatus] = useState(false);

  // Получатели уведомлений
  const [recipients, setRecipients] = useState([]);
  const [groups, setGroups] = useState([]);
  const [clients, setClients] = useState([]);
  const [recipientType, setRecipientType] = useState('group'); // 'group' | 'client' | 'manual'
  const [recipientGroupId, setRecipientGroupId] = useState('');
  const [recipientClientId, setRecipientClientId] = useState('');
  const [recipientManualId, setRecipientManualId] = useState('');
  const [recipientLabel, setRecipientLabel] = useState('');
  const [addingRecipient, setAddingRecipient] = useState(false);

  const loadRecipients = useCallback(() => {
    if (!id) return;
    recipientsApi.list(id).then((r) => setRecipients(r.data || [])).catch(() => {});
  }, [id]);

  useEffect(() => {
    if (isAdmin) {
      groupsApi.list().then((r) => setGroups(r.data || [])).catch(() => {});
      clientsApi.list().then((r) => setClients(r.data || [])).catch(() => {});
      loadRecipients();
    }
  }, [isAdmin, loadRecipients]);

  useEffect(() => {
    shipmentsApi.get(id)
      .then((r) => {
        setShipment(r.data);
        setClientStatus(r.data.status || 'in_transit');
        setForm({
          title: r.data.title || '',
          tracking: r.data.tracking || '',
          product_list: r.data.product_list || '',
          notes: r.data.notes || '',
          dispatch_date: r.data.dispatch_date || '',
          delivery_date: r.data.delivery_date || '',
          status: r.data.status || 'in_transit',
          shipping_type: r.data.shipping_type || '1_7_days',
          weight: r.data.weight ?? 0,
          amount_to_pay: r.data.amount_to_pay ?? 0,
          cashback: r.data.cashback ?? 0,
          calculated: r.data.calculated ?? false,
          client_id: r.data.client_id || null,
          client_phone: r.data.client_phone || '',
        });
      })
      .catch((e) => {
        if (e.response?.status === 403) {
          alert('Доступ запрещён');
          navigate('/');
        }
      })
      .finally(() => setLoading(false));
  }, [id]);

  // --- Admin handlers ---
  const handleSave = () => {
    setSaving(true);
    const payload = {
      ...form,
      dispatch_date: form.dispatch_date,
      delivery_date: form.delivery_date || null,
      client_id: form.client_id || null,
      client_phone: form.client_phone || null,
    };
    shipmentsApi.update(id, payload)
      .then(() => setShipment((s) => ({ ...s, ...form })))
      .catch((e) => alert(e.response?.data?.detail || 'Ошибка'))
      .finally(() => setSaving(false));
  };

  const handleDelete = () => {
    if (!confirm('Удалить накладную? Это действие нельзя отменить.')) return;
    shipmentsApi.delete(id).then(() => navigate('/'));
  };

  const handleNotifyDispatch = () => {
    shipmentsApi.notifyDispatch(id).then(() => {
      setShipment((s) => ({ ...s, dispatch_notified: true }));
      alert('Уведомление отправлено');
    }).catch((e) => alert(e.response?.data?.detail || 'Ошибка'));
  };

  const handleNotifyDelivery = () => {
    if (!form.delivery_date) {
      alert('Пожалуйста, укажите дату прибытия в накладной.');
      return;
    }
    shipmentsApi.notifyDelivery(id).then(() => {
      setShipment((s) => ({ ...s, delivery_notified: true }));
      alert('Уведомление отправлено');
    }).catch((e) => alert(e.response?.data?.detail || 'Ошибка'));
  };

  const handleAddRecipient = async () => {
    let chatId = '';
    let label = recipientLabel.trim();

    if (recipientType === 'group') {
      const g = groups.find((x) => x.chat_id === recipientGroupId);
      if (!g) { alert('Выберите группу'); return; }
      chatId = g.chat_id;
      if (!label) label = g.title;
    } else if (recipientType === 'client') {
      const c = clients.find((x) => x.id === recipientClientId);
      if (!c) { alert('Выберите клиента'); return; }
      // Используем telegram_chat_id клиента
      if (!c.telegram_chat_id) { alert('У клиента нет Telegram Chat ID'); return; }
      chatId = c.telegram_chat_id;
      if (!label) label = c.full_name || c.phone || c.id;
    } else {
      chatId = recipientManualId.trim();
      if (!chatId) { alert('Введите Chat ID'); return; }
      if (!label) label = chatId;
    }

    setAddingRecipient(true);
    try {
      await recipientsApi.add(id, { chat_id: chatId, label });
      setRecipientLabel('');
      setRecipientManualId('');
      loadRecipients();
    } catch (e) {
      alert(e.response?.data?.detail || 'Ошибка добавления');
    } finally {
      setAddingRecipient(false);
    }
  };

  const handleRemoveRecipient = async (recId) => {
    await recipientsApi.remove(id, recId).catch((e) => alert(e.response?.data?.detail || 'Ошибка'));
    loadRecipients();
  };

  const handleDownloadFile = async (slot) => {
    try {
      const res = await shipmentsApi.getFileUrl(id, slot);
      window.open(res.data.url, '_blank');
    } catch (e) {
      alert(e.response?.data?.detail || 'Ошибка получения файла');
    }
  };

  const handleDeleteFile = async (slot) => {
    if (!confirm(`Удалить файл ${slot}?`)) return;
    try {
      const res = await shipmentsApi.deleteFile(id, slot);
      setShipment(res.data);
    } catch (e) {
      alert(e.response?.data?.detail || 'Ошибка удаления файла');
    }
  };

  const handleFileUpload = (e) => {
    const files = e.target.files;
    if (!files?.length) return;
    const freeSlotNumbers = [1, 2, 3].filter((i) => !shipment[`file${i}`]);
    if (freeSlotNumbers.length === 0) {
      alert('Уже загружено 3 файла. Удалите лишние, чтобы добавить новые.');
      e.target.value = '';
      return;
    }
    const fd = new FormData();
    const toAdd = Math.min(freeSlotNumbers.length, files.length);
    for (let i = 0; i < toAdd; i++) {
      fd.append(`file${freeSlotNumbers[i]}`, files[i]);
    }
    shipmentsApi.uploadFiles(id, fd).then((r) => setShipment(r.data));
    e.target.value = '';
  };

  // --- Client handler: только статус ---
  const handleSaveStatus = () => {
    setSavingStatus(true);
    shipmentsApi.update(id, { status: clientStatus })
      .then((r) => {
        setShipment((s) => ({ ...s, status: r.data.status }));
        setForm((f) => ({ ...f, status: r.data.status }));
        alert('Статус обновлён');
      })
      .catch((e) => alert(e.response?.data?.detail || 'Ошибка'))
      .finally(() => setSavingStatus(false));
  };

  if (loading) return <><NavBar showBack backTo="/" /><p>Загрузка...</p></>;
  if (!shipment) return <><NavBar showBack backTo="/" /><p>Накладная не найдена</p></>;

  // ========== КЛИЕНТСКИЙ РЕЖИМ ==========
  if (!isAdmin) {
    return (
      <>
        <NavBar showBack backTo="/" />
        <h2 style={{ marginBottom: '1rem' }}>Накладная</h2>

        {/* Блок изменения статуса */}
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', padding: '1rem', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <label style={{ fontWeight: 600 }}>Статус:</label>
          <select value={clientStatus} onChange={(e) => setClientStatus(e.target.value)}>
            {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <button className="btn btn-primary" onClick={handleSaveStatus} disabled={savingStatus}>
            {savingStatus ? '...' : 'Сохранить статус'}
          </button>
        </div>

        {/* Остальные поля — только просмотр, кешбек и рассчитано скрыты */}
        <ShipmentForm
          form={form}
          setForm={setForm}
          shippingOptions={SHIPPING_OPTIONS}
          statusOptions={STATUS_OPTIONS}
          readOnly={true}
          hideFields={['cashback', 'calculated', 'status', 'client']}
        />

        {/* Файлы — только просмотр */}
        <div className="form-group">
          <label>Файлы</label>
          <div className="file-links">
            {[1, 2, 3].filter((i) => shipment[`file${i}`]).map((i) => (
              <button key={i} className="btn" onClick={() => handleDownloadFile(i)} style={{ padding: '0.2rem 0.6rem', fontSize: '0.85rem' }}>
                Файл {i}
              </button>
            ))}
            {![1, 2, 3].some((i) => shipment[`file${i}`]) && (
              <span style={{ color: 'var(--text-muted)' }}>Нет файлов</span>
            )}
          </div>
        </div>
      </>
    );
  }

  // ========== АДМИНСКИЙ РЕЖИМ ==========
  return (
    <>
      <NavBar showBack backTo="/" />
      <h2 style={{ marginBottom: '1rem' }}>Накладная</h2>
      <div className="actions" style={{ marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <button
          className={`btn ${shipment.dispatch_notified ? 'btn-notified' : 'btn-primary'}`}
          onClick={handleNotifyDispatch}
          title={shipment.dispatch_notified ? 'Уже отправлено' : ''}
        >
          {shipment.dispatch_notified ? '✓ Уведомление об отправке' : 'Уведомление об отправке'}
        </button>
        <button
          className={`btn ${shipment.delivery_notified ? 'btn-notified' : 'btn-success'}`}
          onClick={handleNotifyDelivery}
          title={shipment.delivery_notified ? 'Уже отправлено' : ''}
        >
          {shipment.delivery_notified ? '✓ Уведомление о прибытии' : 'Уведомление о прибытии'}
        </button>
      </div>
      <ShipmentForm
        form={form}
        setForm={setForm}
        shippingOptions={SHIPPING_OPTIONS}
        statusOptions={STATUS_OPTIONS}
      />
      <div className="form-group">
        <label>Файлы</label>
        <div className="file-links">
          {[1, 2, 3].filter((i) => shipment[`file${i}`]).map((i) => (
            <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
              <button className="btn" onClick={() => handleDownloadFile(i)} style={{ padding: '0.2rem 0.6rem', fontSize: '0.85rem' }}>
                Файл {i}
              </button>
              <button
                onClick={() => handleDeleteFile(i)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--danger)', fontWeight: 'bold', fontSize: '1.1rem', lineHeight: 1, padding: '0 2px' }}
                title="Удалить файл"
              >×</button>
            </span>
          ))}
          {![1, 2, 3].some((i) => shipment[`file${i}`]) && (
            <span style={{ color: 'var(--text-muted)' }}>Нет файлов</span>
          )}
        </div>
        <input type="file" multiple onChange={handleFileUpload} style={{ marginTop: '0.5rem' }} />
      </div>
      {/* Получатели уведомлений */}
      <div style={{ marginTop: '1.5rem', marginBottom: '1rem', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', padding: '1rem' }}>
        <h3 style={{ marginBottom: '0.75rem', fontSize: '1rem' }}>Получатели уведомлений</h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
          Уведомления об отправке и прибытии будут отправлены всем указанным получателям.
        </p>

        {/* Список текущих получателей */}
        {recipients.length > 0 && (
          <div style={{ marginBottom: '0.75rem', display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
            {recipients.map((r) => (
              <span key={r.id} style={{
                display: 'inline-flex', alignItems: 'center', gap: '0.35rem',
                background: 'var(--bg)', border: '1px solid var(--border)',
                borderRadius: '20px', padding: '3px 10px', fontSize: '0.85rem'
              }}>
                <span>{r.label || r.chat_id}</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>({r.chat_id})</span>
                <button
                  onClick={() => handleRemoveRecipient(r.id)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--danger)', padding: '0 2px', fontWeight: 'bold', lineHeight: 1 }}
                  title="Удалить"
                >×</button>
              </span>
            ))}
          </div>
        )}
        {recipients.length === 0 && (
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>Получатели не добавлены</p>
        )}

        {/* Форма добавления */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'flex-end' }}>
          <select value={recipientType} onChange={(e) => setRecipientType(e.target.value)} style={{ minWidth: '130px' }}>
            <option value="group">Группа</option>
            <option value="client">Клиент</option>
            <option value="manual">Chat ID вручную</option>
          </select>

          {recipientType === 'group' && (
            <select value={recipientGroupId} onChange={(e) => setRecipientGroupId(e.target.value)} style={{ minWidth: '200px' }}>
              <option value="">— выберите группу —</option>
              {groups.map((g) => (
                <option key={g.chat_id} value={g.chat_id}>{g.title} ({g.member_count} уч.)</option>
              ))}
            </select>
          )}

          {recipientType === 'client' && (
            <select value={recipientClientId} onChange={(e) => setRecipientClientId(e.target.value)} style={{ minWidth: '200px' }}>
              <option value="">— выберите клиента —</option>
              {clients.filter((c) => c.telegram_chat_id).map((c) => (
                <option key={c.id} value={c.id}>{c.full_name || c.phone || c.id}</option>
              ))}
            </select>
          )}

          {recipientType === 'manual' && (
            <input
              type="text"
              placeholder="Chat ID (число)"
              value={recipientManualId}
              onChange={(e) => setRecipientManualId(e.target.value)}
              style={{ width: '160px' }}
            />
          )}

          <input
            type="text"
            placeholder="Подпись (необязательно)"
            value={recipientLabel}
            onChange={(e) => setRecipientLabel(e.target.value)}
            style={{ width: '180px' }}
          />

          <button
            className="btn btn-primary"
            onClick={handleAddRecipient}
            disabled={addingRecipient}
            style={{ whiteSpace: 'nowrap' }}
          >
            {addingRecipient ? '...' : '+ Добавить'}
          </button>
        </div>
      </div>

      <div className="actions">
        <button className="btn btn-primary" onClick={handleSave} disabled={saving}>{saving ? '...' : 'Сохранить'}</button>
        <button className="btn btn-danger" onClick={handleDelete}>Удалить</button>
      </div>
    </>
  );
}
