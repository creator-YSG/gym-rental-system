/**
 * 운동복 대여 시스템 - 키오스크 JavaScript (금액권/구독권 기반)
 * 개선된 결제수단 선택 UI
 */

// ========================================
// 전역 상태
// ========================================

const AppState = {
    member: null,
    products: [],
    // 장바구니: 같은 상품도 결제수단이 다르면 별도 항목으로 관리
    // { product_id, name, size, category, price, quantity, device_uuid, payment: null | { type, id, name } }
    cart: [],
    currentCategory: null,
    paymentMethods: null,
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

function getCategoryName(category) {
    const names = { 'top': '상의', 'pants': '하의', 'towel': '수건', 'sweat_towel': '땀수건', 'other': '기타' };
    return names[category] || category;
}

// 장바구니 아이템의 고유 키 생성 (상품ID + 결제수단)
function getCartItemKey(item) {
    if (!item.payment) return `${item.product_id}_unassigned`;
    return `${item.product_id}_${item.payment.type}_${item.payment.id}`;
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
    
    // NFC 이벤트 폴링 (홈 화면에서만)
    let nfcPollingInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/nfc/poll');
            const data = await response.json();
            
            if (data.has_event && data.success) {
                console.log('[NFC] 태그 감지:', data);
                clearInterval(nfcPollingInterval); // 폴링 중지
                showLoading(true);
                
                try {
                    // member_id로 로그인 API 호출
                    const loginResponse = await apiRequest('/api/auth/member_id', {
                        method: 'POST',
                        body: JSON.stringify({ member_id: data.member_id }),
                    });
                    
                    if (loginResponse.success) {
                        console.log('[NFC] 로그인 성공:', loginResponse.member);
                        sessionStorage.setItem('member', JSON.stringify(loginResponse.member));
                        window.location.href = '/rental';
                    } else {
                        showError(loginResponse.message || 'NFC 로그인에 실패했습니다.');
                        // 폴링 재시작
                        nfcPollingInterval = setInterval(arguments.callee, 500);
                    }
                } catch (error) {
                    console.error('[NFC] 로그인 오류:', error);
                    showError(error.message || 'NFC 로그인 중 오류가 발생했습니다.');
                    // 폴링 재시작
                    nfcPollingInterval = setInterval(arguments.callee, 500);
                } finally {
                    showLoading(false);
                }
            } else if (data.has_event && !data.success) {
                console.log('[NFC] 오류:', data);
                showError(data.message || '락카가 배정되어 있지 않습니다.');
            }
        } catch (error) {
            // 폴링 오류는 조용히 무시 (서버 다운 등)
            // console.error('[NFC] 폴링 오류:', error);
        }
    }, 500); // 500ms마다 폴링
    
    console.log('[NFC] 폴링 시작 (500ms 간격)');
    
    // 페이지 떠날 때 폴링 중지
    window.addEventListener('beforeunload', () => {
        clearInterval(nfcPollingInterval);
    });
    
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
    loadPaymentMethods();
    
    document.getElementById('logoutBtn')?.addEventListener('click', handleLogout);
    document.getElementById('checkoutBtn')?.addEventListener('click', handleCheckout);
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

async function loadPaymentMethods() {
    try {
        const data = await apiRequest(`/api/payment-methods/${AppState.member.member_id}`);
        AppState.paymentMethods = data;
    } catch (error) {
        console.error('결제 수단 로드 오류:', error);
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
    updateMemberDisplay();
}

function renderProducts() {
    const grid = document.getElementById('productsGrid');
    if (!grid) return;
    
    const filtered = AppState.products.filter(p => p.category === AppState.currentCategory);
    
    grid.innerHTML = filtered.map(product => {
        // 해당 상품의 장바구니 총 수량 계산
        const cartQuantity = AppState.cart
            .filter(item => item.product_id === product.product_id)
            .reduce((sum, item) => sum + item.quantity, 0);
        const inCart = cartQuantity > 0;
        const isDisabled = !product.online || product.stock <= 0;
        
        let statusText = '';
        if (!product.connected) statusText = '<span class="product-offline">연결 안됨</span>';
        else if (!product.online) statusText = '<span class="product-offline">오프라인</span>';
        
        return `
            <div class="product-card ${isDisabled ? 'disabled' : ''} ${inCart ? 'in-cart' : ''}"
                 data-product-id="${product.product_id}"
                 onclick="${isDisabled ? '' : `addToCart('${product.product_id}')`}">
                <div class="product-size">${product.size || '-'}</div>
                <div class="product-name">${product.name}</div>
                <div class="product-price">${formatPrice(product.price || 1000)}</div>
                <div class="product-stock ${product.stock <= 0 ? 'empty' : ''}">
                    ${product.stock > 0 ? `재고 ${product.stock}개` : '재고 없음'}
                </div>
                ${statusText}
                ${inCart ? `<div class="product-in-cart-badge">${cartQuantity}개 선택</div>` : ''}
            </div>
        `;
    }).join('');
}

// ========================================
// 장바구니 관리 (새로운 방식)
// ========================================

function addToCart(productId) {
    const product = AppState.products.find(p => p.product_id === productId);
    if (!product) return;
    
    // 장바구니 총 수량이 재고를 초과하는지 확인
    const currentQuantity = AppState.cart
        .filter(item => item.product_id === productId)
        .reduce((sum, item) => sum + item.quantity, 0);
    
    if (currentQuantity >= product.stock) {
        showError('재고가 부족합니다.');
        return;
    }
    
    // 미분류(payment=null) 아이템이 있으면 수량 증가, 없으면 새로 추가
    const unassignedItem = AppState.cart.find(
        item => item.product_id === productId && !item.payment
    );
    
    if (unassignedItem) {
        unassignedItem.quantity += 1;
    } else {
        AppState.cart.push({
            product_id: product.product_id,
            name: product.name,
            size: product.size,
            category: product.category,
            price: product.price || 1000,
            quantity: 1,
            device_uuid: product.device_uuid,
            payment: null,  // 미분류
        });
    }
    
    renderProducts();
    renderCart();
}

function changeCartQuantity(cartIndex, delta) {
    const item = AppState.cart[cartIndex];
    if (!item) return;
    
    const product = AppState.products.find(p => p.product_id === item.product_id);
    if (!product) return;
    
    const newQty = item.quantity + delta;
    
    // 현재 상품의 총 장바구니 수량 계산 (변경될 아이템 제외)
    const otherQuantity = AppState.cart
        .filter((it, idx) => it.product_id === item.product_id && idx !== cartIndex)
        .reduce((sum, it) => sum + it.quantity, 0);
    
    if (newQty <= 0) {
        // 수량이 0 이하면 삭제
        AppState.cart.splice(cartIndex, 1);
    } else if (otherQuantity + newQty > product.stock) {
        showError('재고가 부족합니다.');
        return;
    } else {
        item.quantity = newQty;
    }
    
    renderProducts();
    renderCart();
}

function removeCartItem(cartIndex) {
    AppState.cart.splice(cartIndex, 1);
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
        if (cartTotalEl) cartTotalEl.innerHTML = `총 <strong>0원</strong>`;
        if (checkoutBtn) checkoutBtn.disabled = true;
        return;
    }
    
    // 같은 상품끼리 합치기 (product_id + size 기준)
    const mergedCart = [];
    AppState.cart.forEach((item, idx) => {
        const existing = mergedCart.find(m => m.product_id === item.product_id && m.size === item.size);
        if (existing) {
            existing.quantity += item.quantity;
            existing.originalIndices.push(idx);
        } else {
            mergedCart.push({
                ...item,
                originalIndices: [idx]
            });
        }
    });
    
    // 카드 형태로 렌더링
    const html = `
        <div class="cart-grid">
            ${mergedCart.map((item, idx) => renderCartCard(item, idx)).join('')}
        </div>
    `;
    
    cartItemsEl.innerHTML = html;
    
    const totalAmount = AppState.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    const totalQty = AppState.cart.reduce((sum, item) => sum + item.quantity, 0);
    
    if (cartTotalEl) cartTotalEl.innerHTML = `${totalQty}개 <strong>${formatPrice(totalAmount)}</strong>`;
    if (checkoutBtn) checkoutBtn.disabled = AppState.cart.length === 0;
}

