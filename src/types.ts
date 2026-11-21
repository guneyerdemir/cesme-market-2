export interface Category {
  id: number;
  name: string;
  slug: string;
  icon: string;
  sort_order: number;
  is_active: boolean;
}

export interface Product {
  id: number;
  barcode: string;
  name: string;
  slug: string;
  category_id: number;
  category_name?: string;
  description: string | null;
  image_url: string | null;
  price: number;
  unit: string;
  stock_quantity: number;
  is_stock_verified: boolean;
  is_sample_data: boolean;
  is_active: boolean;
  is_featured: boolean;
  campaign_badge: string | null;
  primary_color: string;
  secondary_color: string;
  last_synced_at: string;
}

export interface StoreMedia {
  id: number;
  placement: 'gallery' | 'sponsor';
  title: string;
  image_url: string;
  link_url: string | null;
  sort_order: number;
  is_active: boolean;
  updated_at: string;
}

export interface CartItem {
  product: Product;
  quantity: number;
}

export interface OrderItem {
  id: number;
  product_id: number;
  barcode_snapshot: string;
  product_name_snapshot: string;
  unit_price_snapshot: number;
  unit_snapshot: string;
  quantity: number;
  line_total: number;
}

export interface OrderStatusLog {
  id: number;
  previous_status: string | null;
  new_status: string;
  changed_by_username: string;
  note: string | null;
  created_at: string;
}

export interface OrderResponse {
  id: number;
  order_number: string;
  customer_name: string;
  customer_phone: string;
  customer_email: string | null;
  order_note: string | null;
  delivery_type: string;
  payment_method: string;
  status: string;
  status_label?: string;
  subtotal_amount: number;
  total_amount: number;
  created_at: string;
  updated_at: string;
  items: OrderItem[];
  status_logs: OrderStatusLog[];
  location_session_token?: string;
}

export interface StoreLayoutResponse {
  store_name: string;
  delivery_model: string;
  contact: {
    address: string;
    phone: string;
    whatsapp: string;
    maps_url: string;
  };
  categories: Category[];
  integration: {
    pos_connected: boolean;
    pos_software_name: string;
    last_synced_at: string | null;
    last_sync_source: string;
    total_products: number;
    verified_products: number;
    sample_products: number;
    supported_methods: string[];
    stock_disclaimer: string;
  };
}
