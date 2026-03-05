import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { shipmentsApi } from '../api';
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
    title: '',
    tracking: '',
    product_list: '',
    notes: '',
    dispatch_date: '',
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

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!form.dispatch_date) {
      alert('Укажите дату отправления');
      return;
    }
    setSaving(true);
    const payload = {
      ...form,
      delivery_date: form.delivery_date || null,
      client_id: form.client_id || null,
      client_phone: form.client_phone || null,
    };
    shipmentsApi.create(payload)
      .then((r) => {
        const id = r.data.id;
        if (files.length) {
          const fd = new FormData();
          files.slice(0, 3).forEach((f, i) => fd.append(`file${i + 1}`, f));
          return shipmentsApi.uploadFiles(id, fd).then(() => id);
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
        <div className="actions">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? '...' : 'Сохранить'}
          </button>
        </div>
      </form>
    </>
  );
}