function renderCartCard(item, mergedIndex) {
    const firstIdx = item.originalIndices[0];
    
    return `
        <div class="cart-card">
            <button class="cart-card-remove" onclick="removeCartItemByProduct('${item.product_id}', '${item.size}')">×</button>
            <div class="cart-card-info">
                <div class="cart-card-name">${item.name}</div>
                <div class="cart-card-size">${item.size}</div>
            </div>
            <div class="cart-card-qty">
                <button class="cart-card-qty-btn" onclick="changeCartQuantityByProduct('${item.product_id}', '${item.size}', -1)">−</button>
                <span class="cart-card-qty-value">${item.quantity}</span>
                <button class="cart-card-qty-btn" onclick="changeCartQuantityByProduct('${item.product_id}', '${item.size}', 1)">+</button>
            </div>
            <div class="cart-card-price">${formatPrice(item.price * item.quantity)}</div>
        </div>
    `;
}

// 상품 기준으로 수량 변경
function changeCartQuantityByProduct(productId, size, delta) {
    const product = AppState.products.find(p => p.product_id === productId);
    if (!product) return;
    
    // 해당 상품의 총 수량 계산
    const currentQty = AppState.cart
        .filter(item => item.product_id === productId && item.size === size)
        .reduce((sum, item) => sum + item.quantity, 0);
    
    const newQty = currentQty + delta;
    
    if (newQty <= 0) {
        // 전부 삭제
        AppState.cart = AppState.cart.filter(item => !(item.product_id === productId && item.size === size));
    } else if (newQty > product.stock) {
        showError('재고가 부족합니다.');
        return;
    } else {
        // 첫 번째 아이템의 수량 조절
        const firstItem = AppState.cart.find(item => item.product_id === productId && item.size === size);
        if (firstItem) {
            firstItem.quantity += delta;
        }
    }
    
    renderProducts();
    renderCart();
}

// 상품 기준으로 삭제
function removeCartItemByProduct(productId, size) {
    AppState.cart = AppState.cart.filter(item => !(item.product_id === productId && item.size === size));
    renderProducts();
    renderCart();
}

// ========================================
// 개별 상품 결제수단 선택 모달
// ========================================

let currentEditingCartIndex = -1;
let paymentModalQuantity = 1;

async function openItemPaymentModal(cartIndex) {
    currentEditingCartIndex = cartIndex;
    const item = AppState.cart[cartIndex];
    if (!item) return;
    
    // 결제 수단 로드
    if (!AppState.paymentMethods) {
        try {
            const data = await apiRequest(`/api/payment-methods/${AppState.member.member_id}`);
            AppState.paymentMethods = data;
        } catch (e) {
            showError('결제 수단을 불러오는데 실패했습니다.');
            return;
        }
    }
    
    paymentModalQuantity = item.quantity;
    
    const modal = document.getElementById('itemPaymentModal');
    if (!modal) return;
    
    renderItemPaymentModal(item);
    modal.classList.add('show');
}

