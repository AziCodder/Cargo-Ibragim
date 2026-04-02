import { useState, useEffect } from 'react';
import NavBar from '../components/NavBar';
import { adminApi, clientsApi } from '../api';

const ROLE_LABELS = { admin: 'Администратор', client: 'Клиент' };

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ username: '', password: '', role: 'client', client_id: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = () => {
    setLoading(true);
    Promise.all([adminApi.listUsers(), clientsApi.list()])
      .then(([usersRes, clientsRes]) => {
        setUsers(usersRes.data || []);
        setClients(clientsRes.data || []);
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.username.trim() || !form.password) {
      setError('Введите логин и пароль');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await adminApi.createUser({
        username: form.username.trim(),
        password: form.password,
        role: form.role,
        client_id: form.role === 'client' && form.client_id ? form.client_id : null,
      });
      setForm({ username: '', password: '', role: 'client', client_id: '' });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка создания пользователя');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (userId, username) => {
    if (!confirm(`Удалить пользователя «${username}»?`)) return;
    try {
      await adminApi.deleteUser(userId);
      load();
    } catch (err) {
      alert(err.response?.data?.detail || 'Ошибка удаления');
    }
  };

  const getClientName = (client_id) => {
    if (!client_id) return '—';
    const c = clients.find((cl) => cl.id === client_id);
    return c ? c.full_name || c.id : client_id;
  };

  return (
    <>
      <NavBar />
      <h2 style={{ marginBottom: '1rem' }}>Пользователи</h2>

      {/* Форма создания */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', padding: '1.25rem', marginBottom: '1.5rem' }}>
        <h3 style={{ marginBottom: '1rem', fontSize: '1rem' }}>Создать пользователя</h3>
        <form onSubmit={handleCreate}>
          <div className="form-row">
            <div className="form-group">
              <label>Логин</label>
              <input
                type="text"
                value={form.username}
                onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
                placeholder="username"
                autoComplete="off"
              />
            </div>
            <div className="form-group">
              <label>Пароль</label>
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                placeholder="пароль"
                autoComplete="new-password"
              />
            </div>
            <div className="form-group">
              <label>Роль</label>
              <select value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value, client_id: '' }))}>
                <option value="client">Клиент</option>
                <option value="admin">Администратор</option>
              </select>
            </div>
            {form.role === 'client' && (
              <div className="form-group">
                <label>Привязать к клиенту</label>
                <select value={form.client_id} onChange={(e) => setForm((f) => ({ ...f, client_id: e.target.value }))}>
                  <option value="">— без привязки —</option>
                  {clients.map((c) => (
                    <option key={c.id} value={c.id}>{c.full_name || c.id} {c.city ? `(${c.city})` : ''}</option>
                  ))}
                </select>
              </div>
            )}
          </div>
          {error && <p style={{ color: 'var(--danger)', marginBottom: '0.75rem', fontSize: '0.9rem' }}>{error}</p>}
          <button className="btn btn-primary" type="submit" disabled={saving}>
            {saving ? 'Создание...' : 'Создать'}
          </button>
        </form>
      </div>

      {/* Таблица пользователей */}
      {loading ? (
        <p>Загрузка...</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Логин</th>
                <th>Роль</th>
                <th>Клиент</th>
                <th>Дата создания</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td><strong>{u.username}</strong></td>
                  <td>{ROLE_LABELS[u.role] || u.role}</td>
                  <td>{getClientName(u.client_id)}</td>
                  <td>{u.created_at ? new Date(u.created_at).toLocaleDateString('ru-RU') : '—'}</td>
                  <td>
                    <button
                      className="btn btn-danger"
                      onClick={() => handleDelete(u.id, u.username)}
                      style={{ padding: '0.25rem 0.75rem', fontSize: '0.85rem' }}
                    >
                      Удалить
                    </button>
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>Нет пользователей</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
