import ClientSelect from './ClientSelect';

/**
 * @param {string[]} hideFields - поля которые не рендерим: ['cashback', 'calculated', ...]
 * @param {boolean} readOnly - все поля только для чтения
 */
export default function ShipmentForm({ form, setForm, shippingOptions, statusOptions, readOnly, hideFields = [] }) {
  const update = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const dis = readOnly;
  const hide = (field) => hideFields.includes(field);

  return (
    <div>
      {!hide('client') && (
        <ClientSelect
          clientId={form.client_id}
          onClientIdChange={(v) => update('client_id', v)}
          clientPhone={form.client_phone}
          onClientPhoneChange={(v) => update('client_phone', v)}
          disabled={dis}
        />
      )}
      <div className="form-row">
        <div className="form-group">
          <label>Заголовок</label>
          <input value={form.title} onChange={(e) => update('title', e.target.value)} readOnly={dis} disabled={dis} />
        </div>
        <div className="form-group">
          <label>Трекинг</label>
          <input value={form.tracking} onChange={(e) => update('tracking', e.target.value)} readOnly={dis} disabled={dis} />
        </div>
      </div>
      <div className="form-group">
        <label>Список товара</label>
        <textarea value={form.product_list} onChange={(e) => update('product_list', e.target.value)} readOnly={dis} disabled={dis} />
      </div>
      <div className="form-group">
        <label>Примечание</label>
        <textarea value={form.notes} onChange={(e) => update('notes', e.target.value)} readOnly={dis} disabled={dis} />
      </div>
      <div className="form-row">
        <div className="form-group">
          <label>Дата отправления</label>
          <input type="date" value={form.dispatch_date} onChange={(e) => update('dispatch_date', e.target.value)} readOnly={dis} disabled={dis} />
        </div>
        <div className="form-group">
          <label>Дата получения</label>
          <input type="date" value={form.delivery_date} onChange={(e) => update('delivery_date', e.target.value)} readOnly={dis} disabled={dis} />
        </div>
        {!hide('status') && (
          <div className="form-group">
            <label>Статус</label>
            <select value={form.status} onChange={(e) => update('status', e.target.value)} disabled={dis}>
              {statusOptions?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
        )}
        <div className="form-group">
          <label>Вид отправки</label>
          <select value={form.shipping_type} onChange={(e) => update('shipping_type', e.target.value)} disabled={dis}>
            {shippingOptions?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>
      <div className="form-row">
        <div className="form-group">
          <label>Вес (кг)</label>
          <input type="number" step="0.1" value={form.weight} onChange={(e) => update('weight', parseFloat(e.target.value) || 0)} readOnly={dis} disabled={dis} />
        </div>
        <div className="form-group">
          <label>Сумма к оплате</label>
          <input type="number" step="1" value={form.amount_to_pay} onChange={(e) => update('amount_to_pay', parseFloat(e.target.value) || 0)} readOnly={dis} disabled={dis} />
        </div>
        {!hide('cashback') && (
          <div className="form-group">
            <label>Кэшбек</label>
            <input type="number" step="0.1" value={form.cashback} onChange={(e) => update('cashback', parseFloat(e.target.value) || 0)} readOnly={dis} disabled={dis} />
          </div>
        )}
        {!hide('calculated') && (
          <div className="form-group">
            <label className="form-label-spacer">&nbsp;</label>
            <div className="form-calculated-row">
              <span>Рассчитано</span>
              <label className="toggle-wrap">
                <input type="checkbox" className="toggle" checked={form.calculated} onChange={(e) => update('calculated', e.target.checked)} disabled={dis} />
                <span className="toggle-slider" />
              </label>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
