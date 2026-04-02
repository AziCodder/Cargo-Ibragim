import { useState, useEffect, useRef, useCallback } from 'react';
import { adminApi } from '../api';
import NavBar from '../components/NavBar';

const LEVELS = {
  ERROR:   { color: '#f87171', bg: 'rgba(239,68,68,0.12)' },
  WARNING: { color: '#fbbf24', bg: 'rgba(251,191,36,0.10)' },
  WARN:    { color: '#fbbf24', bg: 'rgba(251,191,36,0.10)' },
  INFO:    { color: '#60a5fa', bg: '' },
  DEBUG:   { color: '#6b7280', bg: '' },
};

function colorLine(line) {
  for (const [lvl, style] of Object.entries(LEVELS)) {
    if (line.includes(`| ${lvl}`) || line.includes(`[${lvl}]`)) {
      return style;
    }
  }
  return { color: 'var(--text)', bg: '' };
}

const LINE_OPTIONS = [100, 200, 500, 1000];

export default function LogsPage() {
  const [tab, setTab] = useState('site'); // 'site' | 'bot'
  const [logs, setLogs] = useState({ site: '', bot: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [lines, setLines] = useState(200);
  const [filter, setFilter] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const bottomRef = useRef(null);
  const intervalRef = useRef(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError('');
    try {
      const fn = tab === 'site' ? adminApi.getSiteLogs : adminApi.getBotLogs;
      const r = await fn(lines);
      const text = typeof r.data === 'string' ? r.data : '';
      setLogs((prev) => ({ ...prev, [tab]: text }));
      setLastUpdate(new Date());
    } catch (e) {
      setError(e.response?.data?.detail || 'Ошибка загрузки логов');
    } finally {
      if (!silent) setLoading(false);
    }
  }, [tab, lines]);

  // Загрузка при смене вкладки или кол-ва строк
  useEffect(() => { load(); }, [load]);

  // Авто-скролл вниз при обновлении
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs, tab]);

  // Авто-обновление
  useEffect(() => {
    clearInterval(intervalRef.current);
    if (autoRefresh) {
      intervalRef.current = setInterval(() => load(true), 5000);
    }
    return () => clearInterval(intervalRef.current);
  }, [autoRefresh, load]);

  const currentLog = logs[tab] || '';
  const filtered = filter.trim()
    ? currentLog.split('\n').filter((l) => l.toLowerCase().includes(filter.toLowerCase().trim()))
    : currentLog.split('\n');

  return (
    <>
      <NavBar />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <h2 style={{ margin: 0 }}>Логи</h2>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          {lastUpdate && (
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              {lastUpdate.toLocaleTimeString('ru-RU')}
            </span>
          )}
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.85rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
            Авто (5с)
          </label>
          <select value={lines} onChange={(e) => setLines(Number(e.target.value))} style={{ fontSize: '0.85rem' }}>
            {LINE_OPTIONS.map((n) => <option key={n} value={n}>Последние {n} строк</option>)}
          </select>
          <button className="btn" onClick={() => load()} disabled={loading} style={{ minWidth: '80px' }}>
            {loading ? '...' : 'Обновить'}
          </button>
        </div>
      </div>

      {/* Вкладки */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
        {[
          { key: 'site', label: 'Бэкенд (site.log)' },
          { key: 'bot',  label: 'Бот (bot.log)' },
        ].map(({ key, label }) => (
          <button
            key={key}
            className="btn"
            onClick={() => setTab(key)}
            style={{
              background: tab === key ? 'var(--primary, #3b82f6)' : undefined,
              color: tab === key ? '#fff' : undefined,
              fontWeight: tab === key ? 'bold' : undefined,
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Фильтр */}
      <div style={{ marginBottom: '0.75rem' }}>
        <input
          type="text"
          placeholder="Фильтр строк (ERROR, INFO, текст...)"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{ width: '100%', maxWidth: '400px' }}
        />
      </div>

      {error && (
        <p style={{ color: 'var(--danger)', marginBottom: '0.5rem' }}>⚠️ {error}</p>
      )}

      {/* Лог */}
      <div style={{
        background: '#0d1117',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '0.75rem 1rem',
        fontFamily: 'monospace',
        fontSize: '0.78rem',
        lineHeight: '1.6',
        height: 'calc(100vh - 260px)',
        overflowY: 'auto',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-all',
      }}>
        {filtered.length === 0 || (filtered.length === 1 && !filtered[0]) ? (
          <span style={{ color: '#6b7280' }}>
            {loading ? 'Загрузка...' : 'Нет записей'}
          </span>
        ) : (
          filtered.map((line, i) => {
            const { color, bg } = colorLine(line);
            return (
              <div key={i} style={{ color, background: bg || 'transparent', padding: bg ? '0 4px' : 0, borderRadius: bg ? '3px' : 0 }}>
                {line || '\u00A0'}
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>

      <div style={{ marginTop: '0.4rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        Показано строк: {filtered.length}
        {filter && ` (отфильтровано из ${currentLog.split('\n').length})`}
      </div>
    </>
  );
}
