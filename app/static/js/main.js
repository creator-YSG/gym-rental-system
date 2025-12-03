/**
 * 운동복 대여 시스템 - 키오스크 JavaScript (금액권/구독권 기반)
 */

// ========================================
// 전역 상태
// ========================================

const AppState = {
    member: null,
    products: [],
    cart: [],
    currentCategory: null,
    paymentMethods: null,
    selectedPayment: null,  // { type: 'subscription'|'voucher', id: ..., selections: [...] }
};

// ========================================
// 유틸리티 함수
// ========================================

function formatPhoneNumber(numbers) {
    if (!numbers) return '';
    const cleaned = numbers.replace(/\D/g, '');
    if (cleaned.length <= 3) return cleaned;
    if (cleaned.length <= 7) return `${cleaned.slice(0, 3)}-${cleaned.slice(3)}`;
    return `${cleaned.slice(0, 3)}-${cleaned.slice(3, 7)}-${cleaned.slice(7, 11)}`;
}

function formatPrice(amount) {
    return new Intl.NumberFormat('ko-KR').format(amount) + '원';
}

function showError(message, duration = 3000) {
    const errorEl = document.getElementById('errorMessage');
    if (!errorEl) return;
    errorEl.textContent = message;
    errorEl.classList.add('show');
    setTimeout(() => errorEl.classList.remove('show'), duration);
}

function showLoading(show = true) {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.classList.toggle('show', show);
}

async function apiRequest(url, options = {}) {
    const defaultOptions = { headers: { 'Content-Type': 'application/json' } };
    const response = await fetch(url, { ...defaultOptions, ...options });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || '요청 처리 중 오류가 발생했습니다.');
    return data;
}

// ========================================
// 로그인 페이지
// ========================================

let phoneNumbers = '';

function initLoginPage() {
    phoneNumbers = '';
    updatePhoneDisplay();
    
    document.querySelectorAll('.key-btn').forEach(btn => {
        btn.addEventListener('click', handleKeyPress);
    });
    
    const loginBtn = document.getElementById('loginBtn');
    if (loginBtn) loginBtn.addEventListener('click', handleLogin);
    
    console.log('로그인 페이지 초기화 완료');
}

function handleKeyPress(e) {
    const key = e.currentTarget.dataset.key;
    if (key === 'delete') phoneNumbers = phoneNumbers.slice(0, -1);
    else if (key === 'clear') phoneNumbers = '';
    else if (phoneNumbers.length < 11) phoneNumbers += key;
    updatePhoneDisplay();
}

function updatePhoneDisplay() {
    const display = document.getElementById('phoneDisplay');
    const loginBtn = document.getElementById('loginBtn');
    if (!display) return;
    
    if (phoneNumbers.length === 0) {
        display.innerHTML = '<span class="phone-placeholder">010-0000-0000</span>';
        display.classList.remove('has-value');
    } else {
        display.textContent = formatPhoneNumber(phoneNumbers);
        display.classList.add('has-value');
    }
    
    if (loginBtn) loginBtn.disabled = phoneNumbers.length < 10;
}

async function handleLogin() {
    if (phoneNumbers.length < 10) {
        showError('전화번호를 정확히 입력해주세요.');
        return;
    }
    
    showLoading(true);
    
    try {
        const data = await apiRequest('/api/auth/phone', {
            method: 'POST',
            body: JSON.stringify({ phone: phoneNumbers }),
        });
        
        if (data.success) {
            sessionStorage.setItem('member', JSON.stringify(data.member));
            window.location.href = '/rental';
        } else {
            showError(data.message || '로그인에 실패했습니다.');
        }
    } catch (error) {
        console.error('로그인 오류:', error);
        showError(error.message || '로그인 중 오류가 발생했습니다.');
    } finally {
        showLoading(false);
    }
}

// ========================================
// 대여 페이지 (상품 선택 + 장바구니)
// ========================================

function initRentalPage() {
    const memberData = sessionStorage.getItem('member');
    if (!memberData) {
        window.location.href = '/';
        return;
    }
    
    AppState.member = JSON.parse(memberData);
    AppState.cart = [];
    
    updateMemberDisplay();
    loadProducts();
    
    document.getElementById('logoutBtn')?.addEventListener('click', handleLogout);
    document.getElementById('checkoutBtn')?.addEventListener('click', openPaymentModal);
    document.getElementById('mypageBtn')?.addEventListener('click', openMypage);
    
    // 마이페이지 오버레이 클릭 시 닫기
    document.getElementById('mypageOverlay')?.addEventListener('click', (e) => {
        if (e.target.id === 'mypageOverlay') closeMypage();
    });
    
    console.log('대여 페이지 초기화 완료');
}