function renderItemPaymentModal(item) {
    const itemInfoEl = document.getElementById('itemPaymentItemInfo');
    const optionsEl = document.getElementById('itemPaymentOptions');
    
    if (itemInfoEl) {
        itemInfoEl.innerHTML = `
            <div class="item-payment-product">
                <strong>${item.name} (${item.size})</strong>
                <span class="item-payment-unit-price">${formatPrice(item.price)}/개</span>
            </div>
            <div class="item-payment-qty-selector">
                <span>적용 수량:</span>
                <button class="modal-qty-btn" onclick="changePaymentModalQty(-1)">−</button>
                <span class="modal-qty-value" id="paymentModalQtyValue">${paymentModalQuantity}</span>
                <button class="modal-qty-btn" onclick="changePaymentModalQty(1)">+</button>
                <span>/ ${item.quantity}개</span>
            </div>
        `;
    }
    
    const { subscriptions, vouchers } = AppState.paymentMethods || {};
    let optionsHtml = '';
    
    // 구독권 옵션
    if (subscriptions && subscriptions.length > 0) {
        subscriptions.forEach(sub => {
            const remaining = sub.remaining_by_category?.[item.category] ?? 0;
            const isAvailable = remaining >= paymentModalQuantity;
            
            optionsHtml += `
                <div class="item-payment-option ${isAvailable ? '' : 'disabled'}" 
                     onclick="${isAvailable ? `selectItemPayment('subscription', ${sub.subscription_id}, '구독권')` : ''}">
                    <div class="option-left">
                        <span class="option-icon">📋</span>
                        <div class="option-details">
                            <span class="option-name">${sub.product_name}</span>
                            <span class="option-info">${getCategoryName(item.category)} 남은 횟수: ${remaining}회</span>
                        </div>
                    </div>
                    ${!isAvailable ? '<span class="option-disabled-text">횟수 부족</span>' : ''}
                </div>
            `;
        });
    }
    
    // 금액권 옵션
    if (vouchers && vouchers.length > 0) {
        vouchers.forEach(v => {
            const itemTotal = item.price * paymentModalQuantity;
            const isAvailable = v.remaining_amount >= itemTotal;
            
            optionsHtml += `
                <div class="item-payment-option ${isAvailable ? '' : 'partial'}" 
                     onclick="selectItemPayment('voucher', ${v.voucher_id}, '${v.product_name}')">
                    <div class="option-left">
                        <span class="option-icon">💳</span>
                        <div class="option-details">
                            <span class="option-name">${v.product_name}</span>
                            <span class="option-info">잔액: ${formatPrice(v.remaining_amount)}</span>
                        </div>
                    </div>
                    ${!isAvailable ? '<span class="option-warning-text">잔액 부족 (부분 사용)</span>' : ''}
                </div>
            `;
        });
    }
    
    if (!optionsHtml) {
        optionsHtml = '<div class="no-payment-options">사용 가능한 결제 수단이 없습니다.</div>';
    }
    
    if (optionsEl) optionsEl.innerHTML = optionsHtml;
}

function changePaymentModalQty(delta) {
    const item = AppState.cart[currentEditingCartIndex];
    if (!item) return;
    
    const newQty = paymentModalQuantity + delta;
    if (newQty >= 1 && newQty <= item.quantity) {
        paymentModalQuantity = newQty;
        
        const qtyValueEl = document.getElementById('paymentModalQtyValue');
        if (qtyValueEl) qtyValueEl.textContent = paymentModalQuantity;
        
        // 옵션 목록 다시 렌더링 (수량에 따라 가용 여부 변경)
        renderItemPaymentModal(item);
    }
}

function selectItemPayment(type, id, name) {
    if (currentEditingCartIndex < 0) return;
    
    const item = AppState.cart[currentEditingCartIndex];
    if (!item) return;
    
    // 선택한 수량이 현재 아이템의 전체 수량인 경우
    if (paymentModalQuantity === item.quantity) {
        // 전체 아이템에 결제수단 적용
        item.payment = { type, id, name };
    } else {
        // 일부 수량만 분리
        const remainingQty = item.quantity - paymentModalQuantity;
        
        // 기존 아이템 수량 감소
        item.quantity = remainingQty;
        
        // 새 아이템 추가 (선택된 결제수단으로)
        AppState.cart.push({
            product_id: item.product_id,
            name: item.name,
            size: item.size,
            category: item.category,
            price: item.price,
            quantity: paymentModalQuantity,
            device_uuid: item.device_uuid,
            payment: { type, id, name },
        });
    }
    
    renderProducts();
    renderCart();
    closeItemPaymentModal();
}

function closeItemPaymentModal() {
    document.getElementById('itemPaymentModal')?.classList.remove('show');
    currentEditingCartIndex = -1;
    paymentModalQuantity = 1;
}

// ========================================
// 대여하기 버튼 처리
// ========================================

async function handleCheckout() {
    if (AppState.cart.length === 0) {
        showError('선택된 상품이 없습니다.');
        return;
    }
    
    const { subscriptions, vouchers } = AppState.paymentMethods || {};
    const totalPaymentMethods = (subscriptions?.length || 0) + (vouchers?.length || 0);
    
    // 결제수단이 1개만 있으면 자동 배정 후 바로 대여
    if (totalPaymentMethods === 1) {
        autoAssignSinglePaymentAndRent();
        return;
    }
    
    // 결제수단이 여러 개면 결제 확인 모달 표시
    openPaymentConfirmModal();
}

// 결제수단 1개일 때 자동 배정 후 비밀번호 입력
async function autoAssignSinglePaymentAndRent() {
    const { subscriptions, vouchers } = AppState.paymentMethods || {};
    
    // 구독권 1개만 있는 경우
    if (subscriptions?.length === 1 && (!vouchers || vouchers.length === 0)) {
        const sub = subscriptions[0];
        // 구독권으로 가능한 것만 배정, 나머지는 처리 불가
        AppState.cart.forEach(item => {
            const remaining = sub.remaining_by_category?.[item.category] || 0;
            if (remaining >= item.quantity) {
                item.payment = { type: 'subscription', id: sub.subscription_id, name: '구독권' };
            }
        });
        
        // 미배정 아이템 있으면 오류
        const unassigned = AppState.cart.filter(item => !item.payment);
        if (unassigned.length > 0) {
            showError('구독권 잔여 횟수가 부족합니다.');
            return;
        }
    }
    // 금액권 1개만 있는 경우
    else if (vouchers?.length === 1 && (!subscriptions || subscriptions.length === 0)) {
        const voucher = vouchers[0];
        const totalAmount = AppState.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
        
        if (voucher.remaining_amount < totalAmount) {
            showError(`금액권 잔액이 부족합니다. (잔액: ${formatPrice(voucher.remaining_amount)})`);
            return;
        }
        
        AppState.cart.forEach(item => {
            item.payment = { type: 'voucher', id: voucher.voucher_id, name: voucher.product_name };
        });
        
        // 금액권 선택 정보 저장
        AppState.voucherSelections = [{
            voucher_id: voucher.voucher_id,
            amount: totalAmount
        }];
    }
    
    // 비밀번호 입력 모달 열기
    openPasswordModal();
}

