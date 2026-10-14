const $=id=>document.getElementById(id);
const api=async(url,opt={})=>{const r=await fetch(url,{headers:{'Content-Type':'application/json'},...opt});const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.error||'Request failed');return d};
let notificationState={initialized:false,seen:new Set(),role:'',lastUnreadCount:0};
function notificationContainer(){let el=$('liveNotificationToast');if(!el){el=document.createElement('div');el.id='liveNotificationToast';el.className='live-toast-stack';document.body.appendChild(el)}return el}
function playNotificationSound(){try{const C=window.AudioContext||window.webkitAudioContext;if(!C)return;const c=new C();const o=c.createOscillator(),g=c.createGain();o.type='sine';o.frequency.setValueAtTime(880,c.currentTime);o.frequency.exponentialRampToValueAtTime(660,c.currentTime+.16);g.gain.setValueAtTime(.0001,c.currentTime);g.gain.exponentialRampToValueAtTime(.12,c.currentTime+.02);g.gain.exponentialRampToValueAtTime(.0001,c.currentTime+.2);o.connect(g);g.connect(c.destination);o.start();o.stop(c.currentTime+.22)}catch(e){}}
function browserNotify(title,message){try{if('Notification' in window&&Notification.permission==='granted')new Notification(title,{body:message,icon:'/static/favicon.ico'});}catch(e){}}
function requestBrowserNotifications(){try{if('Notification' in window&&Notification.permission==='default')Notification.requestPermission().catch(()=>{})}catch(e){}}
function showLiveNotification(n){const stack=notificationContainer();const el=document.createElement('div');el.className='live-toast';el.innerHTML=`<div class=\"live-toast-icon\">🔔</div><div><b>${esc(n.title)}</b><p>${esc(n.message)}</p></div><button aria-label=\"Close notification\" onclick=\"this.parentElement.remove()\">×</button>`;stack.prepend(el);setTimeout(()=>el.remove(),6500);playNotificationSound();browserNotify(n.title,n.message)}
async function processNotifications(d,forceNew=false){const list=d.notifications||[];if(!notificationState.initialized){list.forEach(n=>notificationState.seen.add(n.id));notificationState.initialized=true;return}for(const n of [...list].reverse()){if(!notificationState.seen.has(n.id)){notificationState.seen.add(n.id);showLiveNotification(n)}}}
async function markNotificationRead(id){try{await api('/api/notifications/'+id+'/read',{method:'PUT'});refreshNotifications();refreshStaffNotifications?.()}catch(e){}}
async function markAllNotificationsRead(){try{await api('/api/notifications/read-all',{method:'POST'});refreshNotifications?.();refreshStaffNotifications?.()}catch(e){}}
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function login(){const button=$('loginButton');const msg=$('msg');if(msg)msg.textContent='';if(button){button.disabled=true;button.innerHTML='Signing in… <span>⏳</span>'}try{const d=await api('/api/auth/login',{method:'POST',body:JSON.stringify({email:$('email').value.trim(),password:$('password').value})});if(msg){msg.textContent='Login successful. Opening your dashboard…';msg.className='msg success-msg'}location.href=d.role==='ADMIN'?'/admin':d.role==='STAFF'?'/staff':'/dashboard'}catch(e){if(msg){msg.textContent=e.message==='Invalid credentials'?'Email or password is incorrect. Check your details or create a student account.':e.message;msg.className='msg error-msg'}if(button){button.disabled=false;button.innerHTML='Sign in <span>→</span>'}}}
async function register(){try{await api('/api/auth/register',{method:'POST',body:JSON.stringify(Object.fromEntries(['full_name','student_id','email','phone','password','confirm_password'].map(x=>[x,$(x).value])))});$('msg').textContent='Registration successful. You can now login.'}catch(e){$('msg').textContent=e.message}}
async function logout(){await api('/api/auth/logout',{method:'POST'}).catch(()=>{});location.href='/login'}
let cart=[],menuData=[],selectedCategory='ALL';
async function initDashboard(){try{const me=await api('/api/me');notificationState.role=me.role;$('welcome').textContent='Welcome back, '+me.name+' 👋';if($('navUser'))$('navUser').textContent=me.name;requestBrowserNotifications();const d=await api('/api/menu');menuData=d.items||[];const h=await api('/api/menu/highlights');renderCategories(h.categories||[]);renderQuick(h);renderMenu();loadPickupSlots();refreshCart();refreshOrders();refreshQueue();refreshNotifications();heartbeat();setInterval(refreshQueue,5000);setInterval(refreshOrders,8000);setInterval(refreshNotifications,3000);setInterval(heartbeat,30000)}catch(e){location.href='/login'}}
function renderCategories(cats){$('categoryChips').innerHTML='<button class="chip active" onclick="selectCategory(this,\'ALL\')">All Items</button>'+cats.map(c=>`<button class="chip" onclick="selectCategory(this,${JSON.stringify(c.name)})">${esc(c.name)}</button>`).join('')}
function selectCategory(btn,cat){selectedCategory=cat;document.querySelectorAll('.chip').forEach(x=>x.classList.remove('active'));btn.classList.add('active');renderMenu()}
function renderQuick(h){const all=[...(h.top_ordered||[]).slice(0,3).map(x=>({...x,badge:'🔥 Most Ordered'})),...(h.instant_ready||[]).slice(0,3).map(x=>({...x,badge:'⚡ Ready Fast'}))];const seen=new Set();const items=all.filter(x=>!seen.has(x.id)&&seen.add(x.id));$('quickOrder').innerHTML=items.length?items.map(foodCard).join(''):'<div class="empty">No quick items available right now.</div>'}
function foodCard(x){const fav=JSON.parse(localStorage.getItem('campusbite_favs')||'[]').includes(x.id);return `<article class="food-card interactive-card"><div class="food-badge">${esc(x.badge||'Available')}</div><div class="food-image-wrap" onclick="previewFood(${x.id})"><img class="food-image" src="${esc(x.image||fallbackImage(x.category))}" onerror="this.src=fallbackImage('${esc(x.category)}')" loading="lazy" alt="${esc(x.name)}"><span class="image-zoom">↗</span></div><div class="food-info"><div class="food-title-row"><h3>${esc(x.name)}</h3><button class="heart-btn" title="Favorite" onclick="event.stopPropagation();toggleFavorite(${x.id},this)">${fav?'♥':'♡'}</button></div><p>${esc(x.description||'Freshly prepared')}</p><div class="food-bottom"><div><b>₹${Number(x.price).toFixed(0)}</b><span>⏱ ${x.preparation_time||5} min</span></div><button onclick="add(${x.id})">+ Add</button></div></div></article>`}
function renderMenu(){const q=($('menuSearch')?.value||'').trim().toLowerCase();const items=menuData.filter(x=>(selectedCategory==='ALL'||x.category===selectedCategory)&&(!q||x.name.toLowerCase().includes(q)||(x.description||'').toLowerCase().includes(q)));const count=$('menuCount');if(count)count.textContent=`${items.length} item${items.length===1?'':'s'}`;$('menu').innerHTML=items.length?items.map(x=>{const fav=JSON.parse(localStorage.getItem('campusbite_favs')||'[]').includes(x.id);return `<article class="menu-card interactive-card"><div class="menu-image-wrap" onclick="previewFood(${x.id})"><img class="menu-image" src="${esc(x.image||fallbackImage(x.category))}" onerror="this.src=fallbackImage('${esc(x.category)}')" loading="lazy" alt="${esc(x.name)}"><span class="image-zoom">View</span></div><div class="menu-card-body"><div class="menu-card-top"><span class="category-label">${esc(x.category)}</span><button class="heart-btn" title="Favorite" onclick="toggleFavorite(${x.id},this)">${fav?'♥':'♡'}</button></div><h3>${esc(x.name)}</h3><p>${esc(x.description||'Fresh campus favorite')}</p><div class="menu-card-footer"><div class="menu-meta"><b>₹${Number(x.price).toFixed(0)}</b><span>⏱ ${x.preparation_time||5} min</span></div><button class="add-btn" onclick="add(${x.id})">+ Add to cart</button></div></div></article>`}).join(''):'<div class="empty menu-empty">No matching food items.<br><small>Try another search or category.</small></div>'}

