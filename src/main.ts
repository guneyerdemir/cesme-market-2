import { ApiClient } from './api';
import { cartStore } from './store';
import { Category, OrderResponse, Product, StoreMedia } from './types';

class CesmeMarketApp {
  private categories: Category[] = [];
  private products: Product[] = [];
  private filteredProducts: Product[] = [];
  private storeMedia: StoreMedia[] = [];
  private galleryIndex = 0;
  private galleryTimer: number | null = null;

  private activeCategoryId: number | null = null;
  private searchQuery = '';

  private selectedProduct: Product | null = null;
  private currentAdminRole: string | null = null;
  private storeContact = { address: '', phone: '', whatsapp: '', maps_url: '' };
  private locationWatchId: number | null = null;
  private activeLocationOrderNumber: string | null = null;
  private activeLocationToken: string | null = null;
  private lastLocationSentAt = 0;
  private adminLocationPollId: number | null = null;
  private selectedMapLocationOrder: string | null = null;
  private selectedMapCoordinates: { latitude: number; longitude: number } | null = null;
  private readonly storeCoordinates = { latitude: 38.3925178, longitude: 27.0045798 };

  constructor() {
    this.setupDialogLightDismissFallbacks();
    this.bindGlobalUI();
    this.initDataAndScene();
  }

  /**
   * Implements the mandatory `closedby="any"` light-dismiss fallback for browsers
   * that do not yet natively support `HTMLDialogElement.prototype.closedBy`.
   */
  private setupDialogLightDismissFallbacks(): void {
    if (!('closedBy' in HTMLDialogElement.prototype)) {
      const outside = (e: PointerEvent, dialog: HTMLDialogElement) => {
        const r = dialog.getBoundingClientRect();
        return (
          e.clientX < r.left ||
          e.clientX > r.right ||
          e.clientY < r.top ||
          e.clientY > r.bottom
        );
      };
      for (const dialog of document.querySelectorAll<HTMLDialogElement>('dialog[closedby="any"]')) {
        let pressedOutside = false;
        dialog.addEventListener('pointerdown', (e) => {
          pressedOutside = outside(e, dialog);
        });
        dialog.addEventListener('pointerup', (e) => {
          if (pressedOutside && outside(e, dialog)) {
            dialog.close();
          }
        });
      }
    }

    // Reset dialog.returnValue on close to avoid stale values across opens
    for (const dialog of document.querySelectorAll<HTMLDialogElement>('dialog')) {
      dialog.addEventListener('close', () => {
        dialog.returnValue = '';
      });
    }
  }

  private async initDataAndScene(): Promise<void> {
    try {
      const [layout, products, media] = await Promise.all([
        ApiClient.getStoreLayout(),
        ApiClient.getProducts(),
        ApiClient.getStoreMedia(),
      ]);

      this.categories = layout.categories;
      this.products = products;
      this.storeContact = layout.contact || this.storeContact;
      this.storeMedia = media;
      this.filteredProducts = [...products];
      this.renderStoreContact();

      const disclaimerEl = document.getElementById('catalog-disclaimer-text');
      if (disclaimerEl && layout.integration?.stock_disclaimer) {
        disclaimerEl.textContent = layout.integration.stock_disclaimer;
      }

      this.render2DCatalogFilters();
      this.render2DProductGrid();
      this.renderLandingDiscovery();
      this.renderStoreMedia();
      this.startGalleryAutoplay();
    } catch (err: any) {
      this.showToast(`Ürün kataloğu yüklenemedi: ${err.message || err}`);
    }
  }

  private renderStoreContact(): void {
    const address = document.getElementById('store-contact-address');
    if (address) address.textContent = this.storeContact.address || 'Mağaza adresi yapılandırılacak.';

    const phoneLink = document.getElementById('store-contact-phone') as HTMLAnchorElement | null;
    if (phoneLink) {
      phoneLink.hidden = !this.storeContact.phone;
      phoneLink.href = this.storeContact.phone ? `tel:${this.storeContact.phone.replace(/[^\d+]/g, '')}` : '';
      phoneLink.textContent = this.storeContact.phone ? `📞 ${this.storeContact.phone}` : 'Telefon';
    }

    const directionsLink = document.getElementById('store-contact-directions') as HTMLAnchorElement | null;
    if (directionsLink) {
      directionsLink.hidden = !this.storeContact.maps_url;
      directionsLink.href = this.storeContact.maps_url || '';
    }

    const whatsappLink = document.getElementById('store-contact-whatsapp') as HTMLAnchorElement | null;
    const headerWhatsappLink = document.getElementById('header-whatsapp-link') as HTMLAnchorElement | null;
    const whatsappNumber = this.storeContact.whatsapp.replace(/\D/g, '');
    const whatsappUrl = whatsappNumber
      ? `https://wa.me/${whatsappNumber}?text=${encodeURIComponent('Merhaba, Çeşme Market 2 mağazası hakkında bilgi almak istiyorum.')}`
      : '';
    if (whatsappLink) {
      whatsappLink.hidden = !whatsappNumber;
      whatsappLink.href = whatsappUrl;
    }
    if (headerWhatsappLink) {
      headerWhatsappLink.hidden = !whatsappNumber;
      headerWhatsappLink.href = whatsappUrl;
    }
    const orderHint = document.getElementById('whatsapp-order-hint');
    const orderButton = document.getElementById('btn-whatsapp-order') as HTMLButtonElement | null;
    if (orderHint) orderHint.hidden = Boolean(whatsappNumber);
    if (orderButton) orderButton.disabled = !whatsappNumber || cartStore.getItems().length === 0;
  }

  private populateContactSettingsForm(): void {
    const addrInput = document.getElementById('setting-store-address') as HTMLInputElement | null;
    const phoneInput = document.getElementById('setting-store-phone') as HTMLInputElement | null;
    const waInput = document.getElementById('setting-store-whatsapp') as HTMLInputElement | null;
    const mapsInput = document.getElementById('setting-store-maps') as HTMLInputElement | null;
    if (addrInput) addrInput.value = this.storeContact.address || '';
    if (phoneInput) phoneInput.value = this.storeContact.phone || '';
    if (waInput) waInput.value = this.storeContact.whatsapp || '';
    if (mapsInput) mapsInput.value = this.storeContact.maps_url || '';
  }

  private openWhatsAppOrderRequest(): void {
    const phone = this.storeContact.whatsapp.replace(/\D/g, '');
    const items = cartStore.getItems();
    if (!phone || items.length === 0) return;
    const lines = items.map((item) => `• ${item.product.name} × ${item.quantity} ${item.product.unit}`);
    const message = [
      'Merhaba, aşağıdaki ürünler için mağazadan teslim sipariş talebi oluşturmak istiyorum:',
      ...lines,
      `Toplam: ${cartStore.getTotalAmount().toFixed(2)} ₺`,
      'Ödemeyi teslim alırken mağazada yapacağım. Lütfen stok ve sipariş durumunu teyit edin.',
    ].join('\n');
    window.open(`https://wa.me/${phone}?text=${encodeURIComponent(message)}`, '_blank', 'noopener,noreferrer');
  }

