import { useState, useEffect } from 'react';
import { clientsApi } from '../api';
import NavBar from '../components/NavBar';

export default function ClientsPage() {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ full_name: '', city: '', phone: '' });

  const load = () => {
    setLoading(true);
    clientsApi.list()
      .then((r) => setClients(r.data || []))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    clientsApi.create({ ...form, telegram_chat_id: null })
      .then(() => { setShowForm(false); setForm({ full_name: '', city: '', phone: '' }); load(); });
  };

  const handleDelete = (id) => {
    if (!confirm('Удалить клиента?')) return;
    clientsApi.delete(id).then(load);
  };

  return (
    <>
      <NavBar />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2>Клиенты</h2>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Отмена' : 'Добавить вручную (без TG)'}
        </button>
      </div>
      {showForm && (
        <form onSubmit={handleSubmit} style={{ marginBottom: '1.5rem', padding: '1rem', border: '1px solid var(--border)', borderRadius: 8 }}>
          <h3 style={{ marginTop: 0 }}>Новый клиент (без Telegram)</h3>
          <div className="form-group">
            <label>ФИО</label>
            <input value={form.full_name} onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))} required />
          </div>
          <div className="form-group">
            <label>Город</label>
            <input value={form.city} onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))} />
          </div>
          <div className="form-group">
            <label>Телефон</label>
            <input type="tel" value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} placeholder="Для клиентов без Telegram" />
          </div>
          <button type="submit" className="btn btn-primary">Сохранить</button>
        </form>
      )}
      <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1rem' }}>
        Клиенты с Telegram регистрируются через бота (/start). Здесь можно добавить клиента без Telegram — укажите телефон.
      </p>
      {loading ? <p>Загрузка...</p> : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ФИО</th>
                <th>Город</th>
                <th>Telegram</th>
                <th>Телефон</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {clients.map((c) => (
                <tr key={c.id}>
                  <td>{c.full_name}</td>
                  <td>{c.city}</td>
                  <td>{c.telegram_chat_id ? '✓' : '—'}</td>
                  <td>{c.phone || '—'}</td>
                  <td>
                    <button className="btn btn-danger" style={{ padding: '0.25rem 0.5rem', fontSize: '0.85rem' }} onClick={() => handleDelete(c.id)}>
                      Удалить
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