// ========================================
// 결제 확인 모달 (구독권 자동배정 + 금액권 쪼개기)
// ========================================

function openPaymentConfirmModal() {
    if (!AppState.paymentMethods) {
        showError('결제 수단을 불러오는 중입니다. 잠시 후 다시 시도해주세요.');
        return;
    }
    
    // 다른 모달이 열려있으면 먼저 닫기
    closeItemPaymentModal();
    closeNumpad();
    
    const modal = document.getElementById('bulkPaymentModal');
    if (!modal) return;
    
    // 구독권 자동 배정 계산
    const { subscriptions, vouchers } = AppState.paymentMethods;
    const cartItems = [...AppState.cart];
    
    // 구독권으로 처리할 아이템과 금액권으로 처리할 아이템 분리
    const subscriptionAssignments = []; // {item, subscription}
    const voucherItems = []; // 금액권으로 결제할 아이템
    
    // 구독권 잔여 횟수 복사 (계산용)
    const subRemaining = {};
    subscriptions?.forEach(sub => {
        subRemaining[sub.subscription_id] = { ...sub.remaining_by_category };
    });
    
    // 각 아이템에 대해 구독권 우선 배정 (부분 배정 지원)
    cartItems.forEach(item => {
        let remainingQty = item.quantity;
        
        // 구독권 확인 (가능한 만큼 배정)
        for (const sub of (subscriptions || [])) {
            if (remainingQty <= 0) break;
            
            const subRemain = subRemaining[sub.subscription_id]?.[item.category] || 0;
            if (subRemain > 0) {
                // 구독권으로 처리할 수 있는 수량
                const assignQty = Math.min(subRemain, remainingQty);
                
                subscriptionAssignments.push({
                    item: { ...item, quantity: assignQty },
                    subscription: sub,
                });
                subRemaining[sub.subscription_id][item.category] -= assignQty;
                remainingQty -= assignQty;
            }
        }
        
        // 남은 수량은 금액권으로
        if (remainingQty > 0) {
            voucherItems.push({ ...item, quantity: remainingQty });
        }
    });
    
    // 금액권 결제 필요 금액
    const voucherTotalAmount = voucherItems.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    
    // 모달 렌더링
    renderPaymentConfirmModal(subscriptionAssignments, voucherItems, voucherTotalAmount, vouchers);
    modal.classList.add('show');
}

function renderPaymentConfirmModal(subscriptionAssignments, voucherItems, voucherTotalAmount, vouchers) {
    const contentEl = document.getElementById('bulkPaymentContent');
    if (!contentEl) return;
    
    let html = '';
    
    // 구독권 자동 적용 섹션
    if (subscriptionAssignments.length > 0) {
        html += `
            <div class="payment-section">
                <div class="payment-section-title">📋 구독권 자동 적용</div>
                <div class="subscription-auto-items">
        `;
        
        // 구독권별로 그룹화
        const subGroups = {};
        subscriptionAssignments.forEach(({ item, subscription }) => {
            const key = subscription.subscription_id;
            if (!subGroups[key]) {
                subGroups[key] = { subscription, items: [] };
            }
            subGroups[key].items.push(item);
        });
        
        for (const [subId, group] of Object.entries(subGroups)) {
            html += `
                <div class="subscription-group">
                    <div class="subscription-name">${group.subscription.product_name}</div>
                    <div class="subscription-items">
                        ${group.items.map(item => `${item.name}(${item.size}) ${item.quantity}개`).join(', ')}
                    </div>
                </div>
            `;
        }
        
        html += `</div></div>`;
    }
    
    // 금액권 결제 섹션
    if (voucherTotalAmount > 0) {
        html += `
            <div class="payment-section">
                <div class="payment-section-title">💳 금액권 결제 (${formatPrice(voucherTotalAmount)})</div>
                <div class="voucher-items-summary">
                    ${voucherItems.map(item => `${item.name}(${item.size}) ${item.quantity}개 = ${formatPrice(item.price * item.quantity)}`).join('<br>')}
                </div>
                <div class="voucher-split-inputs" id="voucherSplitInputs">
        `;
        
        // 금액권별 입력 필드 (유효기간 짧은 순 정렬)
        const sortedVouchers = [...(vouchers || [])].sort((a, b) => {
            return new Date(a.valid_until) - new Date(b.valid_until);
        });
        
        // 자동 금액 배정: 전체 금액을 한번에 결제 가능한 금액권 우선 선택
        const autoAssignments = autoAssignVoucherAmounts(sortedVouchers, voucherTotalAmount);
        
        sortedVouchers.forEach((v, idx) => {
            // 종료일자 포맷팅
            const validUntil = v.valid_until ? new Date(v.valid_until) : null;
            const expiryText = validUntil ? 
                `~${validUntil.getMonth() + 1}/${validUntil.getDate()}` : '';
            
            // 자동 배정된 금액
            const assignedAmount = autoAssignments[v.voucher_id] || 0;
            
            html += `
                <div class="voucher-input-row">
                    <div class="voucher-input-info">
                        <span class="voucher-input-name">${v.product_name}</span>
                        <div class="voucher-input-meta">
                            <span class="voucher-input-balance">잔액: ${formatPrice(v.remaining_amount)}</span>
                            <span class="voucher-expiry">${expiryText}</span>
                        </div>
                    </div>
                    <div class="voucher-input-field">
                        <input type="text" 
                            id="voucherAmount_${v.voucher_id}" 
                            class="voucher-amount-input" 
                            data-voucher-id="${v.voucher_id}"
                            data-max="${v.remaining_amount}"
                            data-voucher-name="${v.product_name}"
                            value="${assignedAmount}"
                            readonly>
                        <span class="voucher-input-unit">원</span>
                        <button type="button" class="voucher-use-all-btn" data-voucher-id="${v.voucher_id}" data-max="${v.remaining_amount}">전액</button>
                    </div>
                </div>
            `;
        });
        
        html += `
                </div>
                <div class="voucher-total-row">
                    <span>배분 합계:</span>
                    <span id="voucherSplitTotal">0원</span>
                    <span>/ ${formatPrice(voucherTotalAmount)}</span>
                    <span id="voucherSplitStatus" class="split-status"></span>
                </div>
            </div>
        `;
    }
    
    // 버튼 (자동 배정으로 항상 충족되므로 바로 활성화)
    const btnDisabled = '';
    html += `
        <div class="payment-modal-buttons">
            <button class="modal-btn cancel" onclick="closeBulkPaymentModal()">취소</button>
            <button class="modal-btn confirm" id="confirmPaymentBtn" onclick="confirmPaymentAndRent()" ${btnDisabled}>대여하기</button>
        </div>
    `;
    
    contentEl.innerHTML = html;
    
    // 저장 (나중에 processRental에서 사용)
    AppState.pendingSubscriptionAssignments = subscriptionAssignments;
    AppState.pendingVoucherItems = voucherItems;
    AppState.pendingVoucherTotal = voucherTotalAmount;
    
    // 초기 합계 업데이트 (금액권이 있을 때만)
    if (voucherTotalAmount > 0) {
        updateVoucherTotal();
    }
}

