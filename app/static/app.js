const state = { products: [], cart: new Map(), admin: false };
const money = new Intl.NumberFormat('es-PE', { style:'currency', currency:'PEN' });
const $ = (id) => document.getElementById(id);

async function jsonFetch(url, options = {}) {
  const response = await fetch(url, { credentials:'same-origin', ...options });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
  return body;
}

function renderCatalog() {
  $('product-count').textContent = `${state.products.length} productos`;
  $('catalog').innerHTML = state.products.map(product => `
    <article class="product">
      <div class="icon">${product.product_id.slice(-2)}</div>
      <p class="category">${product.category}</p>
      <h3>${product.name}</h3>
      <p class="price">${money.format(product.price)}</p>
      <button onclick="addToCart('${product.product_id}')">Agregar al carrito</button>
    </article>`).join('');
}

window.addToCart = function(productId) {
  state.cart.set(productId, (state.cart.get(productId) || 0) + 1);
  renderCart();
};

window.changeQty = function(productId, delta) {
  const next = (state.cart.get(productId) || 0) + delta;
  if (next <= 0) state.cart.delete(productId); else state.cart.set(productId, next);
  renderCart();
};

function renderCart() {
  if (!state.cart.size) { $('cart').className='cart-empty'; $('cart').textContent='Agrega productos del catálogo.'; return; }
  let total = 0;
  const rows = [...state.cart].map(([id, qty]) => {
    const product = state.products.find(item => item.product_id === id);
    total += product.price * qty;
    return `<div class="cart-row"><span>${product.name}<br><small>${qty} x ${money.format(product.price)}</small></span><button onclick="changeQty('${id}',-1)">−</button><button onclick="changeQty('${id}',1)">+</button></div>`;
  }).join('');
  $('cart').className='';
  $('cart').innerHTML = rows + `<div class="cart-total"><span>Total</span><span>${money.format(total)}</span></div>`;
}

async function checkout() {
  $('checkout-message').textContent='';
  try {
    const order = await jsonFetch('/api/orders', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ user_id:$('user-id').value, items:[...state.cart].map(([product_id,quantity]) => ({product_id,quantity})) }) });
    state.cart.clear(); renderCart();
    $('checkout-message').textContent = `Pedido ${order.order_id.slice(0,8)} creado y enviado a SQS.`;
    if (state.admin) refreshAdmin();
  } catch (error) { $('checkout-message').textContent=error.message; }
}

async function login(event) {
  event.preventDefault();
  try {
    await jsonFetch('/api/login', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:$('admin-user').value,password:$('admin-password').value}) });
    state.admin=true; $('admin-state').textContent='Administrador autenticado'; $('admin-state').className='badge'; $('login-message').textContent='Acceso concedido.'; refreshAdmin();
  } catch(error){ $('login-message').textContent=error.message; }
}

async function uploadImage(event) {
  event.preventDefault();
  const file=$('image-file').files[0]; if(!file){$('image-message').textContent='Selecciona una imagen.';return;}
  const form=new FormData(); form.append('image',file);
  try { const result=await jsonFetch(`/api/admin/users/${encodeURIComponent($('image-user').value)}/image`,{method:'POST',body:form}); $('image-message').textContent=`Guardada en s3://${result.bucket}/${result.key}`; }
  catch(error){$('image-message').textContent=error.message;}
}

async function refreshAdmin() {
  try {
    const [orders,queue]=await Promise.all([jsonFetch('/api/admin/orders'),jsonFetch('/api/admin/queue')]);
    $('queue-count').textContent=queue.ApproximateNumberOfMessages;
    $('orders').innerHTML=orders.slice(0,100).map(order=>`<tr><td>${order.order_id.slice(0,8)}</td><td>${order.user_id}</td><td>${money.format(order.total)}</td><td>${order.status}</td><td>${new Date(order.created_at).toLocaleString('es-PE')}</td></tr>`).join('') || '<tr><td colspan="5">No hay pedidos.</td></tr>';
  } catch(error){ if(error.message.includes('administrador')) state.admin=false; }
}

async function start() {
  try { const [products,health]=await Promise.all([jsonFetch('/api/products'),jsonFetch('/api/health')]); state.products=products; renderCatalog(); $('health').textContent=`AWS local activo · ${health.products} productos · ${health.orders} pedidos`; }
  catch(error){$('health').textContent=`Servicios no disponibles: ${error.message}`;}
}
$('checkout').addEventListener('click',checkout);
$('login-form').addEventListener('submit',login);
$('image-form').addEventListener('submit',uploadImage);
$('refresh-admin').addEventListener('click',refreshAdmin);
start();