function updateMemberDisplay() {
    const nameEl = document.getElementById('memberName');
    const balanceEl = document.getElementById('memberBalance');
    
    if (nameEl && AppState.member) {
        nameEl.textContent = `${AppState.member.name}님`;
    }
    
    if (balanceEl && AppState.member) {
        // 현재 탭의 카테고리 가격 기준으로 대여 가능 횟수 계산
        const currentCategory = AppState.currentCategory;
        const productInCategory = AppState.products.find(p => p.category === currentCategory);
        const price = productInCategory?.price || 1000;
        const catName = getCategoryName(currentCategory) || '상품';
        
        let lines = [];
        
        // 구독권 정보 표시
        const subInfo = AppState.member.subscription_info;
        if (subInfo) {
            const remaining = subInfo.remaining_by_category?.[currentCategory] ?? 0;
            const daysLeft = subInfo.days_left || 0;
            lines.push(`📋 구독권: ${catName} ${remaining}회 남음 (D-${daysLeft})`);
        }
        
        // 금액권 대여 가능 횟수 표시
        const totalBalance = AppState.member.total_balance || 0;
        if (totalBalance > 0) {
            const rentableCount = Math.floor(totalBalance / price);
            lines.push(`💳 금액권: ${catName} ${rentableCount}회 가능`);
        }
        
        if (lines.length === 0) {
            lines.push('이용권 없음');
        }
        
        balanceEl.innerHTML = lines.join('<br>');
    }
}

async function loadProducts() {
    try {
        const data = await apiRequest('/api/products');
        AppState.products = data.products || [];
        
        renderCategoryTabs();
        
        if (AppState.products.length > 0) {
            const categories = [...new Set(AppState.products.map(p => p.category))];
            if (categories.length > 0) selectCategory(categories[0]);
        }
    } catch (error) {
        console.error('상품 로드 오류:', error);
        showError('상품 목록을 불러오는데 실패했습니다.');
    }
}

function renderCategoryTabs() {
    const tabsContainer = document.getElementById('categoryTabs');
    if (!tabsContainer) return;
    
    const categoryNames = {
        'top': '상의',
        'pants': '하의',
        'towel': '수건',
        'sweat_towel': '땀수건',
        'other': '기타',
    };
    
    const categories = [...new Set(AppState.products.map(p => p.category))];
    
    tabsContainer.innerHTML = categories.map(cat => `
        <button class="category-tab" data-category="${cat}">
            ${categoryNames[cat] || cat}
        </button>
    `).join('');
    
    tabsContainer.querySelectorAll('.category-tab').forEach(tab => {
        tab.addEventListener('click', () => selectCategory(tab.dataset.category));
    });
}

function selectCategory(category) {
    AppState.currentCategory = category;
    document.querySelectorAll('.category-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.category === category);
    });
    renderProducts();
    updateMemberDisplay();  // 탭 전환 시 대여 가능 횟수 업데이트
}

function renderProducts() {
    const grid = document.getElementById('productsGrid');
    if (!grid) return;
    
    const filtered = AppState.products.filter(p => p.category === AppState.currentCategory);
    
    grid.innerHTML = filtered.map(product => {
        const inCart = AppState.cart.some(item => item.product_id === product.product_id);
        const cartItem = AppState.cart.find(item => item.product_id === product.product_id);
        const isDisabled = !product.online || product.stock <= 0;
        
        let statusText = '';
        if (!product.connected) statusText = '<span class="product-offline">연결 안됨</span>';
        else if (!product.online) statusText = '<span class="product-offline">오프라인</span>';
        
        return `
            <div class="product-card ${isDisabled ? 'disabled' : ''} ${inCart ? 'in-cart' : ''}"
                 data-product-id="${product.product_id}"
                 ${isDisabled ? '' : 'onclick="openQuantityModal(\'' + product.product_id + '\')"'}>
                <div class="product-size">${product.size || '-'}</div>
                <div class="product-name">${product.name}</div>
                <div class="product-price">${formatPrice(product.price || 1000)}</div>
                <div class="product-stock ${product.stock <= 0 ? 'empty' : ''}">
                    ${product.stock > 0 ? `재고 ${product.stock}개` : '재고 없음'}
                </div>
                ${statusText}
                ${inCart ? `<div class="product-in-cart-badge">${cartItem.quantity}개 선택</div>` : ''}
            </div>
        `;
    }).join('');
}

