/**
 * 운동복 대여 시스템 - 키오스크 JavaScript
 */

// ========================================
// 전역 상태
// ========================================

const AppState = {
    member: null,           // 로그인된 회원 정보
    products: [],           // 상품 목록
    cart: [],               // 장바구니
    currentCategory: null,  // 현재 선택된 카테고리
};

// ========================================
// 유틸리티 함수
// ========================================

/**
 * 전화번호 포맷팅 (01012345678 -> 010-1234-5678)
 */
function formatPhoneNumber(numbers) {
    if (!numbers) return '';
    
    const cleaned = numbers.replace(/\D/g, '');
    
    if (cleaned.length <= 3) {
        return cleaned;
    } else if (cleaned.length <= 7) {
        return `${cleaned.slice(0, 3)}-${cleaned.slice(3)}`;
    } else {
        return `${cleaned.slice(0, 3)}-${cleaned.slice(3, 7)}-${cleaned.slice(7, 11)}`;
    }
}

/**
 * 에러 메시지 표시
 */
function showError(message, duration = 3000) {
    const errorEl = document.getElementById('errorMessage');
    if (!errorEl) return;
    
    errorEl.textContent = message;
    errorEl.classList.add('show');
    
    setTimeout(() => {
        errorEl.classList.remove('show');
    }, duration);
}

/**
 * 로딩 표시/숨기기
 */
function showLoading(show = true) {
    const overlay = document.getElementById('loadingOverlay');
    if (!overlay) return;
    
    if (show) {
        overlay.classList.add('show');
    } else {
        overlay.classList.remove('show');
    }
}

/**
 * API 요청 헬퍼
 */
async function apiRequest(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
        },
    };
    
    const response = await fetch(url, { ...defaultOptions, ...options });
    const data = await response.json();
    
    if (!response.ok) {
        throw new Error(data.message || '요청 처리 중 오류가 발생했습니다.');
    }
    
    return data;
}

// ========================================
// 로그인 페이지
// ========================================

let phoneNumbers = '';

function initLoginPage() {
    phoneNumbers = '';
    updatePhoneDisplay();
    
    // 키패드 이벤트 설정
    document.querySelectorAll('.key-btn').forEach(btn => {
        btn.addEventListener('click', handleKeyPress);
    });
    
    // 로그인 버튼 이벤트
    const loginBtn = document.getElementById('loginBtn');
    if (loginBtn) {
        loginBtn.addEventListener('click', handleLogin);
    }
    
    console.log('로그인 페이지 초기화 완료');
}

function handleKeyPress(e) {
    const key = e.currentTarget.dataset.key;
    
    if (key === 'delete') {
        // 마지막 숫자 삭제
        phoneNumbers = phoneNumbers.slice(0, -1);
    } else if (key === 'clear') {
        // 전체 삭제
        phoneNumbers = '';
    } else {
        // 숫자 추가 (최대 11자리)
        if (phoneNumbers.length < 11) {
            phoneNumbers += key;
        }
    }
    
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
    
    // 전화번호가 10자리 이상이면 로그인 버튼 활성화
    if (loginBtn) {
        loginBtn.disabled = phoneNumbers.length < 10;
    }
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
            // 회원 정보 저장 후 대여 페이지로 이동
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
    // 세션에서 회원 정보 로드
    const memberData = sessionStorage.getItem('member');
    if (!memberData) {
        // 로그인 안됨 -> 홈으로 리다이렉트
        window.location.href = '/';
        return;
    }
    
    AppState.member = JSON.parse(memberData);
    AppState.cart = [];
    
    // 회원 정보 표시
    updateMemberDisplay();
    
    // 상품 목록 로드
    loadProducts();
    
    // 로그아웃 버튼
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }
    
    // 대여하기 버튼
    const checkoutBtn = document.getElementById('checkoutBtn');
    if (checkoutBtn) {
        checkoutBtn.addEventListener('click', handleCheckout);
    }
    
    console.log('대여 페이지 초기화 완료');
}

