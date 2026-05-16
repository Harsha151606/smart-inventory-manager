// Smart Inventory Manager - Frontend Logic
let categories=[], scannerInstance=null, forecastChart=null, searchTimer=null;

// --- Navigation ---
function navigate(view){
  document.querySelectorAll('.view').forEach(v=>v.classList.add('hidden'));
  document.getElementById('view-'+view).classList.remove('hidden');
  document.querySelectorAll('.nav-btn').forEach(b=>{b.classList.toggle('active',b.dataset.view===view)});
  if(view==='dash')loadDashboard();
  if(view==='inv')loadItems();
  if(view==='scan')startScanner();
  if(view==='analytics')loadAnalytics();
  if(view!=='scan')stopScanner();
}

// --- API ---
async function api(url,opts={}){
  try{
    const r=await fetch(url,{headers:{'Content-Type':'application/json'},...opts});
    if(!r.ok)throw new Error('Request failed');
    return await r.json();
  }catch(e){toast(e.message,'error');return null;}
}

// --- Toast ---
function toast(msg,type='success'){
  const t=document.getElementById('toast'),inner=document.getElementById('toast-inner'),m=document.getElementById('toast-msg');
  m.textContent=msg;
  inner.className='px-4 py-3 rounded-xl shadow-2xl backdrop-blur-xl border border-white/10 flex items-center gap-3 '+
    (type==='error'?'bg-red-500/90':'type'==='warn'?'bg-amber-500/90':'bg-emerald-500/90');
  t.classList.remove('hidden');setTimeout(()=>t.classList.add('toast-show'),10);
  setTimeout(()=>{t.classList.remove('toast-show');setTimeout(()=>t.classList.add('hidden'),300)},3000);
}

// --- Search ---
function debounceSearch(){clearTimeout(searchTimer);searchTimer=setTimeout(loadItems,300);}

// --- Dashboard ---
async function loadDashboard(){
  const[items,insights,txns]=await Promise.all([api('/api/items'),api('/api/analytics'),api('/api/transactions?limit=8')]);
  if(!items)return;
  const total=items.length, low=items.filter(i=>i.quantity<=i.threshold&&i.quantity>0).length,
    out=items.filter(i=>i.quantity===0).length, ok=total-low-out;

  document.getElementById('stats-grid').innerHTML=`
    <div class="stat-card"><p class="text-2xl font-bold text-accent-400">${total}</p><p class="text-xs text-gray-400 mt-1">Total Items</p></div>
    <div class="stat-card"><p class="text-2xl font-bold text-success-400">${ok}</p><p class="text-xs text-gray-400 mt-1">In Stock</p></div>
    <div class="stat-card"><p class="text-2xl font-bold text-warn-400">${low}</p><p class="text-xs text-gray-400 mt-1">Low Stock</p></div>
    <div class="stat-card"><p class="text-2xl font-bold text-danger-400">${out}</p><p class="text-xs text-gray-400 mt-1">Out of Stock</p></div>`;

  // Alert banner
  const alertItems=items.filter(i=>i.quantity<=i.threshold);
  const banner=document.getElementById('alert-banner');
  if(alertItems.length){
    document.getElementById('alert-text').textContent=`${alertItems.length} item(s) need attention: ${alertItems.slice(0,3).map(i=>i.name).join(', ')}`;
    banner.classList.remove('hidden');
  }else banner.classList.add('hidden');

  // Insights
  const il=document.getElementById('insights-list');
  if(insights&&insights.length){
    il.innerHTML=insights.map(ins=>{
      if(ins.type==='summary')return`<div class="insight-card"><p class="font-semibold text-accent-400">🏥 Inventory Health: ${ins.health_score}%</p><div class="w-full bg-surface-700 rounded-full h-2 mt-2"><div class="h-2 rounded-full bg-gradient-to-r from-accent-500 to-success-400" style="width:${ins.health_score}%"></div></div></div>`;
      if(ins.type==='critical_stock')return`<div class="insight-card border-danger-500/30"><p class="font-semibold text-danger-400">🚨 ${ins.message}</p><p class="text-sm text-gray-400 mt-1">${ins.items.map(i=>`${i.name} (~${i.days||'?'}d)`).join(', ')}</p></div>`;
      if(ins.type==='threshold_adjustment')return`<div class="insight-card"><p class="font-semibold text-warn-400">🤖 AI Suggestion</p><p class="text-sm text-gray-300 mt-1">${ins.message}</p></div>`;
      return'';
    }).join('');
  }else il.innerHTML='<p class="text-gray-500 text-sm">No insights yet</p>';

  // Recent activity
  const ra=document.getElementById('recent-activity');
  if(txns&&txns.length){
    ra.innerHTML=txns.map(t=>{
      const icon=t.action_type==='restocked'?'📥':t.action_type==='consumed'?'📤':t.action_type==='created'?'✨':'✏️';
      const time=new Date(t.created_at).toLocaleDateString();
      return`<div class="flex items-center gap-3 bg-surface-800/50 rounded-xl px-3 py-2 border border-white/5">
        <span class="text-lg">${icon}</span>
        <div class="flex-1 min-w-0"><p class="text-sm font-medium truncate">${t.item_name||'Item #'+t.item_id}</p><p class="text-xs text-gray-500">${t.action_type} · ${t.quantity_change>0?'+':''}${t.quantity_change}</p></div>
        <span class="text-xs text-gray-600">${time}</span></div>`;
    }).join('');
  }else ra.innerHTML='<p class="text-gray-500 text-sm">No activity yet</p>';
}