// 수량 선택 모달
let selectedProduct = null;
let selectedQuantity = 1;

function openQuantityModal(productId) {
    selectedProduct = AppState.products.find(p => p.product_id === productId);
    if (!selectedProduct) return;
    
    const existingItem = AppState.cart.find(item => item.product_id === productId);
    selectedQuantity = existingItem ? existingItem.quantity : 1;
    
    updateQuantityDisplay();
    
    const modal = document.getElementById('quantityModal');
    const titleEl = document.getElementById('modalProductName');
    const priceEl = document.getElementById('modalProductPrice');
    
    if (titleEl) titleEl.textContent = `${selectedProduct.name} (${selectedProduct.size})`;
    if (priceEl) priceEl.textContent = formatPrice(selectedProduct.price || 1000);
    if (modal) modal.classList.add('show');
}

function closeQuantityModal() {
    const modal = document.getElementById('quantityModal');
    if (modal) modal.classList.remove('show');
    selectedProduct = null;
}

function changeQuantity(delta) {
    if (!selectedProduct) return;
    const newQty = selectedQuantity + delta;
    if (newQty >= 1 && newQty <= selectedProduct.stock) {
        selectedQuantity = newQty;
        updateQuantityDisplay();
    }
}

function updateQuantityDisplay() {
    const valueEl = document.getElementById('qtyValue');
    const minusBtn = document.getElementById('qtyMinus');
    const plusBtn = document.getElementById('qtyPlus');
    
    if (valueEl) valueEl.textContent = selectedQuantity;
    if (minusBtn) minusBtn.disabled = selectedQuantity <= 1;
    if (plusBtn && selectedProduct) plusBtn.disabled = selectedQuantity >= selectedProduct.stock;
}

function confirmQuantity() {
    if (!selectedProduct) return;
    
    const existingIndex = AppState.cart.findIndex(item => item.product_id === selectedProduct.product_id);
    
    if (existingIndex >= 0) {
        AppState.cart[existingIndex].quantity = selectedQuantity;
    } else {
        AppState.cart.push({
            product_id: selectedProduct.product_id,
            name: selectedProduct.name,
            size: selectedProduct.size,
            category: selectedProduct.category,
            price: selectedProduct.price || 1000,
            quantity: selectedQuantity,
            device_uuid: selectedProduct.device_uuid,
        });
    }
    
    closeQuantityModal();
    renderProducts();
    renderCart();
}

function renderCart() {
    const cartItemsEl = document.getElementById('cartItems');
    const cartTotalEl = document.getElementById('cartTotal');
    const checkoutBtn = document.getElementById('checkoutBtn');
    
    if (!cartItemsEl) return;
    
    if (AppState.cart.length === 0) {
        cartItemsEl.innerHTML = '<div class="cart-empty">상품을 선택해주세요</div>';
    } else {
        cartItemsEl.innerHTML = AppState.cart.map((item, idx) => {
            const paymentLabel = getPaymentLabel(item.payment);
            return `
                <div class="cart-item" onclick="openItemPaymentModal(${idx})">
                    <div class="cart-item-info">
                        <span class="cart-item-name">${item.name} (${item.size})</span>
                        <span class="cart-item-qty">${item.quantity}개 × ${formatPrice(item.price)}</span>
                        <span class="cart-item-payment ${item.payment ? 'set' : 'unset'}">${paymentLabel}</span>
                    </div>
                    <button class="cart-item-remove" onclick="event.stopPropagation(); removeFromCart('${item.product_id}')">×</button>
                </div>
            `;
        }).join('');
    }
    
    const totalAmount = AppState.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    
    if (cartTotalEl) cartTotalEl.innerHTML = `총 <strong>${formatPrice(totalAmount)}</strong>`;
    if (checkoutBtn) checkoutBtn.disabled = AppState.cart.length === 0;
}

function getPaymentLabel(payment) {
    if (!payment) return '결제수단 선택';
    if (payment.type === 'subscription') return '구독권';
    if (payment.type === 'voucher') return `금액권`;
    return '결제수단 선택';
}

function removeFromCart(productId) {
    AppState.cart = AppState.cart.filter(item => item.product_id !== productId);
    renderProducts();
    renderCart();
}

// ========================================
// 결제 수단 선택 모달
// ========================================

