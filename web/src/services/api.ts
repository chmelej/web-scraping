import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getDashboardInfo = async () => {
  const { data } = await apiClient.get('/dashboard');
  return data;
};

export const getUrlInfo = async (url: string) => {
  const { data } = await apiClient.get('/queue/info', { params: { url } });
  return data;
};

export const enqueueUrl = async (url: string, priority: number = 10) => {
  const { data } = await apiClient.post('/queue', { url, priority });
  return data;
};

export const bulkEnqueueUrls = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await apiClient.post('/queue/bulk', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return data;
};