// 금액권 자동 배정: 전체 금액을 한번에 결제 가능한 금액권 우선
function autoAssignVoucherAmounts(sortedVouchers, totalAmount) {
    const assignments = {};
    
    // 1. 먼저 전체 금액을 한번에 결제 가능한 금액권 찾기 (유효기간 짧은 순)
    const singlePayVoucher = sortedVouchers.find(v => v.remaining_amount >= totalAmount);
    
    if (singlePayVoucher) {
        // 한번에 결제 가능한 금액권이 있으면 그것만 사용
        sortedVouchers.forEach(v => {
            assignments[v.voucher_id] = (v.voucher_id === singlePayVoucher.voucher_id) ? totalAmount : 0;
        });
    } else {
        // 없으면 유효기간 짧은 순으로 채워나가기
        let remaining = totalAmount;
        sortedVouchers.forEach(v => {
            if (remaining > 0) {
                const useAmount = Math.min(v.remaining_amount, remaining);
                assignments[v.voucher_id] = useAmount;
                remaining -= useAmount;
            } else {
                assignments[v.voucher_id] = 0;
            }
        });
    }
    
    return assignments;
}

function updateVoucherTotal() {
    const inputs = document.querySelectorAll('.voucher-amount-input');
    let total = 0;
    
    inputs.forEach(input => {
        const val = parseInt(input.value) || 0;
        const max = parseInt(input.dataset.max) || 0;
        
        // 최대값 제한
        if (val > max) {
            input.value = max;
            total += max;
        } else {
            total += val;
        }
    });
    
    const totalEl = document.getElementById('voucherSplitTotal');
    const statusEl = document.getElementById('voucherSplitStatus');
    const confirmBtn = document.getElementById('confirmPaymentBtn');
    const required = AppState.pendingVoucherTotal || 0;
    
    if (totalEl) totalEl.textContent = formatPrice(total);
    
    if (statusEl && confirmBtn) {
        if (total === required) {
            statusEl.textContent = '✓';
            statusEl.className = 'split-status ok';
            confirmBtn.disabled = false;
        } else if (total < required) {
            statusEl.textContent = `(${formatPrice(required - total)} 부족)`;
            statusEl.className = 'split-status error';
            confirmBtn.disabled = true;
        } else {
            statusEl.textContent = `(${formatPrice(total - required)} 초과)`;
            statusEl.className = 'split-status error';
            confirmBtn.disabled = true;
        }
    }
}

function useAllVoucherBalance(voucherId, maxAmount) {
    const input = document.getElementById(`voucherAmount_${voucherId}`);
    if (input) {
        // 남은 필요 금액 계산
        const inputs = document.querySelectorAll('.voucher-amount-input');
        let currentTotal = 0;
        inputs.forEach(inp => {
            if (inp.id !== `voucherAmount_${voucherId}`) {
                currentTotal += parseInt(inp.value) || 0;
            }
        });
        
        const required = AppState.pendingVoucherTotal || 0;
        const remaining = required - currentTotal;
        
        input.value = Math.min(maxAmount, Math.max(0, remaining));
        updateVoucherTotal();
    }
}

async function confirmPaymentAndRent() {
    // 장바구니를 새로 구성 (구독권/금액권 분할 적용)
    const newCart = [];
    
    // 구독권 배정 아이템 추가
    const subAssignments = AppState.pendingSubscriptionAssignments || [];
    subAssignments.forEach(({ item, subscription }) => {
        newCart.push({
            ...item,
            payment: {
                type: 'subscription',
                id: subscription.subscription_id,
                name: '구독권'
            }
        });
    });
    
    // 금액권 배정 적용 (쪼개기 정보 포함)
    const voucherItems = AppState.pendingVoucherItems || [];
    const inputs = document.querySelectorAll('.voucher-amount-input');
    
    // voucher_selections 생성
    const voucherSelections = [];
    inputs.forEach(input => {
        const amount = parseInt(input.value) || 0;
        if (amount > 0) {
            voucherSelections.push({
                voucher_id: parseInt(input.dataset.voucherId),
                amount: amount
            });
        }
    });
    
    // 금액권 아이템 추가 (첫 번째 금액권으로)
    if (voucherSelections.length > 0 && voucherItems.length > 0) {
        voucherItems.forEach(item => {
            newCart.push({
                ...item,
                payment: {
                    type: 'voucher',
                    id: voucherSelections[0].voucher_id,
                    name: '금액권'
                }
            });
        });
    }
    
    // 장바구니 교체
    AppState.cart = newCart;
    
    // 쪼개기 정보 저장
    AppState.voucherSelections = voucherSelections;
    
    closeBulkPaymentModal();
    
    // 비밀번호 입력 모달 열기
    openPasswordModal();
}

