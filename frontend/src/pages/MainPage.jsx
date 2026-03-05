import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { shipmentsApi, backupApi } from '../api';
import NavBar from '../components/NavBar';
import ShipmentTable from '../components/ShipmentTable';

function matchSearch(s, query) {
  if (!query || !String(query).trim()) return true;
  const q = String(query).trim().toLowerCase();
  const fields = [s.tracking, s.title, s.product_list, s.notes, s.delivery_date, s.dispatch_date, s.client_phone, s.client_name].filter(Boolean).map(String);
  return fields.some((f) => f.toLowerCase().includes(q) || f.toLowerCase() === q);
}

export default function MainPage() {
  const [shipments, setShipments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState('dispatch_date');
  const [order, setOrder] = useState('desc');
  const [trackingFilter, setTrackingFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [backupLoading, setBackupLoading] = useState(false);
  const [s3Loading, setS3Loading] = useState(false);
  const [s3Configured, setS3Configured] = useState(false);
  const [showRestore, setShowRestore] = useState(false);
  const [backups, setBackups] = useState([]);
  const [backupsS3, setBackupsS3] = useState([]);

  const load = () => {
    setLoading(true);
    shipmentsApi.list({ sort, order, status: 'in_transit' })
      .then((r) => setShipments(r.data || []))
      .finally(() => setLoading(false));
  };

  useEffect(load, [sort, order]);
  useEffect(() => {
    backupApi.s3Status().then((r) => setS3Configured(r.data?.configured)).catch(() => setS3Configured(false));
  }, []);

  const handleSort = (col) => {
    if (sort === col) setOrder((o) => (o === 'desc' ? 'asc' : 'desc'));
    else setSort(col);
  };

  const handleBackup = () => {
    setBackupLoading(true);
    backupApi.create().then(() => setBackupLoading(false)).finally(() => setBackupLoading(false));
  };

  const handleS3Backup = () => {
    setS3Loading(true);
    backupApi.createS3()
      .then((r) => alert(`Бэкап в S3 создан: ${r.data?.prefix || 'ok'}`))
      .catch((e) => alert(e.response?.data?.detail || e.message || 'Ошибка'))
      .finally(() => setS3Loading(false));
  };

  const [backupsPath, setBackupsPath] = useState('');
  const loadBackups = () => backupApi.list().then((r) => {
    const d = r.data || {};
    setBackups(Array.isArray(d) ? d : (d.backups || []));
    setBackupsPath(d.path || '');
  });
  const loadBackupsS3 = () => {
    if (!s3Configured) return;
    backupApi.listS3().then((r) => setBackupsS3(r.data?.backups || [])).catch(() => setBackupsS3([]));
  };

  const filtered = useMemo(() => {
    let list = shipments;
    if (trackingFilter && String(trackingFilter).trim()) {
      const t = String(trackingFilter).trim().toLowerCase();
      list = list.filter((s) => (s.tracking || '').toLowerCase().includes(t));
    }
    if (searchQuery && String(searchQuery).trim()) {
      list = list.filter((s) => matchSearch(s, searchQuery));
    }
    return list;
  }, [shipments, trackingFilter, searchQuery]);

  return (
    <>
      <NavBar />
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        {!s3Configured && (
          <button className="btn" onClick={handleBackup} disabled={backupLoading} title="Локальная копия (когда S3 не настроен)">
            {backupLoading ? '...' : 'Резервная копия'}
          </button>
        )}
        {s3Configured && (
          <button className="btn" onClick={handleS3Backup} disabled={s3Loading} title="Загрузить в S3 (Hostkey)">
            {s3Loading ? '...' : 'Бэкап в S3'}
          </button>
        )}
        <button className="btn" onClick={() => { setShowRestore(true); loadBackups(); loadBackupsS3(); }}>
          Восстановить
        </button>
      </div>
      <div className="filters" style={{ marginBottom: '1rem', display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'flex-end' }}>
        <label>
          <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Трекинг</span>
          <input type="text" placeholder="подстрока" value={trackingFilter} onChange={(e) => setTrackingFilter(e.target.value)} style={{ width: '10rem' }} />
        </label>
        <label>
          <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Поиск</span>
          <input type="text" placeholder="по записи" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} style={{ width: '14rem' }} />
        </label>
      </div>
      {loading ? <p>Загрузка...</p> : (
        <ShipmentTable shipments={filtered} sort={sort} order={order} onSort={handleSort} />
      )}
      {!loading && filtered.length !== shipments.length && (
        <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>Показано: {filtered.length} из {shipments.length}</p>
      )}
      {showRestore && (
        <RestoreModal
          backups={backups}
          backupsPath={backupsPath}
          backupsS3={backupsS3}
          s3Configured={s3Configured}
          onClose={() => setShowRestore(false)}
          onRestore={() => { setShowRestore(false); load(); }}
        />
      )}
    </>
  );
}

function RestoreModal({ backups, backupsPath, backupsS3, s3Configured, onClose, onRestore }) {
  const [restoring, setRestoring] = useState(null);
  const [restoringS3, setRestoringS3] = useState(null);

  const handleRestore = (filename) => {
    if (!confirm('Восстановить базу из этой копии? Текущие данные будут заменены.')) return;
    setRestoring(filename);
    backupApi.restore(filename)
      .then(() => { onRestore(); onClose(); })
      .catch((e) => alert(e.response?.data?.detail || 'Ошибка'))
      .finally(() => setRestoring(null));
  };

  const handleRestoreS3 = (prefix) => {
    if (!confirm('Восстановить базу и файлы из бэкапа в S3? Текущие данные будут заменены.')) return;
    setRestoringS3(prefix);
    backupApi.restoreFromS3(prefix)
      .then(() => { onRestore(); onClose(); })
      .catch((e) => alert(e.response?.data?.detail || 'Ошибка'))
      .finally(() => setRestoringS3(null));
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Восстановить из резервной копии</h3>

        {s3Configured && backupsS3?.length > 0 && (
          <section style={{ marginBottom: '1.5rem' }}>
            <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>Бэкапы в S3</h4>
            <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
              <ul style={{ listStyle: 'none', padding: 0 }}>
                {backupsS3.map((b) => (
                  <li key={b.key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <span>{b.prefix}</span>
                    <button
                      className="btn btn-primary"
                      disabled={restoringS3 === b.prefix}
                      onClick={() => handleRestoreS3(b.prefix)}
                    >
                      {restoringS3 === b.prefix ? '...' : 'Восстановить'}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        )}

        <section>
          <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>Локальные копии</h4>
          {backups.length === 0 ? <p>Локальных копий нет</p> : (
            <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
              <ul style={{ listStyle: 'none', padding: 0 }}>
                {backups.map((b) => (
                  <li key={b.filename} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <span>{b.label || b.filename}</span>
                    <button
                      className="btn btn-primary"
                      disabled={restoring === b.filename}
                      onClick={() => handleRestore(b.filename)}
                    >
                      {restoring === b.filename ? '...' : 'Восстановить'}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>

        <div className="modal-actions">
          <button className="btn" onClick={onClose}>Закрыть</button>
        </div>
      </div>
    </div>
  );
}