// --- Items ---
async function loadItems(){
  const q=document.getElementById('search-input').value;
  const cat=document.getElementById('filter-cat').value;
  const st=document.getElementById('filter-status').value;
  const items=await api(`/api/items?q=${encodeURIComponent(q)}&category=${cat}&status=${st}`);
  if(!items)return;
  const grid=document.getElementById('items-grid'), empty=document.getElementById('empty-state');
  if(!items.length){grid.innerHTML='';empty.classList.remove('hidden');return;}
  empty.classList.add('hidden');
  grid.innerHTML=items.map(i=>{
    const pct=i.threshold>0?Math.min(100,Math.round(i.quantity/i.threshold*100)):100;
    const cls=i.quantity===0?'out':i.quantity<=i.threshold?'low':'ok';
    const barClr=cls==='out'?'from-red-500 to-red-600':cls==='low'?'from-amber-400 to-amber-500':'from-emerald-400 to-emerald-500';
    return`<div class="card cursor-pointer" onclick="viewItem(${i.id})">
      <div class="flex items-start justify-between mb-3">
        <div class="min-w-0 flex-1"><h3 class="font-semibold truncate">${i.name}</h3><p class="text-xs text-gray-500">${i.category_name||'Uncategorized'} · #${i.id}</p></div>
        <span class="badge badge-${cls}">${cls==='out'?'OUT':cls==='low'?'LOW':'OK'}</span>
      </div>
      <div class="flex items-center gap-3 mb-3">
        <div class="flex-1"><div class="flex justify-between text-xs mb-1"><span class="text-gray-400">Stock</span><span class="font-medium">${i.quantity} ${i.unit||'pcs'}</span></div>
        <div class="w-full bg-surface-600 rounded-full h-1.5"><div class="h-1.5 rounded-full bg-gradient-to-r ${barClr} transition-all" style="width:${Math.min(pct,100)}%"></div></div></div>
      </div>
      <div class="flex items-center justify-between">
        <span class="text-xs text-gray-500">Threshold: ${i.threshold}</span>
        <div class="flex gap-1" onclick="event.stopPropagation()">
          <button class="qty-btn" onclick="quickUpdate(${i.id},'dec')">−</button>
          <span class="w-10 text-center text-sm font-semibold" id="qty-${i.id}">${i.quantity}</span>
          <button class="qty-btn" onclick="quickUpdate(${i.id},'inc')">+</button>
        </div>
      </div>
    </div>`;
  }).join('');
}

