import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

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
  get: (id) => api.get(`/clients/${id}`),
  create: (data) => api.post('/clients', data),
  update: (id, data) => api.put(`/clients/${id}`, data),
  delete: (id) => api.delete(`/clients/${id}`),
};