// 기존 openBulkPaymentModal은 호환성 위해 유지
function openBulkPaymentModal() {
    openPaymentConfirmModal();
}

function renderBulkPaymentModal(unassignedItems) {
    const contentEl = document.getElementById('bulkPaymentContent');
    if (!contentEl) return;
    
    const totalAmount = unassignedItems.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    const totalQty = unassignedItems.reduce((sum, item) => sum + item.quantity, 0);
    
    // 카테고리별 필요 수량 계산
    const neededByCategory = {};
    unassignedItems.forEach(item => {
        neededByCategory[item.category] = (neededByCategory[item.category] || 0) + item.quantity;
    });
    
    const { subscriptions, vouchers } = AppState.paymentMethods || {};
    
    let html = `
        <div class="bulk-payment-summary">
            <div class="bulk-summary-title">미분류 상품 ${totalQty}개</div>
            <div class="bulk-summary-amount">총 ${formatPrice(totalAmount)}</div>
            <div class="bulk-summary-items">
                ${unassignedItems.map(item => `${item.name}(${item.size}) ${item.quantity}개`).join(', ')}
            </div>
        </div>
        <div class="bulk-payment-options">
    `;
    
    // 구독권 옵션
    if (subscriptions && subscriptions.length > 0) {
        subscriptions.forEach(sub => {
            const remainingByCat = sub.remaining_by_category || {};
            
            // 모든 카테고리에 대해 잔여 횟수 확인
            let isAvailable = true;
            let remainingInfo = [];
            for (const [cat, needed] of Object.entries(neededByCategory)) {
                const remaining = remainingByCat[cat] ?? 0;
                if (remaining < needed) {
                    isAvailable = false;
                }
                remainingInfo.push(`${getCategoryName(cat)} ${remaining}회`);
            }
            
            html += `
                <div class="bulk-payment-option ${isAvailable ? '' : 'disabled'}" 
                     onclick="${isAvailable ? `applyBulkPayment('subscription', ${sub.subscription_id}, '구독권')` : ''}">
                    <div class="option-left">
                        <span class="option-icon">📋</span>
                        <div class="option-details">
                            <span class="option-name">${sub.product_name}</span>
                            <span class="option-info">남은 횟수: ${remainingInfo.join(' / ')}</span>
                        </div>
                    </div>
                    ${!isAvailable ? '<span class="option-disabled-text">횟수 부족</span>' : ''}
                </div>
            `;
        });
    }
    
    // 금액권 옵션
    if (vouchers && vouchers.length > 0) {
        vouchers.forEach(v => {
            const isAvailable = v.remaining_amount >= totalAmount;
            
            html += `
                <div class="bulk-payment-option ${isAvailable ? '' : 'partial'}" 
                     onclick="applyBulkPayment('voucher', ${v.voucher_id}, '${v.product_name}')">
                    <div class="option-left">
                        <span class="option-icon">💳</span>
                        <div class="option-details">
                            <span class="option-name">${v.product_name}</span>
                            <span class="option-info">잔액: ${formatPrice(v.remaining_amount)}</span>
                        </div>
                    </div>
                    ${!isAvailable ? '<span class="option-warning-text">잔액 부족</span>' : ''}
                </div>
            `;
        });
    }
    
    html += '</div>';
    
    contentEl.innerHTML = html;
}

function applyBulkPayment(type, id, name) {
    // 모든 미분류 아이템에 결제수단 적용
    AppState.cart.forEach(item => {
        if (!item.payment) {
            item.payment = { type, id, name };
        }
    });
    
    closeBulkPaymentModal();
    renderCart();
    
    // 바로 대여 처리
    processRental();
}

function closeBulkPaymentModal() {
    document.getElementById('bulkPaymentModal')?.classList.remove('show');
}

// ========================================
// 대여 처리
// ========================================

async function processRental() {
    // 기본 처리 (쪼개기 없이)
    AppState.voucherSelections = null;
    await processRentalWithSplit();
}