  private startLocationSharing(orderNumber: string, token: string): void {
    const status = document.getElementById('customer-location-share-status');
    if (!window.isSecureContext || !navigator.geolocation) {
      if (status) status.textContent = 'Canlı konum paylaşımı için güvenli (HTTPS) bağlantı ve konum izni gerekir.';
      return;
    }
    if (this.locationWatchId !== null) navigator.geolocation.clearWatch(this.locationWatchId);
    this.activeLocationOrderNumber = orderNumber;
    this.activeLocationToken = token;
    this.lastLocationSentAt = 0;
    if (status) status.textContent = 'Konum izni bekleniyor…';
    this.locationWatchId = navigator.geolocation.watchPosition(
      async (position) => {
        const now = Date.now();
        if (now - this.lastLocationSentAt < 8000) return;
        this.lastLocationSentAt = now;
        try {
          await ApiClient.shareCustomerLocation({
            order_number: orderNumber,
            location_session_token: token,
            consent: true,
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy_meters: Number.isFinite(position.coords.accuracy) ? position.coords.accuracy : null,
          });
          if (status) status.textContent = `Konum yöneticinizle paylaşılıyor • Son güncelleme ${new Date().toLocaleTimeString('tr-TR')}`;
          const start = document.getElementById('btn-start-location-share') as HTMLButtonElement | null;
          const stop = document.getElementById('btn-stop-location-share') as HTMLButtonElement | null;
          if (start) start.hidden = true;
          if (stop) stop.hidden = false;
        } catch (err: any) {
          if (status) status.textContent = `Konum gönderilemedi: ${err.message}`;
          if (/süresi dolmuş|artık kapalı|yetkisi bulunamadı/i.test(err.message)) {
            navigator.geolocation.clearWatch(this.locationWatchId!);
            this.locationWatchId = null;
            this.activeLocationOrderNumber = null;
            this.activeLocationToken = null;
            if (status) status.textContent = 'Sipariş için konum paylaşımı kapandı.';
          }
        }
      },
      (error) => {
        if (status) status.textContent = error.code === 1
          ? 'Konum izni verilmedi. Paylaşım başlatılmadı.'
          : 'Konum alınamadı. Tarayıcıda konum servisinin açık olduğunu kontrol edin.';
        if (this.locationWatchId !== null) navigator.geolocation.clearWatch(this.locationWatchId);
        this.locationWatchId = null;
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
    );
  }

  private async stopLocationSharing(): Promise<void> {
    if (this.locationWatchId !== null) navigator.geolocation.clearWatch(this.locationWatchId);
    this.locationWatchId = null;
    const orderNumber = this.activeLocationOrderNumber;
    const token = this.activeLocationToken;
    this.activeLocationOrderNumber = null;
    this.activeLocationToken = null;
    if (orderNumber && token) {
      try {
        await ApiClient.stopCustomerLocation({ order_number: orderNumber, location_session_token: token });
      } catch {
        // Browser tracking has stopped locally; server-side stale cleanup is the fallback.
      }
    }
    const status = document.getElementById('customer-location-share-status');
    const start = document.getElementById('btn-start-location-share') as HTMLButtonElement | null;
    const stop = document.getElementById('btn-stop-location-share') as HTMLButtonElement | null;
    const consent = document.getElementById('customer-location-consent') as HTMLInputElement | null;
    if (status) status.textContent = 'Konum paylaşımı durduruldu; kayıtlı son konum silindi.';
    if (start) { start.hidden = false; start.disabled = true; }
    if (stop) stop.hidden = true;
    if (consent) consent.checked = false;
  }

  private switchViewMode(mode: 'landing' | '2d'): void {
    const viewLanding = document.getElementById('view-landing')!;
    const view2d = document.getElementById('view-2d-catalog')!;

    const btnLanding = document.getElementById('btn-mode-landing')!;
    const btn2d = document.getElementById('btn-mode-2d')!;

    viewLanding.hidden = mode !== 'landing';
    view2d.hidden = mode !== '2d';

    btnLanding.classList.toggle('active', mode === 'landing');
    btnLanding.setAttribute('aria-pressed', String(mode === 'landing'));

    btn2d.classList.toggle('active', mode === '2d');
    btn2d.setAttribute('aria-pressed', String(mode === '2d'));
  }

  // -------------------------------------------------------------------------
  // 2D CATALOG & SEARCH FILTERING
  // -------------------------------------------------------------------------
  private render2DCatalogFilters(): void {
    const catList = document.getElementById('catalog-category-list')!;
    catList.innerHTML = '';

    const allCatBtn = document.createElement('button');
    allCatBtn.type = 'button';
    allCatBtn.className = `filter-list-btn ${this.activeCategoryId === null ? 'active' : ''}`;
    allCatBtn.innerHTML = `<span>🛒 Tüm Kategoriler</span> <span>${this.products.length}</span>`;
    allCatBtn.addEventListener('click', () => {
      this.activeCategoryId = null;
      this.applyProductFilters();
    });
    catList.appendChild(allCatBtn);

    for (const cat of this.categories) {
      const count = this.products.filter((p) => p.category_id === cat.id).length;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `filter-list-btn ${this.activeCategoryId === cat.id ? 'active' : ''}`;
      btn.innerHTML = `<span>${cat.icon} ${cat.name}</span> <span>${count}</span>`;
      btn.addEventListener('click', () => {
        this.activeCategoryId = cat.id;
        this.applyProductFilters();
      });
      catList.appendChild(btn);
    }

  }

  private renderLandingDiscovery(): void {
    const categoryGrid = document.getElementById('landing-category-grid');
    const featuredGrid = document.getElementById('landing-featured-grid');
    if (!categoryGrid || !featuredGrid) return;

    const categories = this.categories;

    categoryGrid.replaceChildren();
    for (const category of categories) {
      const count = this.products.filter((product) => product.category_id === category.id).length;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'landing-category-card';
      const icon = document.createElement('span');
      icon.className = 'landing-category-icon';
      icon.setAttribute('aria-hidden', 'true');
      icon.textContent = category.icon;
      const name = document.createElement('span');
      name.className = 'landing-category-name';
      name.textContent = category.name;
      const categoryCount = document.createElement('span');
      categoryCount.className = 'landing-category-count';
      categoryCount.textContent = `${count} örnek ürün`;
      button.append(icon, name, categoryCount);
      button.addEventListener('click', () => {
        this.activeCategoryId = category.id;
        this.searchQuery = '';
        (document.getElementById('global-search-input') as HTMLInputElement).value = '';
        this.applyProductFilters();
        this.switchViewMode('2d');
      });
      categoryGrid.appendChild(button);
    }

    const featured = this.products.filter((product) => product.is_featured).slice(0, 4);

    featuredGrid.replaceChildren();
    for (const product of featured) {
      const card = document.createElement('article');
      card.className = 'landing-featured-card';
      const productCard = document.createElement('div');
      productCard.className = 'product-card';
      const visual = document.createElement('button');
      visual.type = 'button';
      visual.className = 'prod-card-visual';
      visual.style.background = `linear-gradient(135deg, ${product.primary_color}, ${product.secondary_color})`;
      visual.setAttribute('aria-label', product.name);
      const visualLabel = document.createElement('span');
      visualLabel.textContent = product.name;
      visual.appendChild(visualLabel);
      if (product.image_url) {
        const image = document.createElement('img');
        image.src = product.image_url;
        image.alt = product.name;
        visual.classList.add('has-product-image');
        visual.prepend(image);
      }
      visual.addEventListener('click', () => this.openProductDetailModal(product));
      const info = document.createElement('div');
      info.className = 'prod-card-price-row';
      const name = document.createElement('strong');
      name.className = 'prod-card-title';
      name.textContent = product.name;
      const price = document.createElement('span');
      price.className = 'prod-card-price';
      price.textContent = `${product.price.toFixed(2)} ₺`;
      info.append(name, price);
      const sampleUnit = document.createElement('span');
      sampleUnit.className = 'field-hint';
      sampleUnit.textContent = `Örnek ürün • ${product.unit}`;
      const detail = document.createElement('button');
      detail.type = 'button';
      detail.className = 'btn-outline-sm landing-product-detail';
      detail.textContent = 'Ürünü incele';
      detail.addEventListener('click', () => this.openProductDetailModal(product));
      productCard.append(visual, info, sampleUnit, detail);
      card.appendChild(productCard);
      featuredGrid.appendChild(card);
    }
  }

  private renderStoreMedia(): void {
    const galleryRoot = document.getElementById('store-photo-gallery');
    const galleryPhotos = this.storeMedia.filter((item) => item.placement === 'gallery' && item.is_active);
    if (galleryRoot) {
      galleryRoot.replaceChildren();
      if (!galleryPhotos.length) {
        const empty = document.createElement('p');
        empty.className = 'gallery-empty';
        empty.textContent = 'Mağaza, çalışan ve müşterilerden fotoğraflar yakında burada.';
        galleryRoot.appendChild(empty);
      } else {
        const viewport = document.createElement('div');
        viewport.className = 'gallery-viewport';
        const track = document.createElement('div');
        track.className = 'gallery-track';
        galleryPhotos.forEach((item) => {
          const slide = document.createElement('figure');
          slide.className = 'gallery-slide';
          const image = document.createElement('img');
          image.src = item.image_url;
          image.alt = item.title || 'Çeşme Market 2 fotoğraf galerisi';
          image.loading = 'lazy';
          slide.appendChild(image);
          if (item.title) {
            const caption = document.createElement('figcaption');
            caption.textContent = item.title;
            slide.appendChild(caption);
          }
          track.appendChild(slide);
        });
        viewport.appendChild(track);
        galleryRoot.appendChild(viewport);
        this.galleryIndex = Math.min(this.galleryIndex, galleryPhotos.length - 1);
        this.setGallerySlide();
      }
    }

    const sponsorSection = document.getElementById('sponsor-section');
    const sponsorList = document.getElementById('sponsor-banner-list');
    const sponsors = this.storeMedia.filter((item) => item.placement === 'sponsor' && item.is_active);
    if (!sponsorSection || !sponsorList) return;
    sponsorSection.hidden = false;
    sponsorList.replaceChildren();
    if (!sponsors.length) {
      const empty = document.createElement('p');
      empty.className = 'sponsor-empty';
      empty.textContent = 'Sponsor banner\'ları eklendiğinde burada gösterilecek.';
      sponsorList.appendChild(empty);
    }
    for (const item of sponsors) {
      const banner = document.createElement(item.link_url ? 'a' : 'div');
      banner.className = 'sponsor-banner';
      if (banner instanceof HTMLAnchorElement && item.link_url) {
        try {
          const url = new URL(item.link_url);
          if (url.protocol === 'https:' || url.protocol === 'http:') {
            banner.href = url.href;
            banner.target = '_blank';
            banner.rel = 'noopener noreferrer';
          }
        } catch { /* Ignore invalid optional sponsor links. */ }
      }
      const image = document.createElement('img');
      image.src = item.image_url;
      image.alt = item.title || 'Sponsor tedarikçi';
      image.loading = 'lazy';
      banner.appendChild(image);
      if (item.title) {
        const title = document.createElement('span');
        title.textContent = item.title;
        banner.appendChild(title);
      }
      sponsorList.appendChild(banner);
    }
  }

  private setGallerySlide(): void {
    const track = document.querySelector<HTMLElement>('.gallery-track');
    const total = this.storeMedia.filter((item) => item.placement === 'gallery' && item.is_active).length;
    if (track && total) track.style.transform = `translateX(-${this.galleryIndex * 100}%)`;
  }

  private advanceGallery(step: number): void {
    const total = this.storeMedia.filter((item) => item.placement === 'gallery' && item.is_active).length;
    if (total < 2) return;
    this.galleryIndex = (this.galleryIndex + step + total) % total;
    this.setGallerySlide();
  }

  private startGalleryAutoplay(): void {
    if (this.galleryTimer !== null) window.clearInterval(this.galleryTimer);
    if (this.storeMedia.filter((item) => item.placement === 'gallery' && item.is_active).length < 2
      || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    this.galleryTimer = window.setInterval(() => {
      if (!document.hidden) this.advanceGallery(1);
    }, 3000);
  }

  private applyProductFilters(): void {
    const q = this.searchQuery.trim().toLowerCase();
    this.filteredProducts = this.products.filter((p) => {
      if (this.activeCategoryId !== null && p.category_id !== this.activeCategoryId) {
        return false;
      }
      if (q) {
        const hay = `${p.name} ${p.barcode} ${p.description || ''} ${p.category_name || ''}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    this.render2DCatalogFilters();
    this.render2DProductGrid();
  }

  private render2DProductGrid(): void {
    const grid = document.getElementById('catalog-product-grid')!;
    const countLabel = document.getElementById('catalog-result-count')!;
    grid.innerHTML = '';

    countLabel.textContent = `Toplam ${this.filteredProducts.length} ürün listeleniyor`;

    if (this.filteredProducts.length === 0) {
      grid.innerHTML = `
        <div class="empty-state-box" style="grid-column: 1 / -1; text-align:center; padding: 2.5rem;">
          <h3>Aramanızla Eşleşen Ürün Bulunamadı</h3>
          <p>Farklı bir anahtar kelime deneyebilir veya filtreleri temizleyebilirsiniz.</p>
        </div>
      `;
      return;
    }

    for (const prod of this.filteredProducts) {
      const card = document.createElement('article');
      card.className = 'product-card';

      const badgeHtml = prod.campaign_badge
        ? `<span class="prod-card-badge">${prod.campaign_badge}</span>`
        : prod.is_sample_data
        ? `<span class="prod-card-badge">Örnek Veri</span>`
        : '';

      card.innerHTML = `
        <div>
          <div class="prod-card-visual" data-product-visual style="background: linear-gradient(135deg, ${prod.primary_color}, ${prod.secondary_color});">
            ${badgeHtml}
            <span class="product-visual-label">${prod.name}</span>
          </div>
          <div class="prod-card-category" style="margin-top:0.55rem;">${prod.category_name || 'Kategori'}</div>
          <h3 class="prod-card-title">${prod.name}</h3>
          <div class="prod-card-price-row">
            <span class="prod-card-price">${prod.price.toFixed(2)} ₺</span>
            <span class="field-hint">/ ${prod.unit}</span>
          </div>
        </div>
        <div class="prod-card-actions">
          <button type="button" class="btn-outline-sm btn-card-detail">İncele</button>
          <button type="button" class="btn-primary-yellow btn-card-add" style="flex:1;">🛒 Sepete Ekle</button>
        </div>
      `;

      if (prod.image_url) {
        const visual = card.querySelector<HTMLElement>('[data-product-visual]')!;
        const image = document.createElement('img');
        image.src = prod.image_url;
        image.alt = prod.name;
        image.loading = 'lazy';
        visual.classList.add('has-product-image');
        visual.prepend(image);
      }

      card.querySelector('.prod-card-visual')!.addEventListener('click', () => {
        this.openProductDetailModal(prod);
      });
      card.querySelector('.prod-card-title')!.addEventListener('click', () => {
        this.openProductDetailModal(prod);
      });
      card.querySelector('.btn-card-detail')!.addEventListener('click', () => {
        this.openProductDetailModal(prod);
      });
      card.querySelector('.btn-card-add')!.addEventListener('click', () => {
        cartStore.addItem(prod, 1);
        this.showToast(`"${prod.name}" sepete eklendi.`);
      });

      grid.appendChild(card);
    }
  }

  // -------------------------------------------------------------------------
  // PRODUCT DETAIL DIALOG
  // -------------------------------------------------------------------------
  public openProductDetailModal(product: Product): void {
    this.selectedProduct = product;
    const dlg = document.getElementById('dialog-product-detail') as HTMLDialogElement;

    document.getElementById('dlg-prod-category-badge')!.textContent = product.category_name || 'Kategori';

    const visualBox = document.getElementById('dlg-prod-visual')!;
    visualBox.style.background = `linear-gradient(135deg, ${product.primary_color}, ${product.secondary_color})`;
    visualBox.replaceChildren();
    if (product.image_url) {
      const image = document.createElement('img');
      image.src = product.image_url;
      image.alt = product.name;
      visualBox.appendChild(image);
    }
    const visualInfo = document.createElement('div');
    visualInfo.className = 'product-detail-visual-info';
    const visualName = document.createElement('div');
    visualName.textContent = product.name;
    const visualBarcode = document.createElement('div');
    visualBarcode.textContent = `Barkod: ${product.barcode}`;
    visualInfo.append(visualName, visualBarcode);
    visualBox.appendChild(visualInfo);

    document.getElementById('dlg-prod-category')!.textContent = product.category_name || 'Genel';
    document.getElementById('dlg-prod-barcode')!.textContent = `Barkod: ${product.barcode}`;
    document.getElementById('dlg-prod-title')!.textContent = product.name;
    document.getElementById('dlg-prod-desc')!.textContent =
      product.description || `${product.name} (${product.unit})`;
    document.getElementById('dlg-prod-price')!.textContent = `${product.price.toFixed(2)} ₺`;
    document.getElementById('dlg-prod-unit')!.textContent = `/ ${product.unit}`;

    const stockBadge = document.getElementById('dlg-prod-stock-badge')!;
    if (product.stock_quantity > 0) {
      stockBadge.textContent = product.is_stock_verified
        ? `Doğrulanmış Stok: ${product.stock_quantity} ${product.unit}`
        : `Tahmini Stok: ${product.stock_quantity} ${product.unit}`;
      stockBadge.style.background = '#dcfce7';
      stockBadge.style.color = '#15803d';
    } else {
      stockBadge.textContent = 'Stokta Kalmadı';
      stockBadge.style.background = '#fee2e2';
      stockBadge.style.color = '#991b1b';
    }

    document.getElementById('dlg-prod-stock-note')!.textContent = product.is_sample_data
      ? '* Bu ürün ilk prototip test kataloğundandır ([ÖRNEK VERİ]). Mağaza hazırlık aşamasında güncel kasa fiyatı ve stok durumu teyit edilir.'
      : '* POS / CSV üzerinden doğrulanmış mağaza ürünü.';

    const qtyInput = document.getElementById('dlg-qty-input') as HTMLInputElement;
    qtyInput.value = '1';

    if (!dlg.open) {
      dlg.showModal();
    }
  }

  // -------------------------------------------------------------------------
  // SHOPPING CART & ORDER CREATION
  // -------------------------------------------------------------------------
  public openCartModal(): void {
    this.renderCartItems();
    const dlg = document.getElementById('dialog-cart-checkout') as HTMLDialogElement;
    if (!dlg.open) {
      dlg.showModal();
    }
  }

  private renderCartItems(): void {
    const items = cartStore.getItems();
    const badgeEl = document.getElementById('header-cart-badge')!;
    const totalChipEl = document.getElementById('header-cart-total')!;
    const count = cartStore.getTotalCount();
    const total = cartStore.getTotalAmount();

    badgeEl.textContent = String(count);
    totalChipEl.textContent = `${total.toFixed(2)} ₺`;

    const listEl = document.getElementById('cart-items-list')!;
    const emptyEl = document.getElementById('cart-empty-state')!;
    const summaryEl = document.getElementById('cart-summary-box')!;
    const submitBtn = document.getElementById('btn-submit-order') as HTMLButtonElement;
    const whatsappBtn = document.getElementById('btn-whatsapp-order') as HTMLButtonElement | null;
    if (whatsappBtn) whatsappBtn.disabled = !this.storeContact.whatsapp || items.length === 0;

    if (items.length === 0) {
      emptyEl.hidden = false;
      listEl.innerHTML = '';
      summaryEl.hidden = true;
      if (submitBtn) submitBtn.disabled = true;
      return;
    }

    emptyEl.hidden = true;
    summaryEl.hidden = false;
    if (submitBtn) submitBtn.disabled = false;

    listEl.innerHTML = '';
    for (const item of items) {
      const lineTotal = (item.product.price * item.quantity).toFixed(2);
      const row = document.createElement('div');
      row.className = 'cart-item-row';
      row.innerHTML = `
        <div>
          <div class="cart-item-title">${item.product.name}</div>
          <div class="cart-item-sub">${item.product.price.toFixed(2)} ₺ / ${item.product.unit} • Toplam: <strong>${lineTotal} ₺</strong></div>
        </div>
        <div class="cart-item-controls">
          <button type="button" class="btn-outline-sm btn-dec" aria-label="Azalt">−</button>
          <strong>${item.quantity}</strong>
          <button type="button" class="btn-outline-sm btn-inc" aria-label="Artır">+</button>
          <button type="button" class="btn-outline-sm btn-del" aria-label="Ürünü Sil" style="color:#dc2626;">🗑</button>
        </div>
      `;

      row.querySelector('.btn-dec')!.addEventListener('click', () => {
        cartStore.updateQuantity(item.product.id, item.quantity - 1);
      });
      row.querySelector('.btn-inc')!.addEventListener('click', () => {
        cartStore.updateQuantity(item.product.id, item.quantity + 1);
      });
      row.querySelector('.btn-del')!.addEventListener('click', () => {
        cartStore.removeItem(item.product.id);
      });
      listEl.appendChild(row);
    }

    document.getElementById('cart-subtotal-val')!.textContent = `${total.toFixed(2)} ₺`;
    document.getElementById('cart-total-val')!.textContent = `${total.toFixed(2)} ₺`;
  }

  // -------------------------------------------------------------------------
  // ORDER TRACKER
  // -------------------------------------------------------------------------
  private async showOrderInTracker(orderNumber: string, locationToken?: string): Promise<void> {
    const dlg = document.getElementById('dialog-order-tracker') as HTMLDialogElement;
    const input = document.getElementById('track-order-no') as HTMLInputElement;
    const resultArea = document.getElementById('tracker-result-area')!;

    input.value = orderNumber;
    if (!dlg.open) {
      dlg.showModal();
    }

    resultArea.innerHTML = `<p>Sipariş durumu sorgulanıyor...</p>`;
    try {
      const order = await ApiClient.trackOrder(orderNumber);
      const savedToken = locationToken || sessionStorage.getItem(`cm2-location-${orderNumber}`) || undefined;
      this.renderTrackerCard(order, resultArea, savedToken);
    } catch (err: any) {
      resultArea.innerHTML = `<div class="form-error-box">${err.message}</div>`;
    }
  }

  private renderTrackerCard(order: OrderResponse, container: HTMLElement, locationToken?: string): void {
    const itemsHtml = order.items
      .map(
        (i) =>
          `<li><strong>${i.product_name_snapshot}</strong> — ${i.quantity} ${i.unit_snapshot} x ${i.unit_price_snapshot.toFixed(2)} ₺ = <strong>${i.line_total.toFixed(2)} ₺</strong></li>`
      )
      .join('');

    const logsHtml = order.status_logs
      .map(
        (l) =>
          `<li><small>${new Date(l.created_at).toLocaleString('tr-TR')}</small> — <strong>${l.new_status}</strong>: ${l.note || ''}</li>`
      )
      .join('');

    container.innerHTML = `
      <div class="tracker-card">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
          <div>
            <span class="field-hint">Sipariş Numarası</span>
            <h3 style="margin:0; font-size:1.3rem;">${order.order_number}</h3>
          </div>
          <span class="status-pill status-${order.status}">${order.status_label || order.status}</span>
        </div>
        <hr style="border:none; border-top:1px solid #cbd5e1; margin:0.85rem 0;" />
        <p style="margin:0.25rem 0;"><strong>Müşteri:</strong> ${order.customer_name} (${order.customer_phone})</p>
        <p style="margin:0.25rem 0;"><strong>Teslimat & Ödeme:</strong> Çeşme Market 2 Mağazadan Teslim • Mağazada Ödeme</p>
        <p style="margin:0.25rem 0;"><strong>Ödenecek Toplam Tutar:</strong> <span style="font-size:1.2rem; font-weight:900;">${order.total_amount.toFixed(2)} ₺</span></p>
        ${locationToken && !['HAZIR', 'TESLIM_EDILDI', 'IPTAL_EDILDI'].includes(order.status) ? `
        <section class="customer-location-share">
          <h4>Mağazaya gelişinizi paylaşın</h4>
          <p>Bu isteğe bağlı özellik, siparişinizi hazırlayabilmemiz için son konumunuzu mağaza yöneticisine gösterir. Konum, paylaşımı durdurduğunuzda veya sipariş hazır/iptal/teslim edildiğinde silinir; 2 saat güncelleme gelmezse paylaşım otomatik kapanır. Paylaşılan konum sadece sipariş hazırlığı için kullanılır.</p>
          <details class="location-privacy-details">
            <summary>Konum verisi hakkında aydınlatma</summary>
            <p><strong>Veri sorumlusu:</strong> Çeşme Market 2. Paylaşılan GPS konumu, açık siparişinizi mağazaya varmadan hazırlamak amacıyla işlenir ve yalnızca yetkili mağaza yöneticisine gösterilir.</p>
            <p>Uygulama yalnızca son koordinatı tutar; konum geçmişi oluşturmaz. Paylaşım durdurulduğunda, sipariş hazır/iptal/teslim edildiğinde veya 2 saat güncelleme gelmediğinde koordinat silinir.</p>
            <p>Konum verisi mağazanın sipariş sistemi üzerinden iletilir ve yalnızca yetkili yönetici panelinde görünür; müşteri koordinatları harici harita servisine gönderilmez. Konum paylaşımı sipariş oluşturmanın şartı değildir. İsteğinizi durdurabilir veya konum verinizle ilgili başvurularınızı mağaza iletişim kanallarından iletebilirsiniz.</p>
          </details>
          <div class="form-checkbox-row">
            <input type="checkbox" id="customer-location-consent" />
            <label for="customer-location-consent">Konumumu siparişim hazırlanırken mağaza yöneticisiyle paylaşmayı seçiyorum. İstediğim zaman durdurabilirim.</label>
          </div>
          <div class="location-share-actions">
            <button type="button" id="btn-start-location-share" class="btn-primary-yellow" disabled>📍 Konum paylaşımını başlat</button>
            <button type="button" id="btn-stop-location-share" class="btn-outline-sm" hidden>Paylaşımı durdur</button>
          </div>
          <p id="customer-location-share-status" class="field-hint" role="status" aria-live="polite">Konum paylaşımı kapalı.</p>
        </section>` : ''}
        <h4 style="margin:0.85rem 0 0.35rem;">Sipariş Kalemleri</h4>
        <ul style="margin:0; padding-left:1.25rem; font-size:0.88rem;">${itemsHtml}</ul>
        <h4 style="margin:0.85rem 0 0.35rem;">Sipariş Durum Tarihçesi</h4>
        <ul style="margin:0; padding-left:1.25rem; font-size:0.82rem; color:#475569;">${logsHtml}</ul>
      </div>
    `;
    if (locationToken && !['HAZIR', 'TESLIM_EDILDI', 'IPTAL_EDILDI'].includes(order.status)) {
      const consentCheckbox = document.getElementById('customer-location-consent') as HTMLInputElement;
      const startButton = document.getElementById('btn-start-location-share') as HTMLButtonElement;
      const stopButton = document.getElementById('btn-stop-location-share') as HTMLButtonElement;
      consentCheckbox.addEventListener('change', () => { startButton.disabled = !consentCheckbox.checked; });
      startButton.addEventListener('click', () => this.startLocationSharing(order.order_number, locationToken));
      stopButton.addEventListener('click', () => this.stopLocationSharing());
    }
  }

  // -------------------------------------------------------------------------
  // STORE MANAGEMENT PANEL (ADMIN & STAFF)
  // -------------------------------------------------------------------------
  private async openAdminPanel(): Promise<void> {
    const dlg = document.getElementById('dialog-admin-panel') as HTMLDialogElement;
    if (!dlg.open) {
      dlg.showModal();
    }
    if (ApiClient.getToken()) {
      await this.loadAdminDashboard();
    }
  }

  private async loadAdminDashboard(): Promise<void> {
    const loginSec = document.getElementById('admin-login-section')!;
    const dashSec = document.getElementById('admin-dashboard-section')!;
    const logoutBtn = document.getElementById('btn-admin-logout')!;
    const badge = document.getElementById('admin-user-badge')!;

    try {
      const dash = await ApiClient.getAdminDashboard();
      this.currentAdminRole = dash.current_user.role;
      loginSec.hidden = true;
      dashSec.hidden = false;
      logoutBtn.hidden = false;
      badge.textContent = `${dash.current_user.full_name} (${dash.current_user.role})`;

      document.getElementById('kpi-new-orders')!.textContent = String(dash.new_orders);
      document.getElementById('kpi-approved-orders')!.textContent = String(dash.approved_orders);
      document.getElementById('kpi-preparing-orders')!.textContent = String(dash.preparing_orders);
      document.getElementById('kpi-ready-orders')!.textContent = String(dash.ready_orders);
      document.getElementById('kpi-delivered-orders')!.textContent = String(dash.delivered_orders);
      document.getElementById('kpi-total-revenue')!.textContent = `${dash.active_revenue.toFixed(2)} ₺`;

      // Populate POS status & Notification feed
      this.renderPosAndNotifications(dash.integration, dash.recent_notifications);
      await this.loadAdminOrdersTable();
      await this.loadAdminProductsTable();
      const locationPanel = document.getElementById('admin-live-location-panel')!;
      locationPanel.hidden = this.currentAdminRole !== 'ADMIN';
      document.getElementById('admin-media-tab-btn')!.hidden = this.currentAdminRole !== 'ADMIN';
      document.getElementById('admin-settings-tab-btn')!.hidden = this.currentAdminRole !== 'ADMIN';
      if (dash.contact) {
        this.storeContact = dash.contact;
        this.renderStoreContact();
        this.populateContactSettingsForm();
      }
      const productPhotoFile = document.getElementById('prod-form-image') as HTMLInputElement;
      const productPhotoFields = productPhotoFile.closest('.form-field')!;
      const productPhotoActions = document.getElementById('btn-clear-product-image')!.closest('.form-field')!;
      productPhotoFields.hidden = this.currentAdminRole !== 'ADMIN';
      productPhotoActions.hidden = this.currentAdminRole !== 'ADMIN';
      if (this.currentAdminRole === 'ADMIN') {
        await this.loadAdminLiveLocations();
        await this.loadAdminStoreMedia();
        this.startAdminLocationPolling();
      } else {
        this.stopAdminLocationPolling();
      }
    } catch (err: any) {
      ApiClient.setToken(null);
      loginSec.hidden = false;
      dashSec.hidden = true;
      logoutBtn.hidden = true;
      badge.textContent = 'Giriş Yapılmadı';
      const errorBox = document.getElementById('admin-login-error');
      if (errorBox) {
        errorBox.textContent = `Oturum açıldı ancak yönetim paneli yüklenemedi: ${err?.message || 'Bilinmeyen hata'}`;
        errorBox.hidden = false;
      }
    }
  }

  private startAdminLocationPolling(): void {
    if (this.adminLocationPollId !== null) return;
    this.adminLocationPollId = window.setInterval(() => {
      const dialog = document.getElementById('dialog-admin-panel') as HTMLDialogElement;
      const ordersTab = document.getElementById('admin-tab-orders')!;
      if (dialog.open && !ordersTab.hidden && this.currentAdminRole === 'ADMIN') {
        void this.loadAdminLiveLocations();
      }
    }, 15000);
  }

  private stopAdminLocationPolling(): void {
    if (this.adminLocationPollId !== null) {
      window.clearInterval(this.adminLocationPollId);
      this.adminLocationPollId = null;
    }
  }

  private async loadAdminLiveLocations(): Promise<void> {
    const list = document.getElementById('admin-live-location-list');
    if (!list || this.currentAdminRole !== 'ADMIN') return;
    try {
      const locations = await ApiClient.getAdminLiveLocations();
      list.replaceChildren();
      if (locations.length === 0) {
        list.textContent = 'Şu anda konum paylaşan müşteri yok.';
        this.selectedMapLocationOrder = null;
        this.selectedMapCoordinates = null;
        document.getElementById('admin-live-location-map')!.innerHTML = '<div class="live-map-empty">Konum paylaşan müşteri olduğunda mağazaya göre yön ve mesafe burada görünür.</div>';
        return;
      }

      const selected = locations.find((item) => item.order_number === this.selectedMapLocationOrder) || locations[0];
      for (const location of locations) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `admin-live-location-item ${location.order_number === selected.order_number ? 'active' : ''}`;
        const ageSeconds = Math.max(0, Math.round((Date.now() - new Date(location.updated_at).getTime()) / 1000));
        button.textContent = `${location.order_number} · ${location.customer_name} · ${location.status} · ${ageSeconds}s önce`;
        button.addEventListener('click', () => {
          this.selectedMapLocationOrder = location.order_number;
          this.selectedMapCoordinates = null;
          void this.loadAdminLiveLocations();
        });
        list.appendChild(button);
      }

      const coordsChanged = !this.selectedMapCoordinates
        || Math.abs(selected.latitude - this.selectedMapCoordinates.latitude) > 0.00035
        || Math.abs(selected.longitude - this.selectedMapCoordinates.longitude) > 0.00035;
      const orderChanged = this.selectedMapLocationOrder !== selected.order_number;
      if (orderChanged || coordsChanged) {
        this.selectedMapLocationOrder = selected.order_number;
        this.selectedMapCoordinates = { latitude: selected.latitude, longitude: selected.longitude };
        const northMeters = (selected.latitude - this.storeCoordinates.latitude) * 111_320;
        const eastMeters = (selected.longitude - this.storeCoordinates.longitude)
          * 111_320 * Math.cos(this.storeCoordinates.latitude * Math.PI / 180);
        const distanceMeters = Math.round(Math.hypot(northMeters, eastMeters));
        const bearing = (Math.atan2(eastMeters, northMeters) * 180 / Math.PI + 360) % 360;
        const directions = ['Kuzey', 'Kuzeydoğu', 'Doğu', 'Güneydoğu', 'Güney', 'Güneybatı', 'Batı', 'Kuzeybatı'];
        const direction = directions[Math.round(bearing / 45) % 8];
        const x = Math.max(54, Math.min(546, 300 + eastMeters * 0.65));
        const y = Math.max(45, Math.min(295, 180 - northMeters * 0.65));
        const customerLabel = `${direction} · ${distanceMeters} m`;
        const map = document.getElementById('admin-live-location-map')!;
        map.innerHTML = `
          <svg viewBox="0 0 600 360" role="img" aria-label="Müşteri mağazanın ${direction.toLocaleLowerCase('tr-TR')} yönünde yaklaşık ${distanceMeters} metre uzakta">
            <defs><pattern id="live-map-grid" width="30" height="30" patternUnits="userSpaceOnUse"><path d="M 30 0 L 0 0 0 30" fill="none" stroke="#dbe4dc" stroke-width="1"/></pattern></defs>
            <rect width="600" height="360" fill="#f3f7f2"/><rect width="600" height="360" fill="url(#live-map-grid)"/>
            <path d="M0 275 C130 245 200 295 310 260 S480 245 600 270" fill="none" stroke="#d2ddd4" stroke-width="13"/>
            <path d="M90 0 C135 105 90 210 125 360 M480 0 C450 100 505 250 465 360" fill="none" stroke="#d2ddd4" stroke-width="11"/>
            <path d="M300 180 L${x.toFixed(1)} ${y.toFixed(1)}" fill="none" stroke="#b45309" stroke-width="3" stroke-dasharray="7 6"/>
            <circle cx="300" cy="180" r="21" fill="#166534" stroke="white" stroke-width="4"/><text x="300" y="185" text-anchor="middle" fill="white" font-size="14" font-weight="700">M</text>
            <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="18" fill="#dc2626" stroke="white" stroke-width="4"/><text x="${x.toFixed(1)}" y="${(y + 5).toFixed(1)}" text-anchor="middle" fill="white" font-size="14" font-weight="700">●</text>
            <rect x="${Math.max(8, Math.min(420, x - 80)).toFixed(1)}" y="${Math.max(8, y - 47).toFixed(1)}" width="160" height="30" rx="15" fill="white" stroke="#cbd5e1"/><text x="${Math.max(88, Math.min(500, x)).toFixed(1)}" y="${Math.max(28, y - 27).toFixed(1)}" text-anchor="middle" fill="#7c2d12" font-size="13" font-weight="700">${customerLabel}</text>
            <text x="300" y="222" text-anchor="middle" fill="#166534" font-size="13" font-weight="700">MAĞAZA</text>
            <text x="570" y="35" text-anchor="middle" fill="#334155" font-size="14" font-weight="700">↑ K</text>
          </svg>`;
      }
    } catch (err: any) {
      list.textContent = `Konumlar alınamadı: ${err.message}`;
    }
  }

  private async loadAdminOrdersTable(): Promise<void> {
    const statusFilter = (
      document.getElementById('admin-order-status-filter') as HTMLSelectElement
    ).value;
    const orders = await ApiClient.getAdminOrders(statusFilter);
    const tbody = document.getElementById('admin-orders-tbody')!;
    tbody.innerHTML = '';

    for (const o of orders) {
      const tr = document.createElement('tr');
      const itemsText = o.items
        .map((i) => `${i.product_name_snapshot} (x${i.quantity})`)
        .join('<br/>');

      tr.innerHTML = `
        <th>
          <div>${o.order_number}</div>
          <small style="font-weight:400; color:#64748b;">${new Date(o.created_at).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}</small>
        </th>
        <td>
          <strong>${o.customer_name}</strong><br/>
          <span>📞 ${o.customer_phone}</span>
          ${o.order_note ? `<div style="font-size:0.76rem; color:#92400e; margin-top:0.2rem;">📝 Not: ${o.order_note}</div>` : ''}
        </td>
        <td>${itemsText}</td>
        <td><strong>${o.total_amount.toFixed(2)} ₺</strong></td>
        <td><span class="status-pill status-${o.status}">${o.status_label || o.status}</span></td>
        <td>
          <div style="display:flex; gap:0.35rem; flex-wrap:wrap;">
            <button type="button" class="btn-outline-sm" data-set-status="ONAYLANDI">Onayla</button>
            <button type="button" class="btn-outline-sm" data-set-status="HAZIRLANIYOR">Hazırlanıyor</button>
            <button type="button" class="btn-primary-yellow" style="padding:0.35rem 0.65rem; min-height:34px; font-size:0.78rem;" data-set-status="HAZIR">✅ Hazır</button>
            <button type="button" class="btn-outline-sm" data-set-status="TESLIM_EDILDI">Teslim Edildi</button>
            <button type="button" class="btn-outline-sm" style="color:#dc2626;" data-set-status="IPTAL_EDILDI">İptal</button>
          </div>
        </td>
      `;

      for (const btn of tr.querySelectorAll<HTMLButtonElement>('button[data-set-status]')) {
        btn.addEventListener('click', async () => {
          const targetStatus = btn.dataset.setStatus!;
          try {
            await ApiClient.updateOrderStatus(o.id, targetStatus);
            this.showToast(`Sipariş ${o.order_number} durumu güncellendi.`);
            await this.loadAdminDashboard();
          } catch (err: any) {
            this.showToast(`Hata: ${err.message}`);
          }
        });
      }

      tbody.appendChild(tr);
    }
  }

  private async loadAdminProductsTable(): Promise<void> {
    const allProds = await ApiClient.getProducts({ include_inactive: true });
    this.products = allProds.filter((p) => p.is_active);
    this.applyProductFilters();

    // Populate the category select inside the product form
    const catSelect = document.getElementById('prod-form-category') as HTMLSelectElement;
    catSelect.innerHTML = this.categories
      .map((c) => `<option value="${c.id}">${c.icon} ${c.name}</option>`)
      .join('');


    const tbody = document.getElementById('admin-products-tbody')!;
    tbody.innerHTML = '';

    for (const p of allProds) {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <th>
          <div>${p.name}</div>
          <small style="font-weight:400; color:#64748b;">Barkod: ${p.barcode}</small>
        </th>
        <td>${p.category_name || ''}</td>
        <td><strong>${p.price.toFixed(2)} ₺</strong> / ${p.unit}</td>
        <td>
          <strong>${p.stock_quantity}</strong> ${p.unit}<br/>
          <small>${p.is_sample_data ? 'Örnek Katalog' : 'Doğrulanmış POS/CSV'}</small>
        </td>
        <td>
          <div style="display:flex; gap:0.35rem;">
            <button type="button" class="btn-outline-sm btn-edit-prod">Düzenle</button>
            <button type="button" class="btn-outline-sm btn-toggle-prod">
              ${p.is_active ? 'Pasife Al' : 'Aktifleştir'}
            </button>
          </div>
        </td>
      `;

      if (p.image_url) {
        const productNameCell = tr.querySelector('th')!;
        const thumb = document.createElement('img');
        thumb.className = 'admin-product-thumb';
        thumb.src = p.image_url;
        thumb.alt = `${p.name} fotoğrafı`;
        thumb.loading = 'lazy';
        productNameCell.prepend(thumb);
      }

      tr.querySelector('.btn-edit-prod')!.addEventListener('click', () => {
        this.populateProductFormForEdit(p);
      });

      tr.querySelector('.btn-toggle-prod')!.addEventListener('click', async () => {
        try {
          await ApiClient.toggleProductActive(p.id);
          this.showToast(`"${p.name}" durumu güncellendi.`);
          await this.loadAdminProductsTable();
        } catch (err: any) {
          this.showToast(`Hata: ${err.message}`);
        }
      });

      tbody.appendChild(tr);
    }
  }

  private populateProductFormForEdit(p: Product): void {
    const form = document.getElementById('admin-product-form') as HTMLFormElement;
    form.hidden = false;
    document.getElementById('admin-prod-form-title')!.textContent = `Ürün Düzenle: ${p.name}`;
    (document.getElementById('prod-form-id') as HTMLInputElement).value = String(p.id);
    (document.getElementById('prod-form-barcode') as HTMLInputElement).value = p.barcode;
    (document.getElementById('prod-form-name') as HTMLInputElement).value = p.name;
    (document.getElementById('prod-form-category') as HTMLSelectElement).value = String(p.category_id);
    (document.getElementById('prod-form-price') as HTMLInputElement).value = String(p.price);
    (document.getElementById('prod-form-unit') as HTMLSelectElement).value = p.unit;
    (document.getElementById('prod-form-stock') as HTMLInputElement).value = String(p.stock_quantity);
    (document.getElementById('prod-form-color') as HTMLInputElement).value = p.primary_color;
    (document.getElementById('prod-form-desc') as HTMLInputElement).value = p.description || '';
    (document.getElementById('prod-form-image-url') as HTMLInputElement).value = p.image_url || '';
    (document.getElementById('prod-form-image') as HTMLInputElement).value = '';
    this.setProductImagePreview(p.image_url);
  }

  private setProductImagePreview(imageUrl: string | null): void {
    const preview = document.getElementById('prod-form-image-preview') as HTMLImageElement;
    preview.hidden = !imageUrl;
    preview.src = imageUrl || '';
  }

  private async loadAdminStoreMedia(): Promise<void> {
    const list = document.getElementById('admin-media-list');
    if (!list || this.currentAdminRole !== 'ADMIN') return;
    try {
      const items = await ApiClient.getAdminStoreMedia();
      list.replaceChildren();
      if (!items.length) {
        list.textContent = 'Henüz galeri fotoğrafı veya sponsor banner eklenmedi.';
        return;
      }
      for (const item of items) {
        const row = document.createElement('article');
        row.className = 'admin-media-row';
        const image = document.createElement('img');
        image.src = item.image_url;
        image.alt = item.title || (item.placement === 'gallery' ? 'Galeri fotoğrafı' : 'Sponsor banner');
        image.loading = 'lazy';
        const details = document.createElement('div');
        details.className = 'admin-media-details';
        const title = document.createElement('strong');
        title.textContent = item.title || (item.placement === 'gallery' ? 'Başlıksız galeri fotoğrafı' : 'Başlıksız sponsor banner');
        const meta = document.createElement('small');
        meta.textContent = `${item.placement === 'gallery' ? 'Fotoğraf galerisi' : 'Sponsor banner'} · Sıra ${item.sort_order} · ${item.is_active ? 'Yayında' : 'Taslak'}`;
        details.append(title, meta);
        const actions = document.createElement('div');
        actions.className = 'admin-media-actions';
        const edit = document.createElement('button');
        edit.type = 'button';
        edit.className = 'btn-outline-sm';
        edit.textContent = 'Düzenle';
        edit.addEventListener('click', () => this.populateStoreMediaForm(item));
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'btn-outline-sm';
        remove.textContent = 'Sil';
        remove.addEventListener('click', async () => {
          if (!window.confirm('Bu vitrin görseli kaydını silmek istiyor musunuz?')) return;
          try {
            await ApiClient.deleteStoreMedia(item.id);
            this.storeMedia = this.storeMedia.filter((media) => media.id !== item.id);
            this.renderStoreMedia();
            await this.loadAdminStoreMedia();
          } catch (err: any) {
            this.showToast(`Görsel silinemedi: ${err.message}`);
          }
        });
        actions.append(edit, remove);
        row.append(image, details, actions);
        list.appendChild(row);
      }
    } catch (err: any) {
      list.textContent = `Vitrin görselleri yüklenemedi: ${err.message}`;
    }
  }

  private populateStoreMediaForm(item?: StoreMedia): void {
    const form = document.getElementById('admin-media-form') as HTMLFormElement;
    form.hidden = false;
    form.reset();
    (document.getElementById('media-form-id') as HTMLInputElement).value = item ? String(item.id) : '';
    (document.getElementById('media-form-image-url') as HTMLInputElement).value = item?.image_url || '';
    (document.getElementById('media-form-placement') as HTMLSelectElement).value = item?.placement || 'gallery';
    (document.getElementById('media-form-title') as HTMLInputElement).value = item?.title || '';
    (document.getElementById('media-form-link') as HTMLInputElement).value = item?.link_url || '';
    (document.getElementById('media-form-order') as HTMLInputElement).value = String(item?.sort_order || 0);
    (document.getElementById('media-form-active') as HTMLInputElement).checked = item?.is_active ?? true;
    (document.getElementById('media-form-file') as HTMLInputElement).value = '';
    const preview = document.getElementById('media-form-preview') as HTMLImageElement;
    preview.hidden = !item?.image_url;
    preview.src = item?.image_url || '';
    document.getElementById('admin-media-form-title')!.textContent = item
      ? 'Vitrin görselini düzenle'
      : 'Vitrin görseli ekle';
    form.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  private renderPosAndNotifications(integration: any, notifications: any[]): void {
    const posBox = document.getElementById('pos-status-summary')!;
    posBox.innerHTML = `
      <div style="background:#ffffff; border:1px solid #cbd5e1; padding:0.75rem; border-radius:8px; font-size:0.84rem;">
        <div><strong>POS Durumu:</strong> ${integration.pos_software_name}</div>
        <div><strong>Son Veri Kaynağı:</strong> ${integration.last_sync_source}</div>
        <div><strong>Son Güncelleme Zamanı:</strong> ${integration.last_synced_at ? new Date(integration.last_synced_at).toLocaleString('tr-TR') : 'Başlangıç Verisi'}</div>
        <div><strong>Katalog Özeti:</strong> Toplam ${integration.total_products} ürün (${integration.verified_products} doğrulanmış, ${integration.sample_products} örnek ürün)</div>
      </div>
    `;

    const feedBox = document.getElementById('admin-notifications-feed')!;
    if (!notifications || notifications.length === 0) {
      feedBox.innerHTML = `<p class="field-hint">Henüz yeni bildirim kaydı yok.</p>`;
      return;
    }

    feedBox.innerHTML = notifications
      .map(
        (n) => `
        <div class="notif-item">
          <div><strong>[${n.channel}]</strong> ${n.message}</div>
          <small style="color:#64748b;">${new Date(n.created_at).toLocaleString('tr-TR')} • Durum: ${n.delivered ? 'İletildi' : 'Devre Dışı / Beklemede'}</small>
        </div>
      `
      )
      .join('');
  }

  // -------------------------------------------------------------------------
  // UI EVENT BINDINGS
  // -------------------------------------------------------------------------
  private bindGlobalUI(): void {
    // Subscribe to Cart Store changes
    cartStore.subscribe(() => this.renderCartItems());

    // View mode buttons
    document.getElementById('btn-mode-landing')!.addEventListener('click', () => {
      this.switchViewMode('landing');
    });
    document.getElementById('btn-mode-2d')!.addEventListener('click', () => {
      this.switchViewMode('2d');
    });
    document.getElementById('btn-return-to-landing')!.addEventListener('click', () => {
      this.switchViewMode('landing');
    });
    document.getElementById('btn-hero-enter-2d')!.addEventListener('click', () => {
      this.switchViewMode('2d');
    });
    document.getElementById('btn-landing-open-catalog')!.addEventListener('click', () => {
      this.activeCategoryId = null;
      this.searchQuery = '';
      this.applyProductFilters();
      this.switchViewMode('2d');
    });
    document.getElementById('btn-landing-featured-catalog')!.addEventListener('click', () => {
      this.activeCategoryId = null;
      this.searchQuery = '';
      this.applyProductFilters();
      this.switchViewMode('2d');
    });

    // Global Search Form
    const searchForm = document.getElementById('global-search-form') as HTMLFormElement;
    const searchInput = document.getElementById('global-search-input') as HTMLInputElement;
    searchForm.addEventListener('submit', (e) => {
      e.preventDefault();
      this.searchQuery = searchInput.value;
      this.applyProductFilters();
      this.switchViewMode('2d');
    });
    searchInput.addEventListener('input', () => {
      this.searchQuery = searchInput.value;
      this.applyProductFilters();
    });

    // Product Detail Dialog quantity & add to cart
    const qtyInput = document.getElementById('dlg-qty-input') as HTMLInputElement;
    document.getElementById('dlg-qty-minus')!.addEventListener('click', () => {
      const v = Math.max(1, parseInt(qtyInput.value || '1', 10) - 1);
      qtyInput.value = String(v);
    });
    document.getElementById('dlg-qty-plus')!.addEventListener('click', () => {
      const maxStock = this.selectedProduct?.stock_quantity || 99;
      const v = Math.min(maxStock, parseInt(qtyInput.value || '1', 10) + 1);
      qtyInput.value = String(v);
    });
    document.getElementById('dlg-btn-add-cart')!.addEventListener('click', () => {
      if (!this.selectedProduct) return;
      const qty = Math.max(1, parseInt(qtyInput.value || '1', 10));
      cartStore.addItem(this.selectedProduct, qty);
      (document.getElementById('dialog-product-detail') as HTMLDialogElement).close();
      this.showToast(`"${this.selectedProduct.name}" (${qty} ${this.selectedProduct.unit}) sepete eklendi.`);
    });

    // Header Modals (Cart, Tracker, Admin)
    document.getElementById('btn-open-cart')!.addEventListener('click', () => {
      this.openCartModal();
    });
    document.getElementById('btn-whatsapp-order')!.addEventListener('click', () => {
      this.openWhatsAppOrderRequest();
    });
    document.getElementById('btn-open-tracker')!.addEventListener('click', () => {
      const dlg = document.getElementById('dialog-order-tracker') as HTMLDialogElement;
      dlg.showModal();
    });
    document.getElementById('btn-open-admin')!.addEventListener('click', () => {
      this.openAdminPanel();
    });

    // Checkout Order Submission Form (Validate on blur / submit, clear error on input)
    const checkoutForm = document.getElementById('checkout-order-form') as HTMLFormElement;
    const errorBox = document.getElementById('checkout-form-error')!;
    const submitOrderBtn = document.getElementById('btn-submit-order') as HTMLButtonElement;

    for (const field of checkoutForm.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>('input, textarea')) {
      field.addEventListener('input', () => {
        field.removeAttribute('aria-invalid');
        errorBox.hidden = true;
      });
      field.addEventListener('blur', () => {
        if (field.value && !field.checkValidity()) {
          field.setAttribute('aria-invalid', 'true');
        }
      });
    }

    checkoutForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      errorBox.hidden = true;

      const items = cartStore.getItems();
      if (items.length === 0) {
        errorBox.textContent = 'Sepetiniz boş. Lütfen önce ürün ekleyin.';
        errorBox.hidden = false;
        return;
      }

      const nameInput = document.getElementById('checkout-name') as HTMLInputElement;
      const phoneInput = document.getElementById('checkout-phone') as HTMLInputElement;
      const emailInput = document.getElementById('checkout-email') as HTMLInputElement;
      const noteInput = document.getElementById('checkout-note') as HTMLTextAreaElement;
      const kvkkInput = document.getElementById('checkout-kvkk') as HTMLInputElement;

      if (nameInput.value.trim().length < 2) {
        nameInput.setAttribute('aria-invalid', 'true');
        nameInput.focus();
        errorBox.textContent = 'Lütfen adınızı ve soyadınızı giriniz.';
        errorBox.hidden = false;
        return;
      }

      const digits = phoneInput.value.replace(/\D/g, '');
      if (digits.length < 10) {
        phoneInput.setAttribute('aria-invalid', 'true');
        phoneInput.focus();
        errorBox.textContent = 'Lütfen geçerli bir cep telefonu numarası giriniz (en az 10 rakam).';
        errorBox.hidden = false;
        return;
      }

      submitOrderBtn.disabled = true;
      submitOrderBtn.textContent = 'Siparişiniz Oluşturuluyor...';

      try {
        const idempotencyKey = `cm2-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        const createdOrder = await ApiClient.createOrder({
          customer_name: nameInput.value.trim(),
          customer_phone: phoneInput.value.trim(),
          customer_email: emailInput.value.trim() || null,
          order_note: noteInput.value.trim() || null,
          idempotency_key: idempotencyKey,
          kvkk_approved: kvkkInput.checked,
          items: items.map((i) => ({
            product_id: i.product.id,
            quantity: i.quantity,
          })),
        });

        cartStore.clear();
        checkoutForm.reset();
        (document.getElementById('dialog-cart-checkout') as HTMLDialogElement).close();
        if (createdOrder.location_session_token) {
          sessionStorage.setItem(`cm2-location-${createdOrder.order_number}`, createdOrder.location_session_token);
        }
        this.showToast(`Siparişiniz alındı! Sipariş No: ${createdOrder.order_number}`);
        await this.showOrderInTracker(createdOrder.order_number, createdOrder.location_session_token);
      } catch (err: any) {
        errorBox.textContent = err.message || 'Sipariş oluşturulurken bir hata meydana geldi.';
        errorBox.hidden = false;
      } finally {
        submitOrderBtn.disabled = false;
        submitOrderBtn.textContent = '✅ Siparişi Tamamla (Mağazada Öde)';
      }
    });

    // Order Tracker Form
    document.getElementById('order-track-form')!.addEventListener('submit', async (e) => {
      e.preventDefault();
      const no = (document.getElementById('track-order-no') as HTMLInputElement).value.trim();
      if (no) {
        await this.showOrderInTracker(no);
      }
    });

    document.getElementById('admin-login-form')!.addEventListener('submit', async (e) => {
      e.preventDefault();
      const u = (document.getElementById('admin-username') as HTMLInputElement).value.trim();
      const p = (document.getElementById('admin-password') as HTMLInputElement).value;
      const errEl = document.getElementById('admin-login-error')!;
      errEl.hidden = true;

      try {
        const res = await ApiClient.login(u, p);
        ApiClient.setToken(res.access_token);
        (document.getElementById('admin-password') as HTMLInputElement).value = '';
        this.showToast(`Hoş geldiniz, ${res.full_name}`);
        await this.loadAdminDashboard();
      } catch (err: any) {
        errEl.textContent = err.message;
        errEl.hidden = false;
      }
    });

    document.getElementById('btn-admin-logout')!.addEventListener('click', () => {
      this.stopAdminLocationPolling();
      this.currentAdminRole = null;
      ApiClient.setToken(null);
      document.getElementById('admin-login-section')!.hidden = false;
      document.getElementById('admin-dashboard-section')!.hidden = true;
      document.getElementById('btn-admin-logout')!.hidden = true;
      document.getElementById('admin-user-badge')!.textContent = 'Giriş Yapılmadı';
    });
    document.getElementById('dialog-admin-panel')!.addEventListener('close', () => this.stopAdminLocationPolling());

    // Admin Tabs
    for (const tabBtn of document.querySelectorAll<HTMLButtonElement>('.admin-tab-btn')) {
      tabBtn.addEventListener('click', () => {
        const target = tabBtn.dataset.adminTab!;
        for (const b of document.querySelectorAll<HTMLButtonElement>('.admin-tab-btn')) {
          const active = b === tabBtn;
          b.classList.toggle('active', active);
          b.setAttribute('aria-selected', String(active));
        }
        document.getElementById('admin-tab-orders')!.hidden = target !== 'orders';
        document.getElementById('admin-tab-products')!.hidden = target !== 'products';
        document.getElementById('admin-tab-pos-csv')!.hidden = target !== 'pos-csv';
        document.getElementById('admin-tab-media')!.hidden = target !== 'media';
        document.getElementById('admin-tab-settings')!.hidden = target !== 'settings';
      });
    }

    // Password Change Form (ADMIN only)
    const pwdForm = document.getElementById('admin-password-change-form') as HTMLFormElement | null;
    if (pwdForm) {
      pwdForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const targetUser = (document.getElementById('pwd-target-username') as HTMLSelectElement).value;
        const currentAdminPwd = (document.getElementById('pwd-current-admin') as HTMLInputElement).value;
        const newPwd = (document.getElementById('pwd-new') as HTMLInputElement).value;
        const confirmPwd = (document.getElementById('pwd-new-confirm') as HTMLInputElement).value;
        const feedbackEl = document.getElementById('pwd-change-feedback')!;
        feedbackEl.hidden = true;

        if (newPwd !== confirmPwd) {
          feedbackEl.textContent = 'Yeni şifre ile şifre tekrarı birbiriyle eşleşmiyor.';
          feedbackEl.hidden = false;
          return;
        }
        if (newPwd.length < 6) {
          feedbackEl.textContent = 'Yeni şifre en az 6 karakter olmalıdır.';
          feedbackEl.hidden = false;
          return;
        }

        try {
          const res = await ApiClient.changeUserPassword({
            target_username: targetUser,
            current_admin_password: currentAdminPwd,
            new_password: newPwd,
          });
          pwdForm.reset();
          this.showToast(res.message);
        } catch (err: any) {
          feedbackEl.textContent = err.message || 'Şifre güncellenemedi.';
          feedbackEl.hidden = false;
        }
      });
    }

    // Store Contact Settings Form (ADMIN only)
    const contactForm = document.getElementById('admin-contact-settings-form') as HTMLFormElement | null;
    if (contactForm) {
      contactForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        try {
          const updated = await ApiClient.updateStoreContact({
            address: (document.getElementById('setting-store-address') as HTMLInputElement).value.trim(),
            phone: (document.getElementById('setting-store-phone') as HTMLInputElement).value.trim(),
            whatsapp: (document.getElementById('setting-store-whatsapp') as HTMLInputElement).value.trim(),
            maps_url: (document.getElementById('setting-store-maps') as HTMLInputElement).value.trim(),
          });
          this.storeContact = updated;
          this.renderStoreContact();
          this.showToast('Mağaza iletişim bilgileri güncellendi.');
        } catch (err: any) {
          this.showToast(`İletişim bilgileri kaydedilemedi: ${err.message}`);
        }
      });
    }

    document.getElementById('admin-order-status-filter')!.addEventListener('change', () => {
      this.loadAdminOrdersTable();
    });
    document.getElementById('btn-refresh-orders')!.addEventListener('click', () => {
      this.loadAdminDashboard();
    });
    document.getElementById('btn-refresh-live-locations')!.addEventListener('click', () => {
      this.loadAdminLiveLocations();
    });

    // Product Add/Edit Form
    const prodForm = document.getElementById('admin-product-form') as HTMLFormElement;
    document.getElementById('btn-toggle-new-product-form')!.addEventListener('click', () => {
      prodForm.reset();
      (document.getElementById('prod-form-id') as HTMLInputElement).value = '';
      (document.getElementById('prod-form-image-url') as HTMLInputElement).value = '';
      this.setProductImagePreview(null);
      document.getElementById('admin-prod-form-title')!.textContent = 'Yeni Ürün Ekle';
      prodForm.hidden = !prodForm.hidden;
    });
    document.getElementById('btn-cancel-prod-form')!.addEventListener('click', () => {
      prodForm.hidden = true;
    });

    const productImageInput = document.getElementById('prod-form-image') as HTMLInputElement;
    productImageInput.addEventListener('change', () => {
      const file = productImageInput.files?.[0];
      if (file) this.setProductImagePreview(URL.createObjectURL(file));
    });
    document.getElementById('btn-clear-product-image')!.addEventListener('click', () => {
      (document.getElementById('prod-form-image-url') as HTMLInputElement).value = '';
      productImageInput.value = '';
      this.setProductImagePreview(null);
    });

    prodForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const idStr = (document.getElementById('prod-form-id') as HTMLInputElement).value;
      const prodId = idStr ? parseInt(idStr, 10) : null;

      const payload: any = {
        barcode: (document.getElementById('prod-form-barcode') as HTMLInputElement).value.trim(),
        name: (document.getElementById('prod-form-name') as HTMLInputElement).value.trim(),
        category_id: parseInt(
          (document.getElementById('prod-form-category') as HTMLSelectElement).value,
          10
        ),
        price: parseFloat(
          (document.getElementById('prod-form-price') as HTMLInputElement).value.replace(',', '.')
        ),
        unit: (document.getElementById('prod-form-unit') as HTMLSelectElement).value,
        stock_quantity: parseInt(
          (document.getElementById('prod-form-stock') as HTMLInputElement).value,
          10
        ),
        primary_color: (document.getElementById('prod-form-color') as HTMLInputElement).value,
        secondary_color: '#1E293B',
        description: (document.getElementById('prod-form-desc') as HTMLInputElement).value.trim(),
        is_stock_verified: true,
        is_sample_data: false,
        is_active: true,
        image_url: (document.getElementById('prod-form-image-url') as HTMLInputElement).value || null,
      };

      try {
        const imageFile = productImageInput.files?.[0];
        if (imageFile) {
          const upload = await ApiClient.uploadImage(imageFile);
          payload.image_url = upload.image_url;
        }
        await ApiClient.saveProduct(prodId, payload);
        prodForm.hidden = true;
        this.showToast('Ürün kaydedildi.');
        await this.loadAdminProductsTable();
        this.renderLandingDiscovery();
      } catch (err: any) {
        this.showToast(`Hata: ${err.message}`);
      }
    });

    document.getElementById('gallery-prev')!.addEventListener('click', () => this.advanceGallery(-1));
    document.getElementById('gallery-next')!.addEventListener('click', () => this.advanceGallery(1));

    const mediaForm = document.getElementById('admin-media-form') as HTMLFormElement;
    document.getElementById('btn-add-media')!.addEventListener('click', () => this.populateStoreMediaForm());
    document.getElementById('btn-cancel-media-form')!.addEventListener('click', () => { mediaForm.hidden = true; });
    const mediaFileInput = document.getElementById('media-form-file') as HTMLInputElement;
    mediaFileInput.addEventListener('change', () => {
      const file = mediaFileInput.files?.[0];
      const preview = document.getElementById('media-form-preview') as HTMLImageElement;
      preview.hidden = !file;
      if (file) preview.src = URL.createObjectURL(file);
    });
    mediaForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const idValue = (document.getElementById('media-form-id') as HTMLInputElement).value;
      const mediaId = idValue ? Number(idValue) : null;
      const imageUrlInput = document.getElementById('media-form-image-url') as HTMLInputElement;
      const file = mediaFileInput.files?.[0];
      try {
        if (file) imageUrlInput.value = (await ApiClient.uploadImage(file)).image_url;
        if (!imageUrlInput.value) throw new Error('Lütfen bir görsel seçin.');
        const media = await ApiClient.saveStoreMedia(mediaId, {
          placement: (document.getElementById('media-form-placement') as HTMLSelectElement).value as StoreMedia['placement'],
          title: (document.getElementById('media-form-title') as HTMLInputElement).value.trim(),
          image_url: imageUrlInput.value,
          link_url: (document.getElementById('media-form-link') as HTMLInputElement).value.trim() || null,
          sort_order: Number((document.getElementById('media-form-order') as HTMLInputElement).value || 0),
          is_active: (document.getElementById('media-form-active') as HTMLInputElement).checked,
        });
        const existingIndex = this.storeMedia.findIndex((item) => item.id === media.id);
        if (existingIndex >= 0) this.storeMedia[existingIndex] = media;
        else this.storeMedia.push(media);
        this.storeMedia.sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);
        this.renderStoreMedia();
        this.startGalleryAutoplay();
        mediaForm.hidden = true;
        this.showToast('Vitrin görseli kaydedildi.');
        await this.loadAdminStoreMedia();
      } catch (err: any) {
        this.showToast(`Görsel kaydedilemedi: ${err.message}`);
      }
    });

    // CSV Export & Import
    const downloadAuthorizedCsv = async (url: string, filename: string) => {
      try {
        const res = await fetch(url, {
          headers: { Authorization: `Bearer ${ApiClient.getToken()}` },
        });
        const blob = await res.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
      } catch {
        this.showToast('CSV indirilemedi.');
      }
    };

    document.getElementById('btn-export-products-csv')!.addEventListener('click', () => {
      downloadAuthorizedCsv('/api/v1/admin/export/products.csv', 'cesme_market_2_urunler.csv');
    });
    document.getElementById('btn-export-orders-csv')!.addEventListener('click', () => {
      downloadAuthorizedCsv('/api/v1/admin/export/orders.csv', 'cesme_market_2_siparisler.csv');
    });

    document.getElementById('csv-upload-form')!.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fileInput = document.getElementById('csv-file-input') as HTMLInputElement;
      const resultBox = document.getElementById('csv-import-result')!;
      if (!fileInput.files || fileInput.files.length === 0) return;

      try {
        const res = await ApiClient.importCsv(fileInput.files[0]);
        resultBox.hidden = false;
        resultBox.innerHTML = `
          <div style="margin-top:0.75rem; padding:0.75rem; background:#dcfce7; color:#166534; border-radius:8px; font-weight:700;">
            ✅ CSV Aktarımı Tamamlandı: ${res.created_count} yeni ürün eklendi, ${res.updated_count} ürün güncellendi. (Hata: ${res.error_count})
          </div>
        `;
        await this.loadAdminDashboard();
      } catch (err: any) {
        resultBox.hidden = false;
        resultBox.innerHTML = `<div class="form-error-box">${err.message}</div>`;
      }
    });
  }

  private showToast(message: string): void {
    const toast = document.getElementById('app-toast')!;
    toast.textContent = message;
    toast.hidden = false;
    setTimeout(() => {
      toast.hidden = true;
    }, 3800);
  }
}

window.addEventListener('DOMContentLoaded', () => {
  new CesmeMarketApp();
});
