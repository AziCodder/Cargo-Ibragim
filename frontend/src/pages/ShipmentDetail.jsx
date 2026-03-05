import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { shipmentsApi } from '../api';
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
  const [shipment, setShipment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({});

  useEffect(() => {
    shipmentsApi.get(id)
      .then((r) => {
        setShipment(r.data);
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
      .finally(() => setLoading(false));
  }, [id]);

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
    if (form.status !== 'delivered' || !form.delivery_date) {
      alert('Пожалуйста, исправьте накладную: статус должен быть «доставлено» и указана дата прибытия.');
      return;
    }
    shipmentsApi.notifyDelivery(id).then(() => {
      setShipment((s) => ({ ...s, delivery_notified: true }));
      alert('Уведомление отправлено');
    }).catch((e) => alert(e.response?.data?.detail || 'Ошибка'));
  };

  const handleFileUpload = (e) => {
    const files = e.target.files;
    if (!files?.length) return;
    const fd = new FormData();
    for (let i = 0; i < Math.min(3, files.length); i++) fd.append(`file${i + 1}`, files[i]);
    shipmentsApi.uploadFiles(id, fd).then((r) => setShipment(r.data));
  };

  if (loading) return <><NavBar showBack backTo="/" /><p>Загрузка...</p></>;
  if (!shipment) return <><NavBar showBack backTo="/" /><p>Накладная не найдена</p></>;

  return (
    <>
      <NavBar showBack backTo="/" />
      <h2 style={{ marginBottom: '1rem' }}>Накладная</h2>
      <div className="actions" style={{ marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <button
          className={`btn ${shipment.dispatch_notified ? 'btn-notified' : ''}`}
          onClick={handleNotifyDispatch}
          title={shipment.dispatch_notified ? 'Уже отправлено' : ''}
        >
          {shipment.dispatch_notified ? '✓ Уведомление об отправке' : 'Уведомление об отправке'}
        </button>
        <button
          className={`btn ${shipment.delivery_notified ? 'btn-notified' : ''}`}
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
            <a key={i} href={`/api/shipments/${id}/file/${i}`} target="_blank" rel="noreferrer">Файл {i}</a>
          ))}
        </div>
        <input type="file" multiple onChange={handleFileUpload} style={{ marginTop: '0.5rem' }} />
      </div>
      <div className="actions">
        <button className="btn btn-primary" onClick={handleSave} disabled={saving}>{saving ? '...' : 'Сохранить'}</button>
        <button className="btn btn-danger" onClick={handleDelete}>Удалить</button>
      </div>
    </>
  );
}
