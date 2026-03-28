/**
 * apiClient.ts — Browser-side Axios client
 *
 * baseURL is intentionally EMPTY ("") so every request goes to the
 * same-origin Next.js server (/api/projects, /api/metadata, etc.).
 *
 * All requests to /api/* include x-api-key from NEXT_PUBLIC_BACKEND_API_KEY.
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import { getApiHeaders } from './apiBase';

// baseURL must be empty so all requests go to same origin (Next.js)
const apiClient: AxiosInstance = axios.create({
    baseURL: '',   // <-- same-origin: browser -> Next.js /api/* routes
    headers: {
        'Content-Type': 'application/json',
        ...getApiHeaders(),
    },
    timeout: 120_000,  // 120s timeout for slow backend operations
});

// Response interceptor — turn network/connection errors into readable messages
apiClient.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
        const isNetworkError =
            error.message === 'Network Error' ||
            error.code === 'ECONNREFUSED' ||
            error.code === 'ENOTFOUND' ||
            error.code === 'ECONNABORTED';

        if (isNetworkError) {
            // Silently handle network errors - don't spam console
            return Promise.reject({
                isNetworkError: true,
                message: 'Backend API is currently unreachable. Please check your connection or try again later.',
                originalError: error,
            });
        }

        const errorData = error.response?.data ?? {};
        const status = error.response?.status;
        const statusText = error.response?.statusText;
        
        let errorMsg =
            (errorData as Record<string, string>).error ??
            (errorData as Record<string, string>).details;
        
        if (!errorMsg) {
            if (status && statusText) {
                errorMsg = `HTTP ${status} ${statusText}`;
            } else if (status) {
                errorMsg = `HTTP Error ${status}`;
            } else if (error.message) {
                errorMsg = error.message;
            } else {
                errorMsg = 'An unexpected error occurred';
            }
        }

        return Promise.reject({
            isNetworkError: false,
            message: errorMsg,
            status: status,
            originalError: error,
            data: errorData,
        });
    }
);

export default apiClient;