async function quickUpdate(id,dir){
  const url=`/api/items/${id}/${dir==='inc'?'increment':'decrement'}`;
  const r=await api(url,{method:'POST',body:JSON.stringify({amount:1})});
  if(r){document.getElementById('qty-'+id).textContent=r.quantity;toast(dir==='inc'?'Stock added':'Stock removed');}
}

// --- Item Detail ---
async function viewItem(id){
  const item=await api('/api/items/'+id);
  if(!item)return;
  const cls=item.quantity===0?'out':item.quantity<=item.threshold?'low':'ok';
  const dc=document.getElementById('detail-content');
  dc.innerHTML=`
    <button onclick="navigate('inv')" class="text-sm text-gray-400 hover:text-accent-400 mb-4 flex items-center gap-1">← Back</button>
    <div class="card mb-4">
      <div class="flex items-start justify-between mb-4">
        <div><h2 class="text-xl font-bold">${item.name}</h2><p class="text-sm text-gray-400">${item.category_name||'Uncategorized'} · SKU: ${item.sku||'N/A'} · #${item.id}</p></div>
        <span class="badge badge-${cls} text-base px-4 py-1">${item.quantity} ${item.unit||'pcs'}</span>
      </div>
      ${item.description?`<p class="text-sm text-gray-300 mb-4">${item.description}</p>`:''}
      <div class="grid grid-cols-2 gap-3 mb-4">
        <div class="bg-surface-700/50 rounded-xl p-3 text-center"><p class="text-xs text-gray-500">Threshold</p><p class="text-lg font-bold text-warn-400">${item.threshold}</p></div>
        <div class="bg-surface-700/50 rounded-xl p-3 text-center"><p class="text-xs text-gray-500">Status</p><p class="text-lg font-bold ${cls==='ok'?'text-success-400':cls==='low'?'text-warn-400':'text-danger-400'}">${cls.toUpperCase()}</p></div>
      </div>
      <div class="flex gap-2">
        <button onclick="quickUpdate(${item.id},'dec')" class="flex-1 py-2.5 rounded-xl bg-danger-500/10 border border-danger-500/20 text-danger-400 font-semibold hover:bg-danger-500/20 transition">− Remove</button>
        <button onclick="quickUpdate(${item.id},'inc')" class="flex-1 py-2.5 rounded-xl bg-success-400/10 border border-success-400/20 text-success-400 font-semibold hover:bg-success-400/20 transition">+ Add</button>
      </div>
    </div>
    ${item.qr_image?`<div class="card mb-4 text-center"><p class="text-sm font-medium text-gray-400 mb-3">QR Code</p><img src="data:image/png;base64,${item.qr_image}" class="mx-auto w-40 h-40 rounded-xl bg-white p-2"><p class="text-xs text-gray-500 mt-2">Scan to view item details</p></div>`:''}
    ${item.prediction?`<div class="card mb-4"><p class="text-sm font-semibold text-accent-400 mb-2">🧠 AI Prediction</p>
      <div class="grid grid-cols-2 gap-2 text-sm">
        <div class="bg-surface-700/50 rounded-lg p-2"><span class="text-gray-500">Daily usage:</span> <span class="font-medium">${item.prediction.daily_rate}/day</span></div>
        <div class="bg-surface-700/50 rounded-lg p-2"><span class="text-gray-500">Days left:</span> <span class="font-medium">${item.prediction.days_until_empty||'∞'}</span></div>
      </div>
      ${item.suggested_threshold?`<p class="text-xs text-gray-400 mt-2">💡 AI suggests threshold: <strong class="text-accent-400">${item.suggested_threshold}</strong></p>`:''}</div>`:''}
    ${item.transactions&&item.transactions.length?`<div class="card mb-4"><p class="text-sm font-semibold mb-3">📜 Recent Transactions</p>
      ${item.transactions.slice(0,5).map(t=>`<div class="flex justify-between items-center py-1.5 border-b border-white/5 text-sm">
        <span class="text-gray-400">${t.action_type}</span><span class="${t.quantity_change>0?'text-success-400':'text-danger-400'}">${t.quantity_change>0?'+':''}${t.quantity_change}</span>
        <span class="text-xs text-gray-600">${new Date(t.created_at).toLocaleDateString()}</span></div>`).join('')}</div>`:''}
    <div class="flex gap-2 mt-4">
      <button onclick="editItem(${item.id})" class="flex-1 py-3 rounded-xl bg-accent-500/10 border border-accent-500/20 text-accent-400 font-semibold hover:bg-accent-500/20 transition">✏️ Edit</button>
      <button onclick="deleteItem(${item.id})" class="py-3 px-6 rounded-xl bg-danger-500/10 border border-danger-500/20 text-danger-400 font-semibold hover:bg-danger-500/20 transition">🗑️</button>
    </div>`;
  navigate('detail');
}

