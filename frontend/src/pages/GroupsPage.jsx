import { useState, useEffect, useCallback } from 'react';
import { groupsApi } from '../api';
import NavBar from '../components/NavBar';

export default function GroupsPage() {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [manualId, setManualId] = useState('');
  const [registering, setRegistering] = useState(false);
  const [regError, setRegError] = useState('');
  const [loadError, setLoadError] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    setLoadError('');
    groupsApi.list()
      .then((r) => setGroups(r.data || []))
      .catch((e) => {
        setGroups([]);
        setLoadError(e.response?.data?.detail || e.message || 'Ошибка загрузки. Перезапустите бэкенд.');
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const handleDelete = async (chatId, title) => {
    if (!confirm(`Удалить группу «${title}» из списка?`)) return;
    await groupsApi.delete(chatId).catch((e) => alert(e.response?.data?.detail || 'Ошибка'));
    load();
  };

  const handleRegister = async () => {
    const id = manualId.trim();
    if (!id) { setRegError('Введите Chat ID группы'); return; }
    setRegistering(true);
    setRegError('');
    try {
      await groupsApi.register(id);
      setManualId('');
      load();
    } catch (e) {
      setRegError(e.response?.data?.detail || 'Ошибка. Убедитесь что бот добавлен в группу и Chat ID верный.');
    } finally {
      setRegistering(false);
    }
  };

  return (
    <>
      <NavBar />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2>Telegram-группы</h2>
        <button className="btn" onClick={load}>Обновить</button>
      </div>

      <p style={{ color: 'var(--text-muted)', marginBottom: '0.75rem', fontSize: '0.9rem' }}>
        Здесь отображаются все группы, в которых состоит бот.
        Группа регистрируется автоматически при первом сообщении в ней после запуска бота.
      </p>

      {/* Ручное добавление */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', padding: '0.85rem 1rem', marginBottom: '1.25rem' }}>
        <div style={{ fontWeight: 600, marginBottom: '0.5rem', fontSize: '0.95rem' }}>Добавить группу вручную</div>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '0.6rem' }}>
          Если группа не появилась автоматически — введите Chat ID группы (отрицательное число, например <code>-1001234567890</code>).
          Либо отправьте команду <code>/syncgroups</code> прямо в нужной группе в Telegram.
        </p>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            type="text"
            placeholder="-1001234567890"
            value={manualId}
            onChange={(e) => { setManualId(e.target.value); setRegError(''); }}
            style={{ width: '220px' }}
            onKeyDown={(e) => e.key === 'Enter' && handleRegister()}
          />
          <button className="btn btn-primary" onClick={handleRegister} disabled={registering}>
            {registering ? 'Проверяем...' : 'Добавить'}
          </button>
        </div>
        {regError && <p style={{ color: 'var(--danger)', fontSize: '0.85rem', marginTop: '0.4rem' }}>{regError}</p>}
      </div>

      {loadError && (
        <p style={{ color: 'var(--danger)', background: 'rgba(239,68,68,0.1)', padding: '0.6rem 1rem', borderRadius: '6px', marginBottom: '1rem' }}>
          ⚠️ {loadError}
        </p>
      )}

      {loading ? (
        <p>Загрузка...</p>
      ) : groups.length === 0 && !loadError ? (
        <p style={{ color: 'var(--text-muted)' }}>Бот ещё не добавлен ни в одну группу.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Название группы</th>
                <th>Chat ID</th>
                <th>Участников</th>
                <th>Добавлен</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => (
                <tr key={g.chat_id}>
                  <td><strong>{g.title || '—'}</strong></td>
                  <td>
                    <code style={{ fontSize: '0.85rem', background: 'var(--surface)', padding: '2px 6px', borderRadius: '4px' }}>
                      {g.chat_id}
                    </code>
                  </td>
                  <td>{g.member_count ?? '—'}</td>
                  <td style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    {g.added_at ? new Date(g.added_at).toLocaleString('ru-RU') : '—'}
                  </td>
                  <td>
                    <button
                      className="btn btn-danger"
                      style={{ padding: '0.25rem 0.6rem', fontSize: '0.8rem' }}
                      onClick={() => handleDelete(g.chat_id, g.title)}
                    >
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