function updateMemberDisplay() {
    const nameEl = document.getElementById('memberName');
    const countEl = document.getElementById('memberCount');
    
    if (nameEl && AppState.member) {
        nameEl.textContent = `${AppState.member.name}님`;
    }
    
    if (countEl && AppState.member) {
        countEl.innerHTML = `잔여 <strong>${AppState.member.remaining_count}</strong>회`;
    }
}

async function loadProducts() {
    try {
        const data = await apiRequest('/api/products');
        AppState.products = data.products || [];
        
        // 카테고리 탭 생성
        renderCategoryTabs();
        
        // 첫 번째 카테고리 선택
        if (AppState.products.length > 0) {
            const categories = [...new Set(AppState.products.map(p => p.category))];
            if (categories.length > 0) {
                selectCategory(categories[0]);
            }
        }
    } catch (error) {
        console.error('상품 로드 오류:', error);
        showError('상품 목록을 불러오는데 실패했습니다.');
    }
}

function renderCategoryTabs() {
    const tabsContainer = document.getElementById('categoryTabs');
    if (!tabsContainer) return;
    
    // 카테고리 추출 및 한글 변환
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
    
    // 탭 클릭 이벤트
    tabsContainer.querySelectorAll('.category-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            selectCategory(tab.dataset.category);
        });
    });
}