// --- Form ---
function resetForm(){
  document.getElementById('f-id').value='';
  document.getElementById('f-name').value='';
  document.getElementById('f-qty').value='0';
  document.getElementById('f-thresh').value='5';
  document.getElementById('f-unit').value='pcs';
  document.getElementById('f-sku').value='';
  document.getElementById('f-desc').value='';
  document.getElementById('f-qr').checked=true;
  document.getElementById('form-title').textContent='Add New Item';
  loadCatDropdown();
}

async function editItem(id){
  const item=await api('/api/items/'+id);
  if(!item)return;
  document.getElementById('f-id').value=item.id;
  document.getElementById('f-name').value=item.name;
  document.getElementById('f-qty').value=item.quantity;
  document.getElementById('f-thresh').value=item.threshold;
  document.getElementById('f-unit').value=item.unit||'pcs';
  document.getElementById('f-sku').value=item.sku||'';
  document.getElementById('f-desc').value=item.description||'';
  document.getElementById('form-title').textContent='Edit Item';
  await loadCatDropdown();
  document.getElementById('f-cat').value=item.category_id||'';
  navigate('form');
}

async function saveItem(e){
  e.preventDefault();
  const id=document.getElementById('f-id').value;
  const data={name:document.getElementById('f-name').value,category_id:document.getElementById('f-cat').value||null,
    quantity:parseInt(document.getElementById('f-qty').value)||0,threshold:parseInt(document.getElementById('f-thresh').value)||5,
    unit:document.getElementById('f-unit').value||'pcs',sku:document.getElementById('f-sku').value,
    description:document.getElementById('f-desc').value,auto_qr:document.getElementById('f-qr').checked};
  const url=id?`/api/items/${id}`:'/api/items';
  const method=id?'PUT':'POST';
  const r=await api(url,{method,body:JSON.stringify(data)});
  if(r){toast(id?'Item updated':'Item created');navigate('inv');}
}

async function deleteItem(id){
  if(!confirm('Delete this item?'))return;
  await api(`/api/items/${id}`,{method:'DELETE'});
  toast('Item deleted');navigate('inv');
}

// --- Categories ---
async function loadCategories(){
  categories=await api('/api/categories')||[];
  const sel=document.getElementById('filter-cat');
  sel.innerHTML='<option value="">All</option>'+categories.map(c=>`<option value="${c.id}">${c.name} (${c.item_count})</option>`).join('');
}

async function loadCatDropdown(){
  if(!categories.length)categories=await api('/api/categories')||[];
  const sel=document.getElementById('f-cat');
  sel.innerHTML='<option value="">None</option>'+categories.map(c=>`<option value="${c.id}">${c.name}</option>`).join('');
}

// --- Scanner ---
function startScanner(){
  stopScanner();
  const container=document.getElementById('scanner-container');
  container.innerHTML='<div id="qr-reader" style="width:100%"></div>';
  try{
    scannerInstance=new Html5Qrcode("qr-reader");
    scannerInstance.start({facingMode:"environment"},{fps:10,qrbox:{width:250,height:250}},
      (text)=>{stopScanner();handleScan(text);},()=>{}).catch(()=>{
        container.innerHTML='<p class="text-center py-12 text-gray-500">📷 Camera not available.<br>Please allow camera access.</p>';
      });
  }catch(e){container.innerHTML='<p class="text-center py-12 text-gray-500">Scanner not supported in this browser.</p>';}
}

