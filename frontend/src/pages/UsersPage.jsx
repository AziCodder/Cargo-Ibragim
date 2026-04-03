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

  // Редактирование пользователя
  const [editUser, setEditUser] = useState(null); // { id, username }
  const [editForm, setEditForm] = useState({ username: '', password: '' });
  const [editError, setEditError] = useState('');
  const [editSaving, setEditSaving] = useState(false);

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

  const openEdit = (u) => {
    setEditUser(u);
    setEditForm({ username: u.username, password: '' });
    setEditError('');
  };

  const closeEdit = () => {
    setEditUser(null);
    setEditError('');
  };

  const handleEdit = async (e) => {
    e.preventDefault();
    if (!editForm.username.trim()) {
      setEditError('Логин не может быть пустым');
      return;
    }
    if (!editForm.password && editForm.username.trim() === editUser.username) {
      setEditError('Нет изменений для сохранения');
      return;
    }
    setEditSaving(true);
    setEditError('');
    try {
      await adminApi.updateUser(editUser.id, {
        username: editForm.username.trim(),
        password: editForm.password || undefined,
      });
      closeEdit();
      load();
    } catch (err) {
      setEditError(err.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setEditSaving(false);
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
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '8px', padding: '1.25rem', marginBottom: '1.5rem' }}>
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
                  <td style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      className="btn"
                      onClick={() => openEdit(u)}
                      style={{ padding: '0.25rem 0.75rem', fontSize: '0.85rem' }}
                    >
                      Изменить
                    </button>
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

      {/* Модальное окно редактирования */}
      {editUser && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
          }}
          onClick={(e) => { if (e.target === e.currentTarget) closeEdit(); }}
        >
          <div style={{
            background: 'var(--bg-card)', border: '1px solid var(--border)',
            borderRadius: '10px', padding: '1.5rem', width: '100%', maxWidth: '400px',
          }}>
            <h3 style={{ marginBottom: '1rem', fontSize: '1rem' }}>
              Изменить пользователя <em>{editUser.username}</em>
            </h3>
            <form onSubmit={handleEdit}>
              <div className="form-group" style={{ marginBottom: '0.75rem' }}>
                <label>Новый логин</label>
                <input
                  type="text"
                  value={editForm.username}
                  onChange={(e) => setEditForm((f) => ({ ...f, username: e.target.value }))}
                  autoComplete="off"
                />
              </div>
              <div className="form-group" style={{ marginBottom: '1rem' }}>
                <label>Новый пароль <span style={{ color: 'var(--text-muted)', fontWeight: 'normal' }}>(оставьте пустым, чтобы не менять)</span></label>
                <input
                  type="password"
                  value={editForm.password}
                  onChange={(e) => setEditForm((f) => ({ ...f, password: e.target.value }))}
                  placeholder="новый пароль"
                  autoComplete="new-password"
                />
              </div>
              {editError && <p style={{ color: 'var(--danger)', marginBottom: '0.75rem', fontSize: '0.9rem' }}>{editError}</p>}
              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <button className="btn btn-primary" type="submit" disabled={editSaving}>
                  {editSaving ? 'Сохранение...' : 'Сохранить'}
                </button>
                <button className="btn" type="button" onClick={closeEdit} disabled={editSaving}>
                  Отмена
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
