import { useNavigate } from 'react-router-dom';

const SHIPPING_LABELS = {
  '1_7_days': '1-7 дней',
  '15_20_days': '15-20 дней',
  '20_30_days': '20-30 дней',
};

const STATUS_LABELS = {
  in_transit: 'В дороге',
  delivered: 'Доставлено',
  cancelled: 'Отмена',
};

function StatusBadge({ status }) {
  const cls = status === 'in_transit' ? 'badge-in-transit' : status === 'delivered' ? 'badge-delivered' : 'badge-cancelled';
  return <span className={`badge ${cls}`}>{STATUS_LABELS[status] || status}</span>;
}

export default function ShipmentTable({ shipments, sort, order, onSort }) {
  const navigate = useNavigate();

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Заголовок</th>
            <th>Трекинг</th>
            <th>Клиент</th>
            <th onClick={() => onSort?.('dispatch_date')} style={{ cursor: onSort ? 'pointer' : undefined }}>
              Дата отправки {sort === 'dispatch_date' && (order === 'desc' ? '↓' : '↑')}
            </th>
            <th>Дата получения</th>
            <th>Вес</th>
            <th>Вид отправки</th>
            <th>Сумма к оплате</th>
            <th>Статус</th>
          </tr>
        </thead>
        <tbody>
          {shipments.map((s) => (
            <tr
              key={s.id}
              className="clickable"
              onClick={() => navigate(`/shipments/${s.id}`)}
            >
              <td>{s.title || '—'}</td>
              <td>{s.tracking || '—'}</td>
              <td>{s.client_name || s.client_phone || '—'}</td>
              <td>{s.dispatch_date || '—'}</td>
              <td>{s.delivery_date || '—'}</td>
              <td>{s.weight}</td>
              <td className="shipping-type">{SHIPPING_LABELS[s.shipping_type] || s.shipping_type}</td>
              <td>{s.amount_to_pay}</td>
              <td><StatusBadge status={s.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
