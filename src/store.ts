import { CartItem, Product } from './types';

type CartListener = (items: CartItem[]) => void;

export class CartStore {
  private storageKey = 'cesme_market_2_cart_v1';
  private items: CartItem[] = [];
  private listeners: CartListener[] = [];

  constructor() {
    this.loadFromStorage();
  }

  private loadFromStorage(): void {
    try {
      const raw = localStorage.getItem(this.storageKey);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          this.items = parsed;
        }
      }
    } catch {
      this.items = [];
    }
  }

  private saveToStorage(): void {
    try {
      localStorage.setItem(this.storageKey, JSON.stringify(this.items));
    } catch {
      // Ignore storage quota errors
    }
    this.notify();
  }

  subscribe(listener: CartListener): void {
    this.listeners.push(listener);
    listener(this.items);
  }

  private notify(): void {
    for (const listener of this.listeners) {
      listener(this.items);
    }
  }

  getItems(): CartItem[] {
    return [...this.items];
  }

  addItem(product: Product, quantity = 1): void {
    const existing = this.items.find((i) => i.product.id === product.id);
    if (existing) {
      existing.quantity = Math.min(product.stock_quantity || 99, existing.quantity + quantity);
      existing.product = product;
    } else {
      this.items.push({
        product,
        quantity: Math.min(product.stock_quantity || 99, Math.max(1, quantity)),
      });
    }
    this.saveToStorage();
  }

  updateQuantity(productId: number, newQuantity: number): void {
    if (newQuantity <= 0) {
      this.removeItem(productId);
      return;
    }
    const existing = this.items.find((i) => i.product.id === productId);
    if (existing) {
      const maxStock = existing.product.stock_quantity || 99;
      existing.quantity = Math.min(maxStock, newQuantity);
      this.saveToStorage();
    }
  }

  removeItem(productId: number): void {
    this.items = this.items.filter((i) => i.product.id !== productId);
    this.saveToStorage();
  }

  clear(): void {
    this.items = [];
    this.saveToStorage();
  }

  getTotalCount(): number {
    return this.items.reduce((acc, item) => acc + item.quantity, 0);
  }

  getTotalAmount(): number {
    return this.items.reduce(
      (acc, item) => acc + Math.round(item.product.price * item.quantity * 100) / 100,
      0
    );
  }
}

export const cartStore = new CartStore();