function selectCategory(category) {
    AppState.currentCategory = category;
    
    // 탭 활성화 상태 업데이트
    document.querySelectorAll('.category-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.category === category);
    });
    
    // 상품 그리드 렌더링
    renderProducts();
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
        if (!product.connected) {
            statusText = '<span class="product-offline">연결 안됨</span>';
        } else if (!product.online) {
            statusText = '<span class="product-offline">오프라인</span>';
        }
        
        return `
            <div class="product-card ${isDisabled ? 'disabled' : ''} ${inCart ? 'in-cart' : ''}"
                 data-product-id="${product.product_id}"
                 ${isDisabled ? '' : 'onclick="openQuantityModal(\'' + product.product_id + '\')"'}>
                <div class="product-size">${product.size || '-'}</div>
                <div class="product-name">${product.name}</div>
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
    
    // 이미 장바구니에 있는 경우 해당 수량으로 시작
    const existingItem = AppState.cart.find(item => item.product_id === productId);
    selectedQuantity = existingItem ? existingItem.quantity : 1;
    
    updateQuantityDisplay();
    
    const modal = document.getElementById('quantityModal');
    const titleEl = document.getElementById('modalProductName');
    
    if (titleEl) {
        titleEl.textContent = `${selectedProduct.name} (${selectedProduct.size})`;
    }
    
    if (modal) {
        modal.classList.add('show');
    }
}

function closeQuantityModal() {
    const modal = document.getElementById('quantityModal');
    if (modal) {
        modal.classList.remove('show');
    }
    selectedProduct = null;
}

function changeQuantity(delta) {
    if (!selectedProduct) return;
    
    const newQty = selectedQuantity + delta;
    const maxQty = selectedProduct.stock;
    
    if (newQty >= 1 && newQty <= maxQty) {
        selectedQuantity = newQty;
        updateQuantityDisplay();
    }
}

function updateQuantityDisplay() {
    const valueEl = document.getElementById('qtyValue');
    const minusBtn = document.getElementById('qtyMinus');
    const plusBtn = document.getElementById('qtyPlus');
    
    if (valueEl) {
        valueEl.textContent = selectedQuantity;
    }
    
    if (minusBtn) {
        minusBtn.disabled = selectedQuantity <= 1;
    }
    
    if (plusBtn && selectedProduct) {
        plusBtn.disabled = selectedQuantity >= selectedProduct.stock;
    }
}

function confirmQuantity() {
    if (!selectedProduct) return;
    
    // 장바구니에 추가 또는 업데이트
    const existingIndex = AppState.cart.findIndex(item => item.product_id === selectedProduct.product_id);
    
    if (existingIndex >= 0) {
        AppState.cart[existingIndex].quantity = selectedQuantity;
    } else {
        AppState.cart.push({
            product_id: selectedProduct.product_id,
            name: selectedProduct.name,
            size: selectedProduct.size,
            category: selectedProduct.category,
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
        cartItemsEl.innerHTML = AppState.cart.map(item => `
            <div class="cart-item">
                <div class="cart-item-info">
                    <span class="cart-item-name">${item.name} (${item.size})</span>
                    <span class="cart-item-qty">${item.quantity}개</span>
                </div>
                <button class="cart-item-remove" onclick="removeFromCart('${item.product_id}')">×</button>
            </div>
        `).join('');
    }
    
    // 총 차감 횟수 계산
    const totalCount = AppState.cart.reduce((sum, item) => sum + item.quantity, 0);
    
    if (cartTotalEl) {
        cartTotalEl.innerHTML = `총 <strong>${totalCount}</strong>회 차감`;
    }
    
    if (checkoutBtn) {
        checkoutBtn.disabled = AppState.cart.length === 0;
    }
}

function removeFromCart(productId) {
    AppState.cart = AppState.cart.filter(item => item.product_id !== productId);
    renderProducts();
    renderCart();
}

async function handleCheckout() {
    if (AppState.cart.length === 0) {
        showError('선택된 상품이 없습니다.');
        return;
    }
    
    const totalCount = AppState.cart.reduce((sum, item) => sum + item.quantity, 0);
    
    if (totalCount > AppState.member.remaining_count) {
        showError(`잔여 횟수가 부족합니다. (필요: ${totalCount}회, 잔여: ${AppState.member.remaining_count}회)`);
        return;
    }
    
    showLoading(true);
    
    try {
        const data = await apiRequest('/api/rental/process', {
            method: 'POST',
            body: JSON.stringify({
                member_id: AppState.member.member_id,
                items: AppState.cart.map(item => ({
                    product_id: item.product_id,
                    quantity: item.quantity,
                    device_uuid: item.device_uuid,
                })),
            }),
        });
        
        if (data.success) {
            // 대여 결과 저장 후 완료 페이지로 이동
            sessionStorage.setItem('rentalResult', JSON.stringify({
                items: AppState.cart,
                total_count: totalCount,
                remaining_count: data.remaining_count,
            }));
            window.location.href = '/complete';
        } else {
            showError(data.message || '대여 처리에 실패했습니다.');
        }
    } catch (error) {
        console.error('대여 오류:', error);
        showError(error.message || '대여 처리 중 오류가 발생했습니다.');
    } finally {
        showLoading(false);
    }
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
    
    // 결과 표시
    renderCompleteResult(result);
    
    // 세션 정리
    sessionStorage.removeItem('member');
    sessionStorage.removeItem('rentalResult');
    
    // 5초 후 홈으로 이동
    startCountdown(5);
}

function renderCompleteResult(result) {
    const summaryEl = document.getElementById('completeSummary');
    
    if (!summaryEl) return;
    
    const itemsHtml = result.items.map(item => `
        <div class="summary-row">
            <span class="summary-label">${item.name} (${item.size})</span>
            <span class="summary-value">${item.quantity}개</span>
        </div>
    `).join('');
    
    summaryEl.innerHTML = `
        ${itemsHtml}
        <div class="summary-row">
            <span class="summary-label">총 차감</span>
            <span class="summary-value">${result.total_count}회</span>
        </div>
        <div class="summary-row">
            <span class="summary-label">잔여 횟수</span>
            <span class="summary-value highlight">${result.remaining_count}회</span>
        </div>
    `;
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
// 페이지 초기화
// ========================================

console.log('운동복 대여 시스템 로드됨');
