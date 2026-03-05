import { Link } from 'react-router-dom';

export default function NavBar({ showBack, backTo }) {
  return (
    <nav className="nav">
      {showBack && (
        <Link to={backTo || '/'} className="btn">← Назад</Link>
      )}
      <Link to="/" className="btn">Главная</Link>
      <Link to="/closed" className="btn">Закрытые накладные</Link>
      <Link to="/cashback" className="btn">Расчёт по кэшбеку</Link>
      <Link to="/clients" className="btn">Клиенты</Link>
      <Link to="/shipments/new" className="btn btn-primary">Создать накладную</Link>
    </nav>
  );
}
