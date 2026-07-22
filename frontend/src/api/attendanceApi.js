import apiClient from './apiClient';

export const attendanceApi = {
  list: (params = {}) => apiClient.get('/attendance', { params }),
  checkIn: () => apiClient.post('/attendance/check-in'),
  checkOut: () => apiClient.post('/attendance/check-out'),
};
