import {
  OrderResponse,
  Product,
  StoreMedia,
  StoreLayoutResponse,
} from './types';

export class ApiClient {
  private static tokenKey = 'cm2_admin_jwt_token';

  static getToken(): string | null {
    return localStorage.getItem(this.tokenKey);
  }

  static setToken(token: string | null): void {
    if (token) {
      localStorage.setItem(this.tokenKey, token);
    } else {
      localStorage.removeItem(this.tokenKey);
    }
  }

  private static async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers || {});
    if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    const token = this.getToken();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }

    const res = await fetch(path, { ...options, headers });
    if (!res.ok) {
      let errMsg = `HTTP ${res.status}`;
      try {
        const errJson = await res.json();
        errMsg = errJson.detail || JSON.stringify(errJson);
      } catch {
        errMsg = await res.text();
      }
      throw new Error(errMsg);
    }
    return res.json() as Promise<T>;
  }

  static async getStoreLayout(): Promise<StoreLayoutResponse> {
    return this.request<StoreLayoutResponse>('/api/v1/store/layout');
  }

  static async getProducts(params?: {
    q?: string;
    category_id?: number | null;
    include_inactive?: boolean;
  }): Promise<Product[]> {
    const search = new URLSearchParams();
    if (params?.q) search.set('q', params.q);
    if (params?.category_id) search.set('category_id', String(params.category_id));
    if (params?.include_inactive) search.set('include_inactive', 'true');
    const qs = search.toString();
    return this.request<Product[]>(`/api/v1/products${qs ? `?${qs}` : ''}`);
  }

  static async getStoreMedia(): Promise<StoreMedia[]> {
    return this.request<StoreMedia[]>('/api/v1/store/media');
  }

  static async getAdminStoreMedia(): Promise<StoreMedia[]> {
    return this.request<StoreMedia[]>('/api/v1/admin/store-media');
  }

  static async uploadImage(file: File): Promise<{ image_url: string; filename: string }> {
    const form = new FormData();
    form.append('file', file);
    return this.request('/api/v1/admin/upload-image', { method: 'POST', body: form });
  }

  static async saveStoreMedia(mediaId: number | null, payload: Omit<StoreMedia, 'id' | 'updated_at'>): Promise<StoreMedia> {
    const path = mediaId ? `/api/v1/admin/store-media/${mediaId}` : '/api/v1/admin/store-media';
    return this.request<StoreMedia>(path, {
      method: mediaId ? 'PUT' : 'POST',
      body: JSON.stringify(payload),
    });
  }

  static async deleteStoreMedia(mediaId: number): Promise<void> {
    await this.request(`/api/v1/admin/store-media/${mediaId}`, { method: 'DELETE' });
  }

  static async createOrder(payload: {
    customer_name: string;
    customer_phone: string;
    customer_email?: string | null;
    order_note?: string | null;
    idempotency_key: string;
    kvkk_approved: boolean;
    items: { product_id: number; quantity: number }[];
  }): Promise<OrderResponse> {
    return this.request<OrderResponse>('/api/v1/orders', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  static async trackOrder(orderNumber: string): Promise<OrderResponse> {
    return this.request<OrderResponse>(
      `/api/v1/orders/track/${encodeURIComponent(orderNumber.trim())}`
    );
  }

  static async shareCustomerLocation(payload: {
    order_number: string;
    location_session_token: string;
    consent: true;
    latitude: number;
    longitude: number;
    accuracy_meters: number | null;
  }): Promise<{ active: boolean; updated_at: string }> {
    return this.request('/api/v1/orders/location/share', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  static async stopCustomerLocation(payload: {
    order_number: string;
    location_session_token: string;
  }): Promise<{ active: boolean }> {
    return this.request('/api/v1/orders/location/stop', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  static async getAdminLiveLocations(): Promise<Array<{
    order_number: string;
    customer_name: string;
    customer_phone: string;
    status: string;
    latitude: number;
    longitude: number;
    accuracy_meters: number | null;
    updated_at: string;
  }>> {
    return this.request('/api/v1/admin/live-locations');
  }

  static async login(username: string, password: string): Promise<{
    access_token: string;
    username: string;
    full_name: string;
    role: string;
  }> {
    return this.request('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
  }

  static async getAdminDashboard(): Promise<any> {
    return this.request('/api/v1/admin/dashboard');
  }

  static async getAdminOrders(statusFilter = 'ALL'): Promise<OrderResponse[]> {
    const qs = statusFilter && statusFilter !== 'ALL' ? `?status_filter=${statusFilter}` : '';
    return this.request<OrderResponse[]>(`/api/v1/admin/orders${qs}`);
  }

  static async updateOrderStatus(
    orderId: number,
    status: string,
    note?: string
  ): Promise<OrderResponse> {
    return this.request<OrderResponse>(`/api/v1/admin/orders/${orderId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status, note }),
    });
  }

  static async saveProduct(
    productId: number | null,
    payload: any
  ): Promise<Product> {
    if (productId) {
      return this.request<Product>(`/api/v1/admin/products/${productId}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
    }
    return this.request<Product>('/api/v1/admin/products', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  static async toggleProductActive(productId: number): Promise<Product> {
    return this.request<Product>(`/api/v1/admin/products/${productId}/toggle-active`, {
      method: 'PATCH',
    });
  }

  static async importCsv(file: File): Promise<any> {
    const fd = new FormData();
    fd.append('file', file);
    return this.request('/api/v1/admin/import/csv', {
      method: 'POST',
      body: fd,
    });
  }
}