function fallbackImage(cat){const map={Meals:'/static/images/food-meals.svg','Snacks':'/static/images/food-snacks.svg','Beverages':'/static/images/food-beverages.svg','Breakfast':'/static/images/food-breakfast.svg','South Indian':'/static/images/food-south-indian.svg','Fast Food':'/static/images/food-fast-food.svg','Desserts':'/static/images/food-desserts.svg'};return map[cat]||'/static/images/food-default.svg';}
function previewFood(id){const x=menuData.find(a=>a.id===id);if(!x)return;const m=$('foodModal');if(!m)return;$('modalImg').src=x.image||fallbackImage(x.category);$('modalImg').onerror=()=>{$('modalImg').src=fallbackImage(x.category)};$('modalName').textContent=x.name;$('modalDesc').textContent=x.description||'Freshly prepared';$('modalPrice').textContent='₹'+Number(x.price).toFixed(0);$('modalTime').textContent=(x.preparation_time||5)+' min';$('modalAdd').onclick=()=>{add(x.id);closeFoodModal()};m.classList.add('show')}
function closeFoodModal(){$('foodModal')?.classList.remove('show')}
function toggleFavorite(id,btn){const fav=JSON.parse(localStorage.getItem('campusbite_favs')||'[]');const i=fav.indexOf(id);if(i>=0){fav.splice(i,1);btn.textContent='♡'}else{fav.push(id);btn.textContent='♥'}localStorage.setItem('campusbite_favs',JSON.stringify(fav))}
function add(id){const item=menuData.find(x=>x.id===id);if(!item)return;let x=cart.find(a=>a.id===id);x?x.quantity++:cart.push({id,name:item.name,price:item.price,preparation_time:item.preparation_time||5,quantity:1});refreshCart()}
function refreshCart(){const total=cart.reduce((s,x)=>s+x.price*x.quantity,0);$('cart').innerHTML=cart.length?cart.map(x=>`<div class="cart-line"><div><b>${esc(x.name)}</b><small>₹${x.price} each · ${x.preparation_time||5} min/item</small></div><div><button onclick="removeCart(${x.id})">−</button><b>${x.quantity}</b><button onclick="add(${x.id})">+</button></div></div>`).join(''):'<div class="empty">Your cart is empty.<br><small>Add a favorite from the menu.</small></div>';$('cartTotal').textContent=total.toFixed(0);$('cartCount').textContent=cart.reduce((s,x)=>s+x.quantity,0)+' items';$('quickCart').textContent=cart.reduce((s,x)=>s+x.quantity,0);updatePickupEta()}
function estimateCartMinutes(){return cart.length?Math.max(5,cart.reduce((sum,x)=>sum+(Number(x.preparation_time)||5)*x.quantity,0)):0}
async function loadPickupSlots(){try{const d=await api('/api/pickup-slots');$('pickupSlot').innerHTML=d.slots.map(x=>`<option value="${esc(x.value)}">${esc(x.label)}</option>`).join('');const hint=$('slotHint');if(hint)hint.textContent=`${d.active_orders} active order(s) · queue ~${d.queue_minutes} min`;updatePickupEta()}catch(e){$('pickupSlot').innerHTML='<option value="ASAP">ASAP — earliest available</option>'}}
function updatePickupEta(){const mins=estimateCartMinutes();const el=$('pickupEta');if(!el)return;const slot=$('pickupSlot')?.value||'ASAP';const label=slot==='ASAP'?'earliest available':slot;el.innerHTML=mins?`<b>⏱ Your food: about ${mins} min prep</b><span>Pickup preference: <strong>${esc(label)}</strong></span><span id="queueEtaHint">Checking live kitchen workload…</span>`:'Add items to see your preparation time.';refreshQueueSummary()}
async function refreshQueueSummary(){try{const d=await api('/api/queue/my-position');const hint=$('queueEtaHint');if(hint)hint.textContent=`${d.active_orders??0} active order(s) in kitchen · ${d.position??0} order(s) ahead of your latest order. Final time is confirmed at checkout.`}catch(e){}}
function removeCart(id){const x=cart.find(a=>a.id===id);if(!x)return;if(x.quantity>1)x.quantity--;else cart=cart.filter(a=>a.id!==id);refreshCart()}
async function placeOrder(){if(!cart.length){$('orderMsg').textContent='Add at least one item.';return}try{const requested=$('pickupSlot').value;const d=await api('/api/orders',{method:'POST',body:JSON.stringify({items:cart,pickup_slot:requested})});cart=[];refreshCart();const actual=d.pickup_slot||'ASAP';const adjusted=d.adjusted?` Kitchen is busy, so your slot moved from ${requested} to ${actual}.`:` Pickup slot: ${actual==='ASAP'?'earliest available':actual}.`;$('orderMsg').textContent=`✓ ${d.order_id} placed · Token #${d.token} · ${d.estimated_minutes} min estimated.${adjusted}`;loadPickupSlots();refreshOrders();refreshQueue();refreshNotifications()}catch(e){$('orderMsg').textContent=e.message}}
function trackingSteps(status){
 const steps=['ORDER_PLACED','ACCEPTED','PREPARING','READY','COLLECTED'];
 const current=steps.indexOf(status);
 return '<div class="order-timeline">'+steps.map((s,i)=>`<div class="timeline-step ${i<=current?'done':''} ${s===status?'current':''}"><span>${i<current?'✓':i===current?'●':'○'}</span><small>${s.replaceAll('_',' ')}</small></div>`).join('')+'</div>';
}
async function refreshOrders(){
 const d=await api('/api/orders');
 $('orders').innerHTML=d.orders.length?d.orders.slice(0,15).map(x=>`
 <div class="order-row trackable-order">
   <div class="order-main">
     <div><b>#${x.token_number} · ${esc(x.public_order_id)}</b><p>${esc(x.items)}</p></div>
     ${trackingSteps(x.status)}
     <div class="order-eta-line">⏱ <b>${x.status==='READY'?'Ready for pickup':x.status==='COLLECTED'?'Collected':(x.estimated_minutes||5)+' min estimated'}</b>
       ${x.estimated_ready_at&&!['COLLECTED','CANCELLED'].includes(x.status)?` · Expected around ${esc(x.estimated_ready_at)}`:''}
       ${x.pickup_slot?` · Pickup: ${esc(x.pickup_slot)}`:''}
     </div>
   </div>
   <div class="order-right"><b>₹${x.total}</b><span class="status status-${x.status.toLowerCase()}">${x.status.replaceAll('_',' ')}</span></div>
 </div>`).join(''):'<div class="empty">No orders yet.</div>';
 const active=d.orders.find(x=>!['COLLECTED','CANCELLED'].includes(x.status));
 $('kitchenLive').innerHTML=active?`
   <div class="tracking-card">
     <div class="token-big">#${active.token_number}</div>
     <div><b>${esc(active.items)}</b><p>Current status: <span class="status">${active.status.replaceAll('_',' ')}</span></p>
       ${trackingSteps(active.status)}
       <div class="customer-eta">⏱ ${active.status==='READY'?'Ready for pickup':(active.estimated_minutes||5)+' min estimated'} ${active.estimated_ready_at?'· Expected '+esc(active.estimated_ready_at):''}</div>
     </div>
   </div>`:'No active order right now.';
}
async function refreshQueue(){const d=await api('/api/queue/my-position');$('queue').innerHTML=d.token_number?`<div class="queue-main"><div class="token-big">#${d.token_number}</div><div><span class="eyebrow">YOUR TOKEN</span><h3>${d.status.replaceAll('_',' ')}</h3><p><b>${d.position||0}</b> order(s) ahead · <b>${d.active_orders??0}</b> active in kitchen</p><p class="queue-subtext">Kitchen processes orders in sequence. Staff workload can move your ready time by a few minutes.</p></div></div>`:`<div class="queue-main"><div class="token-big">${d.active_orders??0}</div><div><span class="eyebrow">ACTIVE KITCHEN QUEUE</span><h3>${d.active_orders?'Orders being prepared':'Kitchen is clear'}</h3><p>${d.active_orders??0} active order(s) currently in the queue.</p></div></div>`;$('quickToken').textContent=d.token_number?'#'+d.token_number:'—';$('quickAhead').textContent=d.position??'—';$('quickWait').textContent=d.position?Math.max(2,d.position*3)+' min':'— min'}
async function refreshNotifications(){const d=await api('/api/notifications');await processNotifications(d);const unread=d.notifications.filter(x=>!x.is_read).length;notificationState.lastUnreadCount=unread;document.querySelectorAll('[data-notification-count]').forEach(el=>{el.textContent=unread;el.classList.toggle('show',unread>0)});const mark=unread?`<button class="notice-mark" onclick="markAllNotificationsRead()">Mark all as read</button>`:'';$('notifications').innerHTML=`<div class="notice-toolbar"><span>${unread?`<b>${unread}</b> unread notification${unread===1?'':'s'}`:'All caught up'}</span>${mark}</div>`+(d.notifications.length?d.notifications.slice(0,10).map(x=>`<div class="notice ${x.is_read?'':'unread'}" onclick="markNotificationRead(${x.id})"><span>🔔</span><div><b>${esc(x.title)}</b><p>${esc(x.message)}</p><small>${x.created_at||''}</small></div></div>`).join(''):'<div class="empty">No notifications</div>')}
async function initStaff(){try{const me=await api('/api/me');notificationState.role=me.role;requestBrowserNotifications();heartbeat();refreshStaff();refreshStaffNotifications();setInterval(refreshStaff,4000);setInterval(refreshStaffNotifications,2500);setInterval(heartbeat,30000);setInterval(()=>{if($('staffClock'))$('staffClock').textContent=new Date().toLocaleTimeString()},1000)}catch(e){location.href='/login'}}
async function refreshStaffNotifications(){try{const d=await api('/api/staff/notifications');await processNotifications(d);const unread=d.notifications.filter(x=>!x.is_read).length;document.querySelectorAll('[data-notification-count]').forEach(el=>{el.textContent=unread;el.classList.toggle('show',unread>0)});const mark=unread?`<button class="notice-mark" onclick="markAllNotificationsRead()">Mark all as read</button>`:'';$('staffNotifications').innerHTML=`<div class="notice-toolbar"><span>${unread?`<b>${unread}</b> unread`:'All caught up'}</span>${mark}</div>`+(d.notifications.length?d.notifications.slice(0,10).map(x=>`<div class="notice ${x.is_read?'':'unread'}" onclick="markNotificationRead(${x.id})"><span>🔔</span><div><b>${esc(x.title)}</b><p>${esc(x.message)}</p><small>${esc(x.created_at||'')}</small></div></div>`).join(''):'<div class="empty">No kitchen notifications yet.</div>')}catch(e){}}
async function refreshStaff(){
 const d=await api('/api/staff/orders');
 const active=d.orders.filter(x=>!['COLLECTED','CANCELLED'].includes(x.status));
 const preparing=active.filter(x=>x.status==='PREPARING');
 const avg=active.length?Math.round(active.reduce((s,x)=>s+(x.estimated_minutes||5),0)/active.length):0;
 $('staffSummary').innerHTML=`<div><span>🆕 New</span><b>${d.orders.filter(x=>x.status==='ORDER_PLACED').length}</b></div><div><span>🔥 Preparing</span><b>${preparing.length}</b></div><div><span>⏱ Avg. Prep</span><b>${avg||0} min</b></div><div><span>✅ Ready</span><b>${d.orders.filter(x=>x.status==='READY').length}</b></div>`;
 const groups=[['ORDER_PLACED','New Orders','🆕'],['ACCEPTED','Accepted','👍'],['PREPARING','Preparing','🔥'],['READY','Ready for Pickup','✅']];
 $('staffOrders').innerHTML=groups.map(([status,title,icon])=>{
   const rows=d.orders.filter(x=>x.status===status);
   return `<section class="kitchen-col"><div class="col-head"><h2>${icon} ${title}</h2><span>${rows.length}</span></div>${rows.length?rows.map(x=>{
     const urgent=x.status==='PREPARING'&&x.remaining_minutes<=3;
     const etaControl=`<div class="eta-editor">
       <label>Customer ETA</label>
       <div class="eta-input-row"><input id="eta-${x.id}" type="number" min="1" max="240" value="${x.estimated_minutes||5}"><span>min</span>
       <button class="small-action" onclick="suggestEta(${x.id})">Suggest</button>
       <button class="small-action primary-mini" onclick="saveEta(${x.id})">Set</button></div>
       <small id="eta-hint-${x.id}">System suggestion uses item preparation + current kitchen workload.</small>
     </div>`;
     return `<article class="ticket ${urgent?'urgent-ticket':''}">
       <div class="ticket-top"><b>#${x.token_number}</b><span>${esc(x.public_order_id)}</span></div>
       <h3>${esc(x.items)}</h3><p>Student: ${esc(x.student)}</p>
       <div class="time-grid"><div><small>Estimated</small><b>${x.estimated_minutes||5} min</b></div>
       <div><small>${x.status==='PREPARING'?'Remaining':'Pickup'}</small><b>${x.status==='PREPARING'?(x.remaining_minutes+' min'):esc(x.pickup_slot||'ASAP')}</b></div></div>
       <span class="status">${x.status.replaceAll('_',' ')}</span>
       ${urgent?'<div class="urgent-note">⚠️ Please prioritize this order</div>':''}
       ${etaControl}
       <div class="ticket-actions">
         ${status==='ORDER_PLACED'?`<button onclick="setStatus(${x.id},'ACCEPTED')">Accept Order</button>`:''}
         ${status==='ACCEPTED'?`<button onclick="setStatus(${x.id},'PREPARING')">🔥 Start Preparing</button>`:''}
         ${status==='PREPARING'?`<button onclick="setStatus(${x.id},'READY')">✅ Mark Ready</button>`:''}
         ${status==='READY'?`<button onclick="verify(${x.id})">Verify & Collect</button>`:''}
       </div>
     </article>`}).join(''):'<div class="col-empty">No orders</div>'}</section>`
 }).join('');
 const history=$('staffOrderHistory');
 if(history){
   const all=[...d.orders].sort((a,b)=>Number(b.id)-Number(a.id));
   history.innerHTML=all.length?`<div class="history-count">${all.length} saved order(s) · ${active.length} currently active</div><table class="history-table"><thead><tr><th>Token</th><th>Customer</th><th>Items</th><th>Total</th><th>Pickup / ETA</th><th>Status</th></tr></thead><tbody>${all.map(x=>`<tr><td><b>#${esc(x.token_number)}</b><small>${esc(x.public_order_id||'')}</small></td><td><b>${esc(x.student||'Student')}</b><small>${esc(x.created_at||'')}</small></td><td>${esc(x.items||'')}</td><td>₹${Number(x.total||0).toFixed(2)}</td><td>${esc(x.pickup_slot||'ASAP')}<small>${x.status==='COLLECTED'?'Collected':x.status==='CANCELLED'?'Cancelled':`${Number(x.remaining_minutes??x.estimated_minutes??5)} min estimated`}</small></td><td><span class="status status-${String(x.status||'').toLowerCase()}">${esc(String(x.status||'').replaceAll('_',' '))}</span></td></tr>`).join('')}</tbody></table>`:'<div class="empty">No orders have been placed yet. New orders will appear here automatically.</div>';
 }
}
async function suggestEta(id){
 try{
   const d=await api('/api/staff/orders/'+id+'/eta-suggestion');
   const input=$('eta-'+id); if(input) input.value=d.suggested_minutes;
   const hint=$('eta-hint-'+id); if(hint) hint.textContent=`Suggested ${d.suggested_minutes} min = ${d.item_prep_minutes} min item prep + ${d.active_orders} active order(s) workload + ${d.busy_buffer_minutes} min busy buffer.`;
 }catch(e){alert(e.message)}
}
async function saveEta(id){
 try{
   const minutes=parseInt($('eta-'+id).value,10);
   const d=await api('/api/staff/orders/'+id+'/estimate',{method:'PUT',body:JSON.stringify({estimated_minutes:minutes})});
   const hint=$('eta-hint-'+id); if(hint) hint.textContent=`✓ Customer notified. New estimate: ${d.estimated_minutes} minutes.`;
   refreshStaff(); refreshStaffNotifications();
 }catch(e){alert(e.message)}
}
async function setStatus(id,status){
 try{
   const input=$('eta-'+id);
   const body={status};
   if(input && status!=='READY') body.estimated_minutes=parseInt(input.value,10);
   const d=await api('/api/staff/orders/'+id+'/status',{method:'PUT',body:JSON.stringify(body)});
   refreshStaff();refreshStaffNotifications();
 }catch(e){alert(e.message)}
}
async function verify(id){try{await api('/api/staff/orders/'+id+'/verify',{method:'POST'});refreshStaff();refreshStaffNotifications();refreshOrders?.()}catch(e){alert(e.message)}}
async function heartbeat(){await api('/api/session/heartbeat',{method:'POST'}).catch(()=>{})}
async function loadAdminData(){const [a,l,o,s,on]=await Promise.all([api('/api/admin/analytics'),api('/api/admin/audit-logs'),api('/api/admin/orders'),api('/api/admin/staff-activity'),api('/api/admin/online-users')]);$('stats').innerHTML=`<div><span>Students</span><b>${a.students}</b></div><div><span>Today's Orders</span><b>${a.today_orders}</b></div><div><span>Revenue</span><b>₹${a.revenue}</b></div><div><span>Active Queue</span><b>${a.active_queue}</b></div><div><span>🟢 Online Now</span><b>${on.users.length}</b></div>`;$('onlineUsers').innerHTML=on.users.length?`<div class="online-list">${on.users.map(x=>`<div class="online-user"><span class="avatar">${esc(x.full_name[0]||'U')}</span><div><b>${esc(x.full_name)}</b><small>${esc(x.role)} · ${esc(x.student_id)}</small></div><div class="online-time"><span>● Online</span><small>Last active ${esc(x.last_seen)}</small></div></div>`).join('')}</div>`:'<div class="empty">No users are currently active.</div>';$('staffActivity').innerHTML=s.staff.length?'<table><tr><th>Staff</th><th>Active Orders</th><th>Total Managed</th><th>Last Activity</th></tr>'+s.staff.map(x=>`<tr><td><b>${esc(x.full_name)}</b><br><small>${esc(x.student_id)}</small></td><td>${x.active_orders||0}</td><td>${x.total_orders||0}</td><td>${x.last_activity||'-'}</td></tr>`).join('')+'</table>':'No staff activity';$('adminOrders').innerHTML='<table><tr><th>Token</th><th>Student</th><th>Items</th><th>Amount</th><th>Status</th><th>Managed By</th></tr>'+o.orders.slice(0,20).map(x=>`<tr><td><b>#${x.token_number}</b></td><td>${esc(x.student)}</td><td>${esc(x.items)}</td><td>₹${x.total}</td><td><span class="status">${x.status.replaceAll('_',' ')}</span></td><td>${esc(x.staff||'Not assigned')}</td></tr>`).join('')+'</table>';$('logs').innerHTML=l.logs.slice(0,20).map(x=>`<div class="log-row"><span>${esc(x.timestamp)}</span><b>${esc(x.action)}</b><small>${esc(x.description||'')}</small></div>`).join('')||'No activity yet'}
async function initAdmin(){try{await api('/api/me');heartbeat();await loadAdminData();setInterval(loadAdminData,7000);setInterval(heartbeat,30000)}catch(e){location.href='/login'}}

document.addEventListener('change',e=>{if(e.target&&e.target.id==='pickupSlot')updatePickupEta()});