async function processRentalWithSplit() {
    showLoading(true);
    
    try {
        // 구독권 아이템과 금액권 아이템 분리
        const subscriptionItems = AppState.cart.filter(item => item.payment?.type === 'subscription');
        const voucherItems = AppState.cart.filter(item => item.payment?.type === 'voucher');
        
        let allResults = { 
            success: true, 
            payment_type: 'mixed', 
            total_amount: 0,
            subscription_usage: [],
            voucher_details: []
        };
        
        // 구독권 결제 처리
        if (subscriptionItems.length > 0) {
            // 구독권 ID별로 그룹화
            const subGroups = {};
            subscriptionItems.forEach(item => {
                const subId = item.payment.id;
                if (!subGroups[subId]) subGroups[subId] = [];
                subGroups[subId].push(item);
            });
            
            for (const [subId, items] of Object.entries(subGroups)) {
                const result = await apiRequest('/api/rental/subscription', {
                    method: 'POST',
                    body: JSON.stringify({
                        member_id: AppState.member.member_id,
                        subscription_id: parseInt(subId),
                        payment_password: AppState.paymentPassword,
                        items: items.map(item => ({
                            product_id: item.product_id,
                            quantity: item.quantity,
                            device_uuid: item.device_uuid,
                        })),
                    }),
                });
                
                if (!result.success) {
                    throw new Error(result.message || '구독권 대여 처리 실패');
                }
                
                // 구독권 사용 내역 저장
                allResults.subscription_usage.push({
                    items: items.map(i => ({ name: i.name, size: i.size, quantity: i.quantity, category: i.category }))
                });
            }
        }
        
        // 금액권 결제 처리
        if (voucherItems.length > 0) {
            // 쪼개기 정보가 있으면 사용, 없으면 기존 방식
            let selections;
            if (AppState.voucherSelections && AppState.voucherSelections.length > 0) {
                selections = AppState.voucherSelections;
            } else {
                // 금액권별로 그룹화 및 금액 계산 (기존 방식)
                const voucherGroups = {};
                voucherItems.forEach(item => {
                    const vid = item.payment.id;
                    if (!voucherGroups[vid]) voucherGroups[vid] = { items: [], amount: 0 };
                    voucherGroups[vid].items.push(item);
                    voucherGroups[vid].amount += item.price * item.quantity;
                });
                
                selections = Object.entries(voucherGroups).map(([vid, data]) => ({
                    voucher_id: parseInt(vid),
                    amount: data.amount,
                }));
            }
            
            const result = await apiRequest('/api/rental/voucher', {
                method: 'POST',
                body: JSON.stringify({
                    member_id: AppState.member.member_id,
                    payment_password: AppState.paymentPassword,
                    items: voucherItems.map(item => ({
                        product_id: item.product_id,
                        quantity: item.quantity,
                        device_uuid: item.device_uuid,
                    })),
                    voucher_selections: selections,
                }),
            });
            
            if (!result.success) {
                throw new Error(result.message || '금액권 대여 처리 실패');
            }
            allResults.total_amount += result.total_amount || 0;
            allResults.voucher_details = selections; // 쪼개기 정보 저장
        }
        
        // 결과 저장 및 완료 페이지로 이동
        const itemsWithPayment = AppState.cart.map(item => ({
            ...item,
            payment_type: item.payment?.type,
        }));
        
        sessionStorage.setItem('rentalResult', JSON.stringify({
            items: itemsWithPayment,
            payment_type: allResults.payment_type,
            total_amount: allResults.total_amount,
            subscription_usage: allResults.subscription_usage,
            voucher_details: allResults.voucher_details,
        }));
        
        window.location.href = '/complete';
        
    } catch (error) {
        console.error('대여 오류:', error);
        showError(error.message || '대여 처리 중 오류가 발생했습니다.');
    } finally {
        showLoading(false);
        AppState.voucherSelections = null;
        AppState.paymentPassword = null;
    }
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
    
    // 상품 목록 (구독권/금액권 구분 없이 순수 상품 리스트)
    const itemsEl = document.getElementById('receiptItems');
    if (itemsEl) {
        // 상품별로 그룹화 (같은 상품 합치기)
        const itemGroups = {};
        result.items.forEach(item => {
            const key = `${item.name}-${item.size}`;
            if (!itemGroups[key]) {
                itemGroups[key] = { ...item, quantity: 0 };
            }
            itemGroups[key].quantity += item.quantity;
        });
        
        const totalQty = result.items.reduce((sum, item) => sum + item.quantity, 0);
        
        itemsEl.innerHTML = Object.values(itemGroups).map(item => `
            <div class="receipt-item">
                <div class="receipt-item-left">
                    <div class="receipt-item-name">${item.name} ${item.size || ''}</div>
                </div>
                <div class="receipt-item-right">
                    <div class="receipt-item-qty">${item.quantity}개</div>
                </div>
            </div>
        `).join('') + `
            <div class="receipt-item" style="border-top: 2px solid #3a3a5a; margin-top: 10px; padding-top: 15px;">
                <div class="receipt-item-left">
                    <div class="receipt-item-name" style="color: #888;">합계</div>
                </div>
                <div class="receipt-item-right">
                    <div class="receipt-item-qty">${totalQty}개</div>
                </div>
            </div>
        `;
    }
    
    // 결제 내역 (구독권 사용 + 금액권 결제 분리)
    const totalEl = document.getElementById('receiptTotal');
    if (totalEl) {
        let html = '';
        
        // 구독권 사용 내역
        const subscriptionItems = result.items.filter(item => item.payment_type === 'subscription');
        if (subscriptionItems.length > 0) {
            // 카테고리별로 그룹화
            const catCount = {};
            subscriptionItems.forEach(item => {
                const catName = getCategoryName(item.category);
                catCount[catName] = (catCount[catName] || 0) + item.quantity;
            });
            
            const usageText = Object.entries(catCount)
                .map(([cat, count]) => `${cat} ${count}회`)
                .join(', ');
            
            html += `
                <div class="receipt-payment-section">
                    <div class="receipt-payment-title">📋 구독권 사용</div>
                    <div class="receipt-payment-detail">${usageText}</div>
                </div>
            `;
        }
        
        // 금액권 결제 내역
        if (result.voucher_details && result.voucher_details.length > 0) {
            html += `
                <div class="receipt-payment-section">
                    <div class="receipt-payment-title">💳 금액권 결제</div>
            `;
            
            result.voucher_details.forEach(v => {
                html += `
                    <div class="receipt-total-row">
                        <span class="receipt-total-label">${v.product_name || '금액권'}</span>
                        <span class="receipt-total-value">${formatPrice(v.amount)}</span>
                    </div>
                `;
            });
            
            html += `</div>`;
        }
        
        // 총 결제 금액 (금액권 합계만)
        html += `
            <div class="receipt-total-row" style="border-top: 2px solid #3a3a5a; margin-top: 15px; padding-top: 15px;">
                <span class="receipt-total-label">총 결제 금액</span>
                <span class="receipt-total-value highlight">${formatPrice(result.total_amount)}</span>
            </div>
        `;
        
        totalEl.innerHTML = html;
    }
}