async function openPaymentModal() {
    if (AppState.cart.length === 0) {
        showError('선택된 상품이 없습니다.');
        return;
    }
    
    showLoading(true);
    
    try {
        // 모든 카테고리의 잔여 횟수를 가져옴 (category 파라미터 없이)
        const data = await apiRequest(`/api/payment-methods/${AppState.member.member_id}`);
        AppState.paymentMethods = data;
        AppState.selectedPayment = null;
        
        renderPaymentOptions();
        updatePaymentTotal();
        
        document.getElementById('paymentModal')?.classList.add('show');
    } catch (error) {
        console.error('결제 수단 로드 오류:', error);
        showError('결제 수단을 불러오는데 실패했습니다.');
    } finally {
        showLoading(false);
    }
}

function closePaymentModal() {
    document.getElementById('paymentModal')?.classList.remove('show');
}

function renderPaymentOptions() {
    const subSection = document.getElementById('subscriptionSection');
    const subOptions = document.getElementById('subscriptionOptions');
    const vchSection = document.getElementById('voucherSection');
    const vchOptions = document.getElementById('voucherOptions');
    
    const { subscriptions, vouchers } = AppState.paymentMethods || {};
    
    // 장바구니 카테고리별 필요 수량 계산
    const neededByCategory = {};
    AppState.cart.forEach(item => {
        neededByCategory[item.category] = (neededByCategory[item.category] || 0) + item.quantity;
    });
    
    // 구독권 렌더링
    if (subscriptions && subscriptions.length > 0) {
        subSection.style.display = 'block';
        subOptions.innerHTML = subscriptions.map(sub => {
            const remainingByCat = sub.remaining_by_category || {};
            
            // 모든 카테고리에 대해 잔여 횟수 확인
            let isAvailable = true;
            let remainingInfo = [];
            for (const [cat, needed] of Object.entries(neededByCategory)) {
                const remaining = remainingByCat[cat] ?? 0;
                if (remaining < needed) {
                    isAvailable = false;
                }
                const catName = getCategoryName(cat);
                remainingInfo.push(`${catName} ${remaining}회`);
            }
            
            return `
                <div class="payment-option ${isAvailable ? '' : 'disabled'}" 
                     data-type="subscription" data-id="${sub.subscription_id}"
                     onclick="${isAvailable ? `selectPayment('subscription', ${sub.subscription_id})` : ''}">
                    <div class="payment-option-name">${sub.product_name}</div>
                    <div class="payment-option-info">~${sub.valid_until?.split('T')[0] || ''}</div>
                    <div class="payment-option-value">오늘 남은: ${remainingInfo.join(' / ')}</div>
                </div>
            `;
        }).join('');
    } else {
        subSection.style.display = 'none';
    }
    
    // 금액권 렌더링
    if (vouchers && vouchers.length > 0) {
        vchSection.style.display = 'block';
        const totalAmount = AppState.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
        const canSplit = vouchers.length >= 2;
        
        let vchHtml = vouchers.map(v => {
            const isSelected = AppState.selectedPayment?.selections?.some(s => s.voucher_id === v.voucher_id);
            const selectedAmount = AppState.selectedPayment?.selections?.find(s => s.voucher_id === v.voucher_id)?.amount || 0;
            
            return `
                <div class="payment-option ${isSelected ? 'selected' : ''}" 
                     data-type="voucher" data-id="${v.voucher_id}"
                     onclick="selectVoucher(${v.voucher_id})">
                    <div class="payment-option-name">${v.product_name}</div>
                    <div class="payment-option-info">~${v.valid_until?.split('T')[0] || ''}</div>
                    <div class="payment-option-value">잔액: ${formatPrice(v.remaining_amount)}</div>
                    ${isSelected && canSplit ? `
                        <div class="voucher-split-input" onclick="event.stopPropagation()">
                            <label>사용 금액:</label>
                            <input type="number" value="${selectedAmount}" min="0" max="${v.remaining_amount}"
                                   onchange="updateVoucherAmount(${v.voucher_id}, this.value)" />원
                        </div>
                    ` : ''}
                </div>
            `;
        }).join('');
        
        vchOptions.innerHTML = vchHtml;
    } else {
        vchSection.style.display = 'none';
    }
}

