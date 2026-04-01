import { useState, useEffect } from 'react';
import { clientsApi, groupsApi } from '../api';
import NavBar from '../components/NavBar';

const EMPTY_FORM = { full_name: '', city: '', phone: '', group_chat_id: '' };

export default function ClientsPage() {
  const [clients, setClients] = useState([]);
  const [pendingClients, setPendingClients] = useState([]);
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  // Редактирование group_chat_id у существующего клиента
  const [editingGroupChat, setEditingGroupChat] = useState(null);
  const [groupChatValue, setGroupChatValue] = useState('');

  // Модальное окно одобрения заявки
  const [approveTarget, setApproveTarget] = useState(null); // pending client object
  const [approveForm, setApproveForm] = useState({ username: '', password: '' });
  const [approveError, setApproveError] = useState('');
  const [approveLoading, setApproveLoading] = useState(false);

  const load = () => {
    setLoading(true);
    Promise.all([clientsApi.list(), clientsApi.listPending(), groupsApi.list()])
      .then(([cRes, pRes, gRes]) => {
        setClients(cRes.data || []);
        setPendingClients(pRes.data || []);
        setGroups(gRes.data || []);
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    clientsApi.create({ ...form, telegram_chat_id: null })
      .then(() => { setShowForm(false); setForm(EMPTY_FORM); load(); });
  };

  const handleDelete = (id) => {
    if (!confirm('Удалить клиента?')) return;
    clientsApi.delete(id).then(load);
  };

  const handleRejectPending = (id) => {
    if (!confirm('Отклонить и удалить заявку?')) return;
    clientsApi.delete(id).then(load);
  };

  const handleSaveGroupChat = (clientId) => {
    clientsApi.update(clientId, { group_chat_id: groupChatValue.trim() || null })
      .then(() => { setEditingGroupChat(null); load(); })
      .catch((e) => alert(e.response?.data?.detail || 'Ошибка'));
  };

  const openApprove = (client) => {
    setApproveTarget(client);
    setApproveForm({ username: '', password: '' });
    setApproveError('');
  };

  const handleApprove = (e) => {
    e.preventDefault();
    if (!approveForm.username.trim() || !approveForm.password.trim()) {
      setApproveError('Введите логин и пароль');
      return;
    }
    setApproveLoading(true);
    setApproveError('');
    clientsApi.approve(approveTarget.id, approveForm.username.trim(), approveForm.password.trim())
      .then(() => {
        setApproveTarget(null);
        load();
      })
      .catch((e) => setApproveError(e.response?.data?.detail || 'Ошибка при одобрении'))
      .finally(() => setApproveLoading(false));
  };

  return (
    <>
      <NavBar />

      {/* ---- Заявки на регистрацию ---- */}
      {pendingClients.length > 0 && (
        <div style={{ marginBottom: '2rem', padding: '1rem', border: '2px solid #f59e0b', borderRadius: 8, background: 'rgba(245,158,11,0.07)' }}>
          <h3 style={{ marginTop: 0, color: '#f59e0b' }}>⏳ Заявки на регистрацию ({pendingClients.length})</h3>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
            Клиенты, зарегистрировавшиеся через Telegram-бот и ожидающие одобрения.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ФИО</th>
                  <th>Город</th>
                  <th>Telegram ID</th>
                  <th>Дата заявки</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {pendingClients.map((c) => (
                  <tr key={c.id}>
                    <td>{c.full_name}</td>
                    <td>{c.city}</td>
                    <td><code style={{ fontSize: '0.8rem' }}>{c.telegram_chat_id}</code></td>
                    <td style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                      {new Date(c.created_at).toLocaleString('ru-RU')}
                    </td>
                    <td style={{ display: 'flex', gap: '0.4rem' }}>
                      <button
                        className="btn btn-primary"
                        style={{ padding: '0.25rem 0.75rem', fontSize: '0.85rem' }}
                        onClick={() => openApprove(c)}
                      >
                        Одобрить
                      </button>
                      <button
                        className="btn btn-danger"
                        style={{ padding: '0.25rem 0.5rem', fontSize: '0.85rem' }}
                        onClick={() => handleRejectPending(c.id)}
                      >
                        Отклонить
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ---- Список клиентов ---- */}
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
          <div className="form-group">
            <label>Группа для уведомлений</label>
            {groups.length > 0 ? (
              <select
                value={form.group_chat_id}
                onChange={(e) => setForm((f) => ({ ...f, group_chat_id: e.target.value }))}
              >
                <option value="">— не выбрана —</option>
                {groups.map((g) => (
                  <option key={g.chat_id} value={g.chat_id}>{g.title} ({g.member_count} уч.)</option>
                ))}
              </select>
            ) : (
              <input
                value={form.group_chat_id}
                onChange={(e) => setForm((f) => ({ ...f, group_chat_id: e.target.value }))}
                placeholder="-1001234567890 (сначала добавьте бота в группу)"
              />
            )}
            <small style={{ color: 'var(--text-muted)' }}>Уведомления будут дублироваться в этот чат.</small>
          </div>
          <button type="submit" className="btn btn-primary">Сохранить</button>
        </form>
      )}

      <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1rem' }}>
        Клиенты регистрируются через бота (/start). Здесь можно добавить клиента без Telegram — укажите телефон.
      </p>

      {loading ? <p>Загрузка...</p> : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ФИО</th>
                <th>Город</th>
                <th>Telegram</th>
                <th>Группа TG</th>
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
                  <td>
                    {editingGroupChat === c.id ? (
                      <span style={{ display: 'flex', gap: '0.25rem', alignItems: 'center', flexWrap: 'wrap' }}>
                        {groups.length > 0 ? (
                          <select
                            value={groupChatValue}
                            onChange={(e) => setGroupChatValue(e.target.value)}
                            style={{ fontSize: '0.85rem', minWidth: '160px' }}
                          >
                            <option value="">— убрать —</option>
                            {groups.map((g) => (
                              <option key={g.chat_id} value={g.chat_id}>{g.title}</option>
                            ))}
                          </select>
                        ) : (
                          <input
                            value={groupChatValue}
                            onChange={(e) => setGroupChatValue(e.target.value)}
                            placeholder="-100..."
                            style={{ width: '10rem', fontSize: '0.85rem' }}
                          />
                        )}
                        <button className="btn" style={{ padding: '0.2rem 0.5rem', fontSize: '0.8rem' }} onClick={() => handleSaveGroupChat(c.id)}>✓</button>
                        <button className="btn" style={{ padding: '0.2rem 0.5rem', fontSize: '0.8rem' }} onClick={() => setEditingGroupChat(null)}>✕</button>
                      </span>
                    ) : (
                      <span
                        style={{ cursor: 'pointer', color: c.group_chat_id ? 'var(--success)' : 'var(--text-muted)', fontSize: '0.85rem' }}
                        onClick={() => { setEditingGroupChat(c.id); setGroupChatValue(c.group_chat_id || ''); }}
                        title="Нажмите чтобы изменить"
                      >
                        {c.group_chat_id ? `✓ ${c.group_chat_id}` : '+ задать'}
                      </span>
                    )}
                  </td>
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

      {/* ---- Модальное окно одобрения ---- */}
      {approveTarget && (
        <div className="modal-overlay" onClick={() => setApproveTarget(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 440 }}>
            <h3 style={{ marginTop: 0 }}>Одобрить регистрацию</h3>
            <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>
              <b>{approveTarget.full_name}</b> — {approveTarget.city}<br />
              <span style={{ fontSize: '0.85rem' }}>Telegram: <code>{approveTarget.telegram_chat_id}</code></span>
            </p>
            <p style={{ fontSize: '0.9rem', marginBottom: '1rem' }}>
              Придумайте логин и пароль для этого клиента. После подтверждения данные будут автоматически отправлены ему в Telegram.
            </p>
            <form onSubmit={handleApprove}>
              <div className="form-group">
                <label>Логин</label>
                <input
                  value={approveForm.username}
                  onChange={(e) => setApproveForm((f) => ({ ...f, username: e.target.value }))}
                  placeholder="Например: ivan_petrov"
                  required
                  autoFocus
                />
              </div>
              <div className="form-group">
                <label>Пароль</label>
                <input
                  value={approveForm.password}
                  onChange={(e) => setApproveForm((f) => ({ ...f, password: e.target.value }))}
                  placeholder="Минимум 4 символа"
                  required
                />
              </div>
              {approveError && (
                <p style={{ color: 'var(--danger)', fontSize: '0.9rem', margin: '0 0 1rem' }}>{approveError}</p>
              )}
              <div className="modal-actions">
                <button type="submit" className="btn btn-primary" disabled={approveLoading}>
                  {approveLoading ? 'Отправка...' : '✓ Одобрить и отправить данные'}
                </button>
                <button type="button" className="btn" onClick={() => setApproveTarget(null)}>
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
