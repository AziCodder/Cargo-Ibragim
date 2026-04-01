import axios from 'axios';

const TOKEN_KEY = 'cargo_token';

const api = axios.create({ baseURL: '/api' });

// Добавляем Bearer-токен к каждому запросу
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

// При 401 — очищаем токен и редиректим на /login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem('cargo_user');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const authApi = {
  login: (username, password) => api.post('/auth/login', { username, password }),
  me: () => api.get('/auth/me'),
};

export const adminApi = {
  listUsers: () => api.get('/admin/users'),
  createUser: (data) => api.post('/admin/users', data),
  updateUser: (id, data) => api.put(`/admin/users/${id}`, data),
  deleteUser: (id) => api.delete(`/admin/users/${id}`),
  getSiteLogs: (lines = 500) => api.get('/admin/logs/site', { params: { lines }, responseType: 'text' }),
  getBotLogs: (lines = 500) => api.get('/admin/logs/bot', { params: { lines }, responseType: 'text' }),
};

export const shipmentsApi = {
  list: (params) => api.get('/shipments', { params }),
  listClosed: (params) => api.get('/shipments', { params: { ...params, status: 'closed' } }),
  listCashback: () => api.get('/shipments/cashback'),
  get: (id) => api.get(`/shipments/${id}`),
  create: (data) => api.post('/shipments', data),
  update: (id, data) => api.put(`/shipments/${id}`, data),
  uploadFiles: (id, formData) => api.post(`/shipments/${id}/files`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  delete: (id) => api.delete(`/shipments/${id}`),
  notifyDispatch: (id) => api.post(`/shipments/${id}/notify-dispatch`),
  notifyDelivery: (id) => api.post(`/shipments/${id}/notify-delivery`),
  updateCalculated: (id, calculated) => api.patch(`/shipments/${id}/calculated`, { calculated }),
};

export const backupApi = {
  create: () => api.post('/backup'),
  list: () => api.get('/backups'),
  restore: (filename) => api.post(`/backups/restore/${filename}`),
  createS3: () => api.post('/backup/s3'),
  s3Status: () => api.get('/backup/s3/status'),
  listS3: () => api.get('/backups/s3'),
  restoreFromS3: (prefix) => api.post('/backups/s3/restore', { prefix }),
};

export const clientsApi = {
  list: () => api.get('/clients'),
  listPending: () => api.get('/clients/pending'),
  get: (id) => api.get(`/clients/${id}`),
  create: (data) => api.post('/clients', data),
  update: (id, data) => api.put(`/clients/${id}`, data),
  delete: (id) => api.delete(`/clients/${id}`),
  approve: (id, username, password) => api.post(`/clients/${id}/approve`, { username, password }),
};

export const groupsApi = {
  list: () => api.get('/groups'),
  register: (chatId) => api.post('/groups/register', { chat_id: chatId, title: '', member_count: 0 }),
  delete: (chatId) => api.delete(`/groups/${chatId}`),
};

export const recipientsApi = {
  list: (shipmentId) => api.get(`/shipments/${shipmentId}/recipients`),
  add: (shipmentId, data) => api.post(`/shipments/${shipmentId}/recipients`, data),
  remove: (shipmentId, recId) => api.delete(`/shipments/${shipmentId}/recipients/${recId}`),
};