function selectPayment(type, id) {
    // 구독권 선택 (전체 결제)
    AppState.selectedPayment = { type, id, selections: [] };
    
    document.querySelectorAll('.payment-option').forEach(opt => {
        opt.classList.remove('selected');
    });
    
    const selected = document.querySelector(`.payment-option[data-type="${type}"][data-id="${id}"]`);
    if (selected) selected.classList.add('selected');
    
    updatePaymentTotal();
}

// ========================================
// 개별 상품별 결제 수단 선택
// ========================================

let currentEditingCartIndex = -1;

async function openItemPaymentModal(cartIndex) {
    currentEditingCartIndex = cartIndex;
    const item = AppState.cart[cartIndex];
    if (!item) return;
    
    // 결제 수단 로드 (아직 로드 안 됐으면)
    if (!AppState.paymentMethods) {
        try {
            const data = await apiRequest(`/api/payment-methods/${AppState.member.member_id}`);
            AppState.paymentMethods = data;
        } catch (e) {
            showError('결제 수단을 불러오는데 실패했습니다.');
            return;
        }
    }
    
    const modal = document.getElementById('itemPaymentModal');
    if (!modal) return;
    
    const itemInfoEl = document.getElementById('itemPaymentItemInfo');
    const optionsEl = document.getElementById('itemPaymentOptions');
    
    if (itemInfoEl) {
        itemInfoEl.innerHTML = `<strong>${item.name} (${item.size})</strong> - ${item.quantity}개 × ${formatPrice(item.price)}`;
    }
    
    const { subscriptions, vouchers } = AppState.paymentMethods || {};
    let optionsHtml = '';
    
    // 구독권 옵션
    if (subscriptions && subscriptions.length > 0) {
        const sub = subscriptions[0];
        const remaining = sub.remaining_by_category?.[item.category] ?? 0;
        const isAvailable = remaining >= item.quantity;
        
        optionsHtml += `
            <div class="item-payment-option ${isAvailable ? '' : 'disabled'}" 
                 data-type="subscription" data-id="${sub.subscription_id}"
                 onclick="${isAvailable ? `selectItemPayment('subscription', ${sub.subscription_id})` : ''}">
                <span class="option-name">구독권</span>
                <span class="option-info">${getCategoryName(item.category)} 남은 횟수: ${remaining}회</span>
            </div>
        `;
    }
    
    // 금액권 옵션
    if (vouchers && vouchers.length > 0) {
        vouchers.forEach(v => {
            const itemTotal = item.price * item.quantity;
            const isAvailable = v.remaining_amount >= itemTotal;
            optionsHtml += `
                <div class="item-payment-option ${isAvailable ? '' : 'partial'}" 
                     data-type="voucher" data-id="${v.voucher_id}"
                     onclick="selectItemPayment('voucher', ${v.voucher_id})">
                    <span class="option-name">${v.product_name}</span>
                    <span class="option-info">잔액: ${formatPrice(v.remaining_amount)}</span>
                </div>
            `;
        });
    }
    
    if (optionsEl) optionsEl.innerHTML = optionsHtml;
    
    modal.classList.add('show');
}

function closeItemPaymentModal() {
    document.getElementById('itemPaymentModal')?.classList.remove('show');
    currentEditingCartIndex = -1;
}

function selectItemPayment(type, id) {
    if (currentEditingCartIndex < 0) return;
    
    AppState.cart[currentEditingCartIndex].payment = { type, id };
    renderCart();
    closeItemPaymentModal();
}

function selectVoucher(voucherId) {
    const voucher = AppState.paymentMethods.vouchers.find(v => v.voucher_id === voucherId);
    if (!voucher) return;
    
    const totalAmount = AppState.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    
    // 금액권 선택/토글
    if (!AppState.selectedPayment || AppState.selectedPayment.type !== 'voucher') {
        AppState.selectedPayment = { type: 'voucher', selections: [] };
    }
    
    const existingIdx = AppState.selectedPayment.selections.findIndex(s => s.voucher_id === voucherId);
    
    if (existingIdx >= 0) {
        // 이미 선택됨 -> 해제
        AppState.selectedPayment.selections.splice(existingIdx, 1);
    } else {
        // 새로 추가
        const currentTotal = AppState.selectedPayment.selections.reduce((s, x) => s + x.amount, 0);
        const remaining = totalAmount - currentTotal;
        const useAmount = Math.min(voucher.remaining_amount, remaining);
        
        if (useAmount > 0) {
            AppState.selectedPayment.selections.push({
                voucher_id: voucherId,
                amount: useAmount,
            });
        }
    }
    
    // 구독권 선택 해제
    document.querySelectorAll('.payment-option[data-type="subscription"]').forEach(opt => {
        opt.classList.remove('selected');
    });
    
    // 금액권 쪼개기 UI가 있으면 전체 다시 렌더링
    renderPaymentOptions();
    updatePaymentTotal();
}

