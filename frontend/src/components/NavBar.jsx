import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function NavBar({ showBack, backTo }) {
  const { isAdmin, user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <nav className="nav">
      {showBack && (
        <Link to={backTo || '/'} className="btn">← Назад</Link>
      )}
      <Link to="/" className="btn">Главная</Link>
      <Link to="/closed" className="btn">Закрытые накладные</Link>
      {isAdmin && (
        <>
          <Link to="/cashback" className="btn">Расчёт по кэшбеку</Link>
          <Link to="/clients" className="btn">Клиенты</Link>
          <Link to="/users" className="btn">Пользователи</Link>
          <Link to="/groups" className="btn">Группы</Link>
          <Link to="/shipments/new" className="btn btn-primary">Создать накладную</Link>
        </>
      )}
      <button
        className="btn"
        onClick={handleLogout}
        style={{ marginLeft: 'auto' }}
        title={`Выйти (${user?.username || ''})`}
      >
        Выйти
      </button>
    </nav>
  );
}