function getCategoryName(category) {
    const names = {
        'top': '상의',
        'pants': '하의',
        'towel': '수건',
        'sweat_towel': '땀수건',
        'other': '기타'
    };
    return names[category] || category || '기타';
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

// ========================================
// 숫자 키패드 (금액 입력용)
// ========================================

let currentNumpadInput = null;
let numpadCurrentValue = '';

function openNumpad(inputEl) {
    if (!inputEl) {
        console.error('openNumpad: inputEl이 없습니다');
        return;
    }
    
    currentNumpadInput = inputEl;
    numpadCurrentValue = inputEl.value || '0';
    
    const overlay = document.getElementById('numpadOverlay');
    const titleEl = document.getElementById('numpadTitle');
    const valueEl = document.getElementById('numpadValue');
    
    if (titleEl) {
        const voucherName = inputEl.dataset.voucherName || '금액권';
        const maxAmount = parseInt(inputEl.dataset.max) || 0;
        titleEl.textContent = `${voucherName} (최대 ${formatPrice(maxAmount)})`;
    }
    
    if (valueEl) {
        valueEl.textContent = formatPrice(parseInt(numpadCurrentValue) || 0);
    }
    
    if (overlay) {
        overlay.classList.add('show');
    } else {
        console.error('openNumpad: numpadOverlay를 찾을 수 없습니다');
    }
}

// 이벤트 위임을 통한 금액 입력 필드 및 전액 버튼 클릭 처리
document.addEventListener('click', function(e) {
    // 금액 입력 필드 클릭 시 숫자 키패드 열기
    if (e.target.classList.contains('voucher-amount-input')) {
        e.preventDefault();
        e.stopPropagation();
        openNumpad(e.target);
    }
    
    // "전액" 버튼 클릭 처리
    if (e.target.classList.contains('voucher-use-all-btn')) {
        e.preventDefault();
        e.stopPropagation();
        const voucherId = parseInt(e.target.dataset.voucherId);
        const maxAmount = parseInt(e.target.dataset.max);
        if (voucherId && maxAmount) {
            useAllVoucherBalance(voucherId, maxAmount);
        }
    }
});

function closeNumpad() {
    document.getElementById('numpadOverlay')?.classList.remove('show');
    currentNumpadInput = null;
    numpadCurrentValue = '';
}

function closeNumpadOnOverlay(event) {
    if (event.target.id === 'numpadOverlay') {
        closeNumpad();
    }
}

function numpadInput(digit) {
    // 0으로 시작하면 대체
    if (numpadCurrentValue === '0') {
        numpadCurrentValue = digit;
    } else {
        numpadCurrentValue += digit;
    }
    
    // 최대값 제한
    if (currentNumpadInput) {
        const max = parseInt(currentNumpadInput.dataset.max) || 999999;
        if (parseInt(numpadCurrentValue) > max) {
            numpadCurrentValue = max.toString();
        }
    }
    
    updateNumpadDisplay();
}

function numpadDelete() {
    if (numpadCurrentValue.length > 1) {
        numpadCurrentValue = numpadCurrentValue.slice(0, -1);
    } else {
        numpadCurrentValue = '0';
    }
    updateNumpadDisplay();
}

function numpadClear() {
    numpadCurrentValue = '0';
    updateNumpadDisplay();
}

function updateNumpadDisplay() {
    const valueEl = document.getElementById('numpadValue');
    if (valueEl) {
        valueEl.textContent = formatPrice(parseInt(numpadCurrentValue) || 0);
    }
}

function confirmNumpad() {
    if (currentNumpadInput) {
        currentNumpadInput.value = numpadCurrentValue;
        updateVoucherTotal();
    }
    closeNumpad();
}

// ========================================
// 결제 비밀번호 입력
// ========================================

let passwordValue = '';

function openPasswordModal() {
    passwordValue = '';
    
    const modal = document.getElementById('passwordModal');
    if (modal) {
        modal.classList.add('show');
        updatePasswordDisplay();
        clearPasswordError();
    }
}

function closePasswordModal() {
    document.getElementById('passwordModal')?.classList.remove('show');
    passwordValue = '';
    updatePasswordDisplay();
    clearPasswordError();
}

function passwordInput(digit) {
    if (passwordValue.length >= 6) return;
    
    passwordValue += digit;
    updatePasswordDisplay();
    clearPasswordError();
}

function passwordDelete() {
    if (passwordValue.length > 0) {
        passwordValue = passwordValue.slice(0, -1);
        updatePasswordDisplay();
        clearPasswordError();
    }
}

function passwordClear() {
    passwordValue = '';
    updatePasswordDisplay();
    clearPasswordError();
}

function updatePasswordDisplay() {
    const dots = document.querySelectorAll('#passwordDots .dot');
    const confirmBtn = document.getElementById('passwordConfirmBtn');
    
    dots.forEach((dot, index) => {
        dot.classList.toggle('filled', index < passwordValue.length);
    });
    
    if (confirmBtn) {
        confirmBtn.disabled = passwordValue.length !== 6;
    }
}

function clearPasswordError() {
    const errorEl = document.getElementById('passwordError');
    if (errorEl) {
        errorEl.textContent = '';
    }
}

function showPasswordError(message) {
    const errorEl = document.getElementById('passwordError');
    if (errorEl) {
        errorEl.textContent = message;
    }
}

async function confirmPassword() {
    if (passwordValue.length !== 6) {
        showPasswordError('6자리 비밀번호를 입력해주세요.');
        return;
    }
    
    // 비밀번호 저장 (API 호출 시 사용)
    AppState.paymentPassword = passwordValue;
    
    // 모달 닫기
    closePasswordModal();
    
    // 대여 처리 진행
    await processRentalWithSplit();
}

console.log('운동복 대여 시스템 로드됨 (개선된 결제수단 UI + 숫자 키패드 + 비밀번호)');