function updateVoucherAmount(voucherId, value) {
    if (!AppState.selectedPayment || AppState.selectedPayment.type !== 'voucher') return;
    
    const amount = parseInt(value) || 0;
    const voucher = AppState.paymentMethods.vouchers.find(v => v.voucher_id === voucherId);
    if (!voucher) return;
    
    // 금액 범위 제한
    const validAmount = Math.max(0, Math.min(amount, voucher.remaining_amount));
    
    const selection = AppState.selectedPayment.selections.find(s => s.voucher_id === voucherId);
    if (selection) {
        selection.amount = validAmount;
    }
    
    updatePaymentTotal();
}

function updatePaymentTotal() {
    const totalAmountEl = document.getElementById('paymentTotalAmount');
    const selectedAmountEl = document.getElementById('paymentSelectedAmount');
    const confirmBtn = document.getElementById('confirmPaymentBtn');
    
    const totalAmount = AppState.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    
    if (totalAmountEl) totalAmountEl.textContent = formatPrice(totalAmount);
    
    let selectedAmount = 0;
    let canConfirm = false;
    
    if (AppState.selectedPayment) {
        if (AppState.selectedPayment.type === 'subscription') {
            selectedAmount = totalAmount;  // 구독권은 전액 커버
            canConfirm = true;
        } else if (AppState.selectedPayment.type === 'voucher') {
            selectedAmount = AppState.selectedPayment.selections.reduce((s, x) => s + x.amount, 0);
            canConfirm = selectedAmount >= totalAmount;
        }
    }
    
    if (selectedAmountEl) selectedAmountEl.textContent = formatPrice(selectedAmount);
    if (confirmBtn) confirmBtn.disabled = !canConfirm;
}

async function confirmPayment() {
    // 개별 상품별 결제 수단이 설정되어 있는지 확인
    const hasItemPayments = AppState.cart.some(item => item.payment);
    
    if (!hasItemPayments && !AppState.selectedPayment) {
        showError('결제 수단을 선택해주세요.');
        return;
    }
    
    showLoading(true);
    closePaymentModal();
    
    try {
        let result;
        
        // 개별 상품별 결제 수단이 설정된 경우
        if (hasItemPayments) {
            result = await processItemPayments();
        } else if (AppState.selectedPayment.type === 'subscription') {
            result = await apiRequest('/api/rental/subscription', {
                method: 'POST',
                body: JSON.stringify({
                    member_id: AppState.member.member_id,
                    subscription_id: AppState.selectedPayment.id,
                    items: AppState.cart.map(item => ({
                        product_id: item.product_id,
                        quantity: item.quantity,
                        device_uuid: item.device_uuid,
                    })),
                }),
            });
        } else {
            result = await apiRequest('/api/rental/voucher', {
                method: 'POST',
                body: JSON.stringify({
                    member_id: AppState.member.member_id,
                    items: AppState.cart.map(item => ({
                        product_id: item.product_id,
                        quantity: item.quantity,
                        device_uuid: item.device_uuid,
                    })),
                    voucher_selections: AppState.selectedPayment.selections,
                }),
            });
        }
        
        if (result.success) {
            const totalAmount = AppState.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
            
            // 결제 수단별 상세 정보 생성
            const itemsWithPayment = AppState.cart.map(item => ({
                ...item,
                payment_type: item.payment?.type || AppState.selectedPayment?.type,
            }));
            
            sessionStorage.setItem('rentalResult', JSON.stringify({
                items: itemsWithPayment,
                payment_type: result.payment_type || 'mixed',
                total_amount: result.total_amount || totalAmount,
                voucher_details: result.voucher_details || AppState.selectedPayment?.selections?.map(s => {
                    const v = AppState.paymentMethods?.vouchers?.find(v => v.voucher_id === s.voucher_id);
                    return { name: v?.product_name, amount: s.amount };
                }),
            }));
            window.location.href = '/complete';
        } else {
            showError(result.message || '대여 처리에 실패했습니다.');
        }
    } catch (error) {
        console.error('대여 오류:', error);
        showError(error.message || '대여 처리 중 오류가 발생했습니다.');
    } finally {
        showLoading(false);
    }
}

