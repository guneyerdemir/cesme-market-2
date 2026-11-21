from sqlalchemy.orm import Session
from backend.config import (
    INITIAL_ADMIN_PASSWORD,
    INITIAL_ADMIN_USERNAME,
    INITIAL_STAFF_PASSWORD,
    INITIAL_STAFF_USERNAME,
)
from backend.models import (
    Category,
    Order,
    OrderItem,
    OrderStatusLog,
    Product,
    SystemMetadata,
    User,
)
from backend.pos_integration import slugify_tr
from backend.security import hash_password


def seed_initial_data(db: Session) -> None:
    # 1. Seed Users (Admin & Staff)
    if db.query(User).count() == 0:
        db.add_all(
            [
                User(
                    username=INITIAL_ADMIN_USERNAME,
                    password_hash=hash_password(INITIAL_ADMIN_PASSWORD),
                    full_name="Çeşme Market 2 - Mağaza Yöneticisi",
                    role="ADMIN",
                    is_active=True,
                ),
                User(
                    username=INITIAL_STAFF_USERNAME,
                    password_hash=hash_password(INITIAL_STAFF_PASSWORD),
                    full_name="Çeşme Market 2 - Reyon & Sipariş Personeli",
                    role="STAFF",
                    is_active=True,
                ),
            ]
        )
        db.commit()

    # 2. Seed Categories (10 Required Categories)
    if db.query(Category).count() == 0:
        categories_data = [
            ("Meyve ve Sebze", "meyve-ve-sebze", "🍎", 1),
            ("Süt ve Süt Ürünleri", "sut-ve-sut-urunleri", "🥛", 2),
            ("Et ve Tavuk", "et-ve-tavuk", "🥩", 3),
            ("Şarküteri", "sarkuteri", "🧀", 4),
            ("Temel Gıda", "temel-gida", "🌾", 5),
            ("İçecekler", "icecekler", "🥤", 6),
            ("Atıştırmalıklar", "atistirmaliklar", "🍪", 7),
            ("Temizlik Ürünleri", "temizlik-urunleri", "🧼", 8),
            ("Kişisel Bakım", "kisisel-bakim", "🧴", 9),
            ("Dondurulmuş Ürünler", "dondurulmus-urunler", "🍦", 10),
        ]
        for name, slug, icon, order in categories_data:
            db.add(
                Category(
                    name=name,
                    slug=slug,
                    icon=icon,
                    sort_order=order,
                    is_active=True,
                )
            )
        db.commit()

    # 3. Seed Sample Products
    if db.query(Product).count() == 0:
        cat_map = {c.slug: c.id for c in db.query(Category).all()}

        # Tuple format:
        # (barcode, name, category, price, unit, stock, primary_color, secondary_color, featured, badge, description)
        raw_products = [
            # Dış Cephe & Giriş Dolapları (Dondurulmuş / Su / Soğuk İçecek - Referans fotoğrafa birebir uygun)
            ('8690637010019', 'Algida Maraş Usulü Sade Dondurma 500 ml', 'dondurulmus-urunler', 135.0, 'Paket', 24, '#E11D48', '#FFFFFF', True, 'Ön Cephe Dolabı', 'Çeşme Market 2 girişindeki Algida dondurma dolabından kesme Maraş dondurması.'),
            ('8690637010026', 'Algida Magnum Badem 100 ml', 'dondurulmus-urunler', 55.0, 'Adet', 40, '#78350F', '#F59E0B', False, None, 'Badem kaplamalı vanilyalı Magnum dondurma.'),
            ('8690637010033', 'Cornetto Disc Çikolata 125 ml', 'dondurulmus-urunler', 45.0, 'Adet', 35, '#1D4ED8', '#FFFFFF', False, None, 'Çıtır külah içinde çikolatalı Cornetto.'),
            ('8690555010018', 'Erikli Doğal Kaynak Suyu 5 Litre', 'icecekler', 42.5, 'Adet', 50, '#0284C7', '#E0F2FE', True, 'Çok Satan', 'Uludağ zirvesinden Erikli 5L büyük boy su (Giriş su standı).'),
            ('8690555010025', 'Erikli Doğal Kaynak Suyu 6x1.5 Litre Paket', 'icecekler', 78.0, 'Paket', 30, '#0369A1', '#BAE6FD', False, None, "6'lı ekonomik paket Erikli 1.5L su."),

            # Meyve ve Sebze Reyonu
            ('2700001000011', 'Çeşme Tarla Domatesi', 'meyve-ve-sebze', 49.9, 'Kg', 45, '#EF4444', '#15803D', True, 'Taze Hasat', 'Ege bahçelerinden günlük taze kokulu salkım/tarla domatesi.'),
            ('2700001000028', 'Çengelköy Badem Salatalık', 'meyve-ve-sebze', 39.9, 'Kg', 35, '#16A34A', '#DCFCE7', False, None, 'Çıtır taze kahvaltılık badem salatalık.'),
            ('2700001000035', 'Amasya Elması', 'meyve-ve-sebze', 54.9, 'Kg', 40, '#DC2626', '#FEF08A', False, None, 'Sulu ve tatlı yerli elma.'),
            ('2700001000042', 'Anamur Yerli Muz', 'meyve-ve-sebze', 74.9, 'Kg', 30, '#FACC15', '#713F12', True, 'Günlük Taze', 'Yerli Anamur muzu.'),
            ('2700001000059', 'Finike Portakal', 'meyve-ve-sebze', 38.5, 'Kg', 50, '#F97316', '#FFEDD5', False, None, 'Bol sulu C vitamini deposu sofralık portakal.'),

            # Süt ve Süt Ürünleri Reyonu
            ('8690123020014', 'Pınar Tam Yağlı Süt 1 Litre', 'sut-ve-sut-urunleri', 44.5, 'Adet', 60, '#0EA5E9', '#FFFFFF', True, None, '%3.3 yağlı UHT uzun ömürlü Pınar süt.'),
            ('8690123020021', 'Sütaş Kaymaklı Yoğurt 1000 g', 'sut-ve-sut-urunleri', 79.9, 'Adet', 35, '#16A34A', '#FFFFFF', False, None, 'Geleneksel lezzet Sütaş tava yoğurdu.'),
            ('8690123020038', 'İçim Tereyağı 500 g', 'sut-ve-sut-urunleri', 215.0, 'Adet', 25, '#FACC15', '#1E3A8A', False, None, '%82 süt yağlı kahvaltılık ve yemeklik tereyağı.'),
            ('8690123020045', 'Sütaş Pratik Şişe Ayran 1 Litre', 'sut-ve-sut-urunleri', 39.5, 'Adet', 45, '#38BDF8', '#FFFFFF', False, None, 'Serinletici bol köpüklü Sütaş ayran.'),
            ('8690123020052', 'Pınar Labne 400 g', 'sut-ve-sut-urunleri', 98.0, 'Adet', 30, '#22C55E', '#FFFFFF', False, None, 'Kahvaltı ve tatlılar için sürülebilir Pınar Labne.'),

            # Temel Gıda Reyonu
            ('8690504030017', 'Tariş Kuzey Ege Sızma Zeytinyağı 1 Litre', 'temel-gida', 385.0, 'Litre', 22, '#15803D', '#FEF08A', True, 'Ege Özel', 'Soğuk sıkım erken hasat Ege sızma zeytinyağı.'),
            ('8690504030024', 'Komili Ayçiçek Yağı 2 Litre', 'temel-gida', 169.0, 'Adet', 32, '#F59E0B', '#FEF3C7', False, None, 'Yemeklik ve kızartmalık 2L ayçiçek yağı.'),
            ('8690504030031', 'Barilla Spagetti Makarna 500 g', 'temel-gida', 34.5, 'Paket', 80, '#1E3A8A', '#EF4444', False, None, 'Durum buğdayı irmiğinden Barilla No:5 Spagetti.'),
            ('8690504030048', 'Reis Osmancık Pirinç 1000 g', 'temel-gida', 79.0, 'Paket', 45, '#B91C1C', '#FFFFFF', False, None, 'Tane tane pilavlık yerli Osmancık pirinci.'),
            ('8690504030055', 'Tat Domates Salçası 830 g', 'temel-gida', 64.9, 'Adet', 50, '#DC2626', '#FFFFFF', False, None, 'Mevsim domateslerinden katkısız Tat salça.'),
            ('8690504030062', 'Çaykur Tiryaki Çayı 1000 g', 'temel-gida', 195.0, 'Paket', 40, '#EF4444', '#FACC15', True, 'İndirimli', 'Karadeniz yapraklarından demli Tiryaki çayı.'),

            # Atıştırmalık Reyonu
            ('8690504040016', "Ülker Çikolatalı Gofret 5'li Paket", 'atistirmaliklar', 49.5, 'Paket', 70, '#DC2626', '#FFFFFF', False, None, "Ülker Çikolatalı Gofret sevmeyen var mı? 5'li ekonomik paket."),
            ('8690504040023', 'Eti Karam Gurme Bitter Çikolata 50 g', 'atistirmaliklar', 24.5, 'Adet', 65, '#451A03', '#F59E0B', False, None, 'Yoğun bitter çikolatalı çıtır gofret.'),
            ('8690504040030', "Lay's Klasik Patates Cipsi Süper Boy", 'atistirmaliklar', 42.0, 'Paket', 55, '#FACC15', '#DC2626', False, None, "Özenle seçilmiş patateslerden incecik çıtır Lay's."),
            ('8690504040047', 'Tadım Karışık Kuruyemiş Klasik 180 g', 'atistirmaliklar', 115.0, 'Paket', 35, '#991B1B', '#FEF08A', True, None, 'Kavrulmuş fındık, badem, yer fıstığı ve kuru üzüm.'),
            ('8690504040054', "Eti Burçak Tam Buğdaylı Bisküvi 3'lü", 'atistirmaliklar', 48.0, 'Paket', 50, '#D97706', '#FEF3C7', False, None, "Lif kaynağı klasik Eti Burçak 3'lü paket."),

            # İçecek Reyonu
            ('8690504050015', 'Coca-Cola Orijinal Tat 1 Litre', 'icecekler', 38.0, 'Adet', 90, '#DC2626', '#FFFFFF', True, 'Soğuk Dolap', 'Soğuk içecek dolabından 1 Litre Coca-Cola.'),
            ('8690504050022', 'Beypazarı Doğal Maden Suyu 6x200 ml', 'icecekler', 46.0, 'Paket', 75, '#15803D', '#FFFFFF', False, None, "Zengin mineralli 6'lı Beypazarı maden suyu."),
            ('8690504050039', 'Fuse Tea Şeftali Aromalı Soğuk Çay 1 L', 'icecekler', 36.5, 'Adet', 50, '#F97316', '#FEF3C7', False, None, 'Şeftali aromalı serinletici buzlu çay.'),
            ('8690504050046', 'Cappy %100 Karışık Meyve Suyu 1 Litre', 'icecekler', 52.0, 'Adet', 40, '#EA580C', '#16A34A', False, None, 'Şeker ilavesiz %100 meyve suyu.'),
            ('8690504050053', 'Uludağ Efsane Gazoz 1 Litre', 'icecekler', 35.0, 'Adet', 55, '#0D9488', '#FFFFFF', False, None, "1930'dan beri efsane Uludağ gazozu."),

            # Et ve Tavuk Reyonu
            ('2800001060012', 'Uzman Kasap Dana Kıyma 400 g', 'et-ve-tavuk', 225.0, 'Paket', 18, '#B91C1C', '#FEE2E2', True, 'Günlük Taze', '%100 yerli besi orta yağlı dana kıyma.'),
            ('2800001060029', 'Dana Kuşbaşı 400 g', 'et-ve-tavuk', 245.0, 'Paket', 15, '#991B1B', '#FECACA', False, None, 'Yumuşak sinirsiz yemeklik dana kuşbaşı.'),
            ('2800001060036', 'Banvit Piliç Göğüs Bonfile', 'et-ve-tavuk', 168.0, 'Kg', 25, '#F59E0B', '#FFFFFF', False, None, 'Taze derisiz piliç bonfile.'),
            ('2800001060043', 'Kasap Köfte Izgaralık 400 g', 'et-ve-tavuk', 230.0, 'Paket', 20, '#7F1D1D', '#FDE047', False, None, 'Özel baharat harmanlı ızgaralık kasap köfte.'),

            # Şarküteri Reyonu
            ('8690504070013', 'Tahildaroğlu Клаsik Ezine Beyaz Peynir 600 g', 'sarkuteri', 249.0, 'Paket', 28, '#FBBF24', '#1E293B', True, 'Yöresel Lezzet', 'Çanakkale Ezine yöresi olgunlaştırılmış tam yağlı beyaz peynir.'),
            ('8690504070020', 'Cumhuriyet Kangal Fermente Sucuk 250 g', 'sarkuteri', 210.0, 'Paket', 24, '#991B1B', '#FEF08A', False, None, '%100 dana etinden geleneksel fermente sucuk.'),
            ('8690504070037', 'Marmarabirlik Kuru Sele Siyah Zeytin 400 g', 'sarkuteri', 138.0, 'Adet', 35, '#1E293B', '#F59E0B', False, None, 'İri taneli az tuzlu Gemlik kuru sele zeytin.'),
            ('8690504070044', "Gezen Tavuk Organik Yumurta 15'li (L Boy)", 'sarkuteri', 92.0, 'Paket', 40, '#D97706', '#FEF3C7', False, None, "Günlük taze büyük boy 15'li yumurta."),

            # Temizlik ve Kişisel Bakım Reyonu
            ('8690504080012', 'Omo Active Fresh Toz Çamaşır Deterjanı 4.5 Kg', 'temizlik-urunleri', 265.0, 'Paket', 20, '#1D4ED8', '#EF4444', False, None, 'Zorlu lekelerde etkili 30 yıkama Omo toz deterjan.'),
            ('8690504080029', 'Fairy Limonlu Sıvı Bulaşık Deterjanı 1500 ml', 'temizlik-urunleri', 118.0, 'Adet', 35, '#22C55E', '#FACC15', False, None, '%100 yağda bile etkili limon kokulu Fairy.'),
            ('8690504080036', "Selpak Dev Rulo Kağıt Havlu 8'li", 'temizlik-urunleri', 145.0, 'Paket', 30, '#38BDF8', '#FFFFFF', True, None, 'Süper emici 3 katlı Selpak kağıt havlu.'),
            ('8690504090011', 'Elidor Güçlü ve Parlak Şampuan 400 ml', 'kisisel-bakim', 109.0, 'Adet', 28, '#EC4899', '#FFFFFF', False, None, 'Vitamin kompleksli günlük bakım şampuanı.'),
            ('8690504090028', 'Colgate Üçlü Etki Diş Macunu 100 ml', 'kisisel-bakim', 69.0, 'Adet', 45, '#EF4444', '#3B82F6', False, None, 'Çürüklere karşı koruma, beyazlık ve ferah nefes.'),
        ]

        for (
            barcode,
            name,
            cat_slug,
            price,
            unit,
            stock,
            primary_color,
            secondary_color,
            is_featured,
            badge,
            desc,
        ) in raw_products:
            db.add(
                Product(
                    barcode=barcode,
                    name=name,
                    slug=f"{slugify_tr(name)}-{barcode[-4:]}",
                    category_id=cat_map[cat_slug],
                    description=desc,
                    price=price,
                    unit=unit,
                    stock_quantity=stock,
                    is_stock_verified=False,
                    is_sample_data=True,
                    is_active=True,
                    is_featured=is_featured,
                    campaign_badge=badge,
                    primary_color=primary_color,
                    secondary_color=secondary_color,
                )
            )
        db.commit()

    # 5. Seed Sample Orders for Admin Panel Demonstration
    if db.query(Order).count() == 0:
        p1 = db.query(Product).filter(Product.barcode == "8690555010018").first()
        p2 = db.query(Product).filter(Product.barcode == "8690504030017").first()
        p3 = db.query(Product).filter(Product.barcode == "8690504070013").first()

        if p1 and p2 and p3:
            sample_order_1 = Order(
                order_number="CM2-20261121-1001",
                idempotency_key="seed-order-1001",
                customer_name="Ege Yılmaz (Örnek Sipariş)",
                customer_phone="0532 555 01 01",
                customer_email="ege.yilmaz@example.com",
                order_note="Akşam 18:30 gibi mağazadan geçerken teslim alacağım.",
                delivery_type="MAGAZADAN_TESLIM",
                payment_method="MAGAZADA_ODEME",
                status="HAZIR",
                subtotal_amount=round(p1.price * 2 + p3.price, 2),
                total_amount=round(p1.price * 2 + p3.price, 2),
            )
            db.add(sample_order_1)
            db.flush()

            db.add_all(
                [
                    OrderItem(
                        order_id=sample_order_1.id,
                        product_id=p1.id,
                        barcode_snapshot=p1.barcode,
                        product_name_snapshot=p1.name,
                        unit_price_snapshot=p1.price,
                        unit_snapshot=p1.unit,
                        quantity=2,
                        line_total=round(p1.price * 2, 2),
                    ),
                    OrderItem(
                        order_id=sample_order_1.id,
                        product_id=p3.id,
                        barcode_snapshot=p3.barcode,
                        product_name_snapshot=p3.name,
                        unit_price_snapshot=p3.price,
                        unit_snapshot=p3.unit,
                        quantity=1,
                        line_total=round(p3.price, 2),
                    ),
                    OrderStatusLog(
                        order_id=sample_order_1.id,
                        previous_status=None,
                        new_status="YENI_SIPARIS",
                        changed_by_username="sistem",
                        note="Dijital katalog üzerinden sipariş oluşturuldu.",
                    ),
                    OrderStatusLog(
                        order_id=sample_order_1.id,
                        previous_status="YENI_SIPARIS",
                        new_status="ONAYLANDI",
                        changed_by_username="personel",
                        note="Mağaza personeli siparişi onayladı.",
                    ),
                    OrderStatusLog(
                        order_id=sample_order_1.id,
                        previous_status="ONAYLANDI",
                        new_status="HAZIR",
                        changed_by_username="personel",
                        note="Ürünler kasada poşetlendi, teslimata hazır.",
                    ),
                ]
            )

            sample_order_2 = Order(
                order_number="CM2-20261121-1002",
                idempotency_key="seed-order-1002",
                customer_name="Zeynep Kaya (Örnek Sipariş)",
                customer_phone="0544 555 02 02",
                customer_email=None,
                order_note="Zeytinyağı cam şişe olduğu için kutuya koyabilirseniz sevinirim.",
                delivery_type="MAGAZADAN_TESLIM",
                payment_method="MAGAZADA_ODEME",
                status="YENI_SIPARIS",
                subtotal_amount=round(p2.price, 2),
                total_amount=round(p2.price, 2),
            )
            db.add(sample_order_2)
            db.flush()

            db.add_all(
                [
                    OrderItem(
                        order_id=sample_order_2.id,
                        product_id=p2.id,
                        barcode_snapshot=p2.barcode,
                        product_name_snapshot=p2.name,
                        unit_price_snapshot=p2.price,
                        unit_snapshot=p2.unit,
                        quantity=1,
                        line_total=round(p2.price, 2),
                    ),
                    OrderStatusLog(
                        order_id=sample_order_2.id,
                        previous_status=None,
                        new_status="YENI_SIPARIS",
                        changed_by_username="sistem",
                        note="Sipariş oluşturuldu, mağaza onayı bekleniyor.",
                    ),
                ]
            )
            db.commit()

    # 6. Metadata
    if not db.query(SystemMetadata).filter(SystemMetadata.key == "store_notice").first():
        db.add(
            SystemMetadata(
                key="store_notice",
                value="Çeşme Market 2 Dijital Mağaza: Online sipariş verin, sıra beklemeden mağazamızdan teslim alın ve ödemenizi teslimatta yapın.",
            )
        )
        db.commit()
