import axios from 'axios';
import { API_URL } from '../config/api';

const http = axios.create({
  baseURL: API_URL,   // 统一走环境变量或 /api
  timeout: 15000,
});

export default http;