// 개별 상품별 결제 처리
async function processItemPayments() {
    // 구독권 아이템과 금액권 아이템 분리
    const subscriptionItems = AppState.cart.filter(item => item.payment?.type === 'subscription');
    const voucherItems = AppState.cart.filter(item => item.payment?.type === 'voucher');
    
    let allResults = { success: true, payment_type: 'mixed', total_amount: 0 };
    
    // 구독권 결제 처리
    if (subscriptionItems.length > 0) {
        const subId = subscriptionItems[0].payment.id;
        const result = await apiRequest('/api/rental/subscription', {
            method: 'POST',
            body: JSON.stringify({
                member_id: AppState.member.member_id,
                subscription_id: subId,
                items: subscriptionItems.map(item => ({
                    product_id: item.product_id,
                    quantity: item.quantity,
                    device_uuid: item.device_uuid,
                })),
            }),
        });
        
        if (!result.success) {
            return result;
        }
        allResults.total_amount += result.total_amount || 0;
    }
    
    // 금액권 결제 처리
    if (voucherItems.length > 0) {
        // 금액권별로 그룹화
        const voucherGroups = {};
        voucherItems.forEach(item => {
            const vid = item.payment.id;
            if (!voucherGroups[vid]) voucherGroups[vid] = [];
            voucherGroups[vid].push(item);
        });
        
        // 각 금액권에서 차감할 금액 계산
        const selections = Object.entries(voucherGroups).map(([vid, items]) => ({
            voucher_id: parseInt(vid),
            amount: items.reduce((sum, item) => sum + (item.price * item.quantity), 0),
        }));
        
        const result = await apiRequest('/api/rental/voucher', {
            method: 'POST',
            body: JSON.stringify({
                member_id: AppState.member.member_id,
                items: voucherItems.map(item => ({
                    product_id: item.product_id,
                    quantity: item.quantity,
                    device_uuid: item.device_uuid,
                })),
                voucher_selections: selections,
            }),
        });
        
        if (!result.success) {
            return result;
        }
        allResults.total_amount += result.total_amount || 0;
        allResults.voucher_details = result.voucher_details;
    }
    
    return allResults;
}

// ========================================
// 마이페이지 슬라이드 패널
// ========================================

async function openMypage() {
    const overlay = document.getElementById('mypageOverlay');
    const content = document.getElementById('mypageContent');
    
    if (!overlay || !content) return;
    
    overlay.classList.add('show');
    content.innerHTML = '<div style="text-align:center;padding:40px;color:#888;">로딩 중...</div>';
    
    try {
        const data = await apiRequest(`/api/member/${AppState.member.member_id}/cards`);
        renderMypageContent(data);
    } catch (error) {
        console.error('마이페이지 로드 오류:', error);
        content.innerHTML = '<div style="text-align:center;padding:40px;color:#f44336;">로드 실패</div>';
    }
}

function closeMypage() {
    document.getElementById('mypageOverlay')?.classList.remove('show');
}

function renderMypageContent(data) {
    const content = document.getElementById('mypageContent');
    if (!content) return;
    
    const { subscriptions, vouchers } = data;
    
    let html = '';
    
    // 구독권 섹션
    html += '<div class="mypage-section">';
    html += '<div class="mypage-section-title">📋 구독권</div>';
    
    if (subscriptions && subscriptions.length > 0) {
        html += subscriptions.map(sub => {
            const status = sub.status;
            const statusText = status === 'active' ? '✅ 사용 중' : '❌ 만료';
            const limits = sub.daily_limits || {};
            const limitsText = Object.entries(limits)
                .map(([k, v]) => `${getCategoryName(k)} ${v}`)
                .join(' / ');
            
            return `
                <div class="card-item ${status}">
                    <div class="card-status ${status}">${statusText}</div>
                    <div class="card-name">${sub.product_name}</div>
                    <div class="card-info">
                        ${sub.valid_from?.split('T')[0] || ''} ~ ${sub.valid_until?.split('T')[0] || ''}<br>
                        ${limitsText}
                    </div>
                </div>
            `;
        }).join('');
    } else {
        html += '<div style="color:#666;padding:10px;">구독권이 없습니다.</div>';
    }
    html += '</div>';
    
    // 금액권 섹션
    html += '<div class="mypage-section">';
    html += '<div class="mypage-section-title">💳 금액권</div>';
    
    if (vouchers && vouchers.length > 0) {
        html += vouchers.map(v => {
            const status = v.status;
            let statusText = '';
            if (status === 'active') statusText = '✅ 사용 중';
            else if (status === 'pending') statusText = '⏳ 미활성 (보너스)';
            else if (status === 'exhausted') statusText = '⬚ 소진';
            else if (status === 'expired') statusText = '❌ 만료';
            
            return `
                <div class="card-item ${status}">
                    <div class="card-status ${status}">${statusText}</div>
                    <div class="card-name">${v.product_name}</div>
                    <div class="card-info">
                        ${v.valid_until ? `~${v.valid_until.split('T')[0]}` : '(활성화 시 유효기간 시작)'}
                    </div>
                    <div class="card-balance">잔액: ${formatPrice(v.remaining_amount)}</div>
                </div>
            `;
        }).join('');
    } else {
        html += '<div style="color:#666;padding:10px;">금액권이 없습니다.</div>';
    }
    html += '</div>';
    
    content.innerHTML = html;
}

