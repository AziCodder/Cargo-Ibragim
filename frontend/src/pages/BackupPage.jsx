import { useState, useEffect } from 'react';
import { backupApi } from '../api';
import NavBar from '../components/NavBar';

export default function BackupPage() {
  const [s3, setS3] = useState(null); // null | true | false
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const loadBackups = async () => {
    setLoading(true);
    setError('');
    try {
      const statusRes = await backupApi.s3Status();
      const isS3 = statusRes.data.configured;
      setS3(isS3);
      if (isS3) {
        const res = await backupApi.listS3();
        setBackups(res.data.backups || []);
      } else {
        const res = await backupApi.list();
        setBackups(res.data.backups || []);
      }
    } catch (e) {
      setError(e.response?.data?.detail || 'Ошибка загрузки списка бэкапов');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadBackups(); }, []);

  const handleCreate = async () => {
    setBusy(true);
    setMessage('');
    setError('');
    try {
      await backupApi.create();
      setMessage('Резервная копия создана');
      await loadBackups();
    } catch (e) {
      setError(e.response?.data?.detail || 'Ошибка создания бэкапа');
    } finally {
      setBusy(false);
    }
  };

  const handleRestore = async (item) => {
    const label = s3 ? item.prefix : item.filename;
    if (!confirm(`Восстановить из «${label}»?\nТекущая база будет перезаписана.`)) return;
    setBusy(true);
    setMessage('');
    setError('');
    try {
      if (s3) {
        await backupApi.restoreFromS3(item.prefix);
      } else {
        await backupApi.restore(item.filename);
      }
      setMessage('База данных восстановлена. Рекомендуется перезапустить сервер.');
    } catch (e) {
      setError(e.response?.data?.detail || 'Ошибка восстановления');
    } finally {
      setBusy(false);
    }
  };

  const fmtSize = (bytes) => {
    if (!bytes) return '—';
    if (bytes < 1024) return `${bytes} Б`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
    return `${(bytes / 1024 / 1024).toFixed(2)} МБ`;
  };

  return (
    <>
      <NavBar />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <h2 style={{ margin: 0 }}>Резервные копии</h2>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-primary" onClick={handleCreate} disabled={busy}>
            {busy ? '...' : 'Создать резервную копию'}
          </button>
          <button className="btn" onClick={loadBackups} disabled={loading || busy}>
            Обновить
          </button>
        </div>
      </div>

      {s3 !== null && (
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
          Хранилище: <strong>{s3 ? 'S3' : 'Локально'}</strong>
        </p>
      )}

      {message && (
        <p style={{ color: 'var(--success, #22c55e)', marginBottom: '0.75rem', fontWeight: 500 }}>{message}</p>
      )}
      {error && (
        <p style={{ color: 'var(--danger)', marginBottom: '0.75rem' }}>{error}</p>
      )}

      {loading ? (
        <p>Загрузка...</p>
      ) : backups.length === 0 ? (
        <p style={{ color: 'var(--text-muted)' }}>Резервных копий нет</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{s3 ? 'Дата / Папка' : 'Файл'}</th>
                {!s3 && <th>Размер</th>}
                <th></th>
              </tr>
            </thead>
            <tbody>
              {backups.map((item, i) => (
                <tr key={i}>
                  <td>{s3 ? item.prefix : item.filename}</td>
                  {!s3 && <td>{fmtSize(item.size)}</td>}
                  <td>
                    <button
                      className="btn btn-danger"
                      onClick={() => handleRestore(item)}
                      disabled={busy}
                      style={{ padding: '0.25rem 0.75rem', fontSize: '0.85rem' }}
                    >
                      Восстановить
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
