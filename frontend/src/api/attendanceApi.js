import apiClient from './apiClient';

export const attendanceApi = {
  list: (params = {}) => apiClient.get('/attendance', { params }),
  summary: (params = {}) => apiClient.get('/attendance/summary', { params }),
  today: () => apiClient.get('/attendance/me/today'),
  checkIn: () => apiClient.post('/attendance/check-in'),
  checkOut: () => apiClient.post('/attendance/check-out'),
};