function stopScanner(){if(scannerInstance){try{scannerInstance.stop().catch(()=>{});}catch(e){}scannerInstance=null;}}

async function handleScan(text){
  const res=document.getElementById('scan-result');
  try{
    const data=JSON.parse(text);
    if(data.id){res.innerHTML=`<p class="text-success-400 font-semibold mb-2">✅ Item Found!</p><p class="text-sm">${data.name||'Item #'+data.id}</p>
      <button onclick="viewItem(${data.id})" class="mt-3 w-full py-2 bg-accent-500 text-white rounded-xl font-semibold">View Details</button>`;
      res.classList.remove('hidden');return;}
  }catch(e){}
  res.innerHTML=`<p class="text-warn-400 font-semibold">QR Data:</p><p class="text-sm text-gray-300 break-all">${text}</p>`;
  res.classList.remove('hidden');
}

// --- Analytics ---
async function loadAnalytics(){
  const data=await api('/api/analytics');
  if(!data)return;
  const ac=document.getElementById('analytics-content');
  ac.innerHTML=data.map(ins=>{
    if(ins.type==='summary')return`<div class="card"><div class="flex items-center justify-between mb-3"><span class="font-semibold">Inventory Health</span>
      <span class="text-2xl font-bold ${ins.health_score>=70?'text-success-400':ins.health_score>=40?'text-warn-400':'text-danger-400'}">${ins.health_score}%</span></div>
      <div class="w-full bg-surface-600 rounded-full h-3"><div class="h-3 rounded-full bg-gradient-to-r ${ins.health_score>=70?'from-emerald-400 to-emerald-500':ins.health_score>=40?'from-amber-400 to-amber-500':'from-red-400 to-red-500'}" style="width:${ins.health_score}%"></div></div>
      <div class="grid grid-cols-3 gap-2 mt-3 text-center text-sm"><div><p class="font-bold">${ins.total_items}</p><p class="text-xs text-gray-500">Total</p></div><div><p class="font-bold text-warn-400">${ins.low_stock}</p><p class="text-xs text-gray-500">Low</p></div><div><p class="font-bold text-danger-400">${ins.out_of_stock}</p><p class="text-xs text-gray-500">Out</p></div></div></div>`;
    if(ins.type==='critical_stock')return`<div class="card border-danger-500/20"><p class="font-semibold text-danger-400 mb-2">🚨 Critical Items</p>
      ${ins.items.map(i=>`<div class="flex justify-between py-1 text-sm"><span>${i.name}</span><span class="text-danger-400">${i.days?'~'+Math.round(i.days)+'d':'urgent'}</span></div>`).join('')}</div>`;
    if(ins.type==='threshold_adjustment')return`<div class="insight-card"><p class="font-semibold text-accent-400 mb-1">🤖 AI Recommendation</p><p class="text-sm text-gray-300">${ins.message}</p>
      <button onclick="applyThreshold(${ins.item_id},${ins.suggested_threshold})" class="mt-2 text-xs bg-accent-500/20 text-accent-400 px-3 py-1 rounded-lg hover:bg-accent-500/30 transition">Apply Suggestion</button></div>`;
    return'';
  }).join('');
}

async function applyThreshold(id,val){
  await api(`/api/items/${id}`,{method:'PUT',body:JSON.stringify({threshold:val})});
  toast('Threshold updated by AI');loadAnalytics();
}

// --- Utils ---
async function manualStockCheck(){
  await api('/api/check-stock',{method:'POST'});
  toast('Stock check completed');loadDashboard();
}

function closeModal(){document.getElementById('modal-overlay').classList.add('hidden');}

// --- Init ---
document.addEventListener('DOMContentLoaded',async()=>{
  await loadCategories();
  loadDashboard();
});