function getCategoryName(category) {
    const names = { 'top': '상의', 'pants': '하의', 'towel': '수건', 'sweat_towel': '땀수건', 'other': '기타' };
    return names[category] || category;
}

function handleLogout() {
    sessionStorage.removeItem('member');
    window.location.href = '/';
}

// ========================================
// 완료 페이지
// ========================================

function initCompletePage() {
    const resultData = sessionStorage.getItem('rentalResult');
    
    if (!resultData) {
        window.location.href = '/';
        return;
    }
    
    const result = JSON.parse(resultData);
    renderCompleteResult(result);
    
    sessionStorage.removeItem('member');
    sessionStorage.removeItem('rentalResult');
    
    startCountdown(5);
}

function renderCompleteResult(result) {
    // 날짜 표시
    const dateEl = document.getElementById('receiptDate');
    if (dateEl) {
        const now = new Date();
        dateEl.textContent = now.toLocaleString('ko-KR');
    }
    
    // 상품 목록
    const itemsEl = document.getElementById('receiptItems');
    if (itemsEl) {
        itemsEl.innerHTML = result.items.map(item => {
            const paymentText = item.payment_type === 'subscription' ? '구독권' : 
                               item.payment_type === 'voucher' ? '금액권' : '';
            return `
                <div class="receipt-item">
                    <div class="receipt-item-left">
                        <div class="receipt-item-name">${item.name}</div>
                        <div class="receipt-item-detail">사이즈: ${item.size || '-'}</div>
                        ${paymentText ? `<div class="receipt-item-payment">${paymentText} 결제</div>` : ''}
                    </div>
                    <div class="receipt-item-right">
                        <div class="receipt-item-qty">${item.quantity}개</div>
                        <div class="receipt-item-price">${formatPrice(item.price * item.quantity)}</div>
                    </div>
                </div>
            `;
        }).join('');
    }
    
    // 결제 정보
    const totalEl = document.getElementById('receiptTotal');
    if (totalEl) {
        const paymentTypeText = result.payment_type === 'subscription' ? '구독권' : '금액권';
        let detailHtml = '';
        
        // 금액권 쪼개기 상세
        if (result.voucher_details && result.voucher_details.length > 0) {
            detailHtml = result.voucher_details.map(v => `
                <div class="receipt-total-row">
                    <span class="receipt-total-label">${v.name || '금액권'}</span>
                    <span class="receipt-total-value">-${formatPrice(v.amount)}</span>
                </div>
            `).join('');
        }
        
        totalEl.innerHTML = `
            <div class="receipt-total-row">
                <span class="receipt-total-label">결제 방식</span>
                <span class="receipt-total-value">${paymentTypeText}</span>
            </div>
            ${detailHtml}
            <div class="receipt-total-row">
                <span class="receipt-total-label">총 결제 금액</span>
                <span class="receipt-total-value highlight">${formatPrice(result.total_amount)}</span>
            </div>
        `;
    }
}

function startCountdown(seconds) {
    const countdownEl = document.getElementById('countdown');
    let remaining = seconds;
    
    function updateCountdown() {
        if (countdownEl) {
            countdownEl.innerHTML = `<strong>${remaining}</strong>초 후 처음 화면으로 이동합니다`;
        }
        
        if (remaining <= 0) {
            window.location.href = '/';
        } else {
            remaining--;
            setTimeout(updateCountdown, 1000);
        }
    }
    
    updateCountdown();
}

console.log('운동복 대여 시스템 로드됨 (금액권/구독권 기반)');
