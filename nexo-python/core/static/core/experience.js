'use strict';

// The same Django API and permissions power the real business and the private demo.
const toolGroups = [
  {name:'Día a día',icon:'grid',tone:'violet',modules:['Resumen','Ventas','Facturación']},
  {name:'Productos',icon:'box',tone:'mint',modules:['Inventario','Compras','Movimientos','Kardex','Almacenes']},
  {name:'Tu negocio',icon:'users',tone:'blue',modules:['Contactos','Reportes','Equipo y permisos','Bitácora','Configuración']}
];
const toolDescriptions = {'Resumen':'Lo importante de tu negocio','Ventas':'Lo que vendes, paso a paso','Facturación':'Tus facturas y cobros','Inventario':'Lo que tienes y cuánto te queda','Compras':'Los productos que recibes','Movimientos':'Entradas, salidas y correcciones','Kardex':'La historia de cada producto','Almacenes':'Dónde guardas tus productos','Contactos':'Tus clientes y proveedores','Reportes':'Información para decidir','Equipo y permisos':'Tus usuarios y sus permisos','Bitácora':'Quién hizo cada cambio','Configuración':'Adapta Nexo a tu negocio'};
Object.assign(iconPaths,{home:'m3 10 9-7 9 7v11h-6v-8H9v8H3z',chevron:'m9 5 7 7-7 7',more:'M5 12h.01M12 12h.01M19 12h.01',help:'M9 9a3 3 0 1 1 5 2c-2 1-2 2-2 3m0 3h.01M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20',spark:'m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z'});
const primaryLinks=[['Inicio','Resumen','home'],['Productos','Inventario','box'],['Vender','Ventas','buy'],['Más','Más','grid']];
state.saleStep=1;state.kardex=null;state.ledgerFilters={};state.ledgerLoading=false;
function resetExperience(){state.saleStep=1;state.saleInvoice=null;state.kardex=null;state.ledgerFilters={};state.ledgerLoading=false;state.ledgerError='';state.cartWarehouse=null;state.cartContact='';state.cartDue=iso();state.cartNote='';state.ledgerRequest=(state.ledgerRequest||0)+1;state.count=null;}
function primaryMarkup(){return primaryLinks.map(([label,view,ico])=>`<button class="primary-link ${state.view===view||(view==='Más'&&!['Resumen','Inventario','Ventas'].includes(state.view))?'active':''}" data-action="nav" data-id="${view}" ${state.view===view?'aria-current="page"':''}>${icon(ico,23)}<span>${label}</span>${view==='Ventas'&&state.cart.length?`<b class="cart-count">${state.cart.length}</b>`:''}</button>`).join('')}
function syncPrimaryNavigation(){$('#navigation').innerHTML=primaryMarkup();$('#mobile-navigation').innerHTML=primaryMarkup()}
function renderChrome(){
  if(state.view!=='Más'&&modules.find(m=>m[0]===state.view)?.[2]&&!admin())state.view='Resumen';
  $('#business-select').innerHTML=state.businesses.map(b=>`<option value="${b.id}" ${b.id===state.id?'selected':''}>${esc(b.name)}</option>`).join('');
  $('#role-label').textContent=roles[state.data.role];$('#profile-name').textContent=state.user.name;
  $('.avatar').textContent=state.user.name.slice(0,2).toUpperCase();
  if(DEMO)$('#demo-role').value=state.data.role;
  $('#footer-business').textContent=state.data.business.name+' · '+state.data.business.currency;
  syncPrimaryNavigation();
}
function navigate(view){
  const mod=modules.find(m=>m[0]===view);
  if(view!=='Más'&&(!mod||mod[2]&&!admin()))view='Resumen';
  state.view=view;state.query='';state.category='Todas';state.filter='Todos';
  if($('#modal').open)closeModal();
  renderChrome();render();window.scrollTo({top:0,behavior:'instant'});$('#page').focus({preventScroll:true});
  if(view==='Kardex')loadKardex();
}
function toolsView(){
  const count=modules.filter(m=>!m[2]||admin()).length;
  return heading('Todas tus herramientas','Encuentra lo que necesitas. Puedes volver al inicio cuando quieras.')+
    `<div class="helper-note">${icon('spark',23)}<div><b>${admin()?'Tus 13 módulos siguen aquí.':'Herramientas para tu trabajo diario.'}</b><span>Abre una categoría. Cada opción te explica para qué sirve.</span></div></div><div class="tool-groups">`+
    toolGroups.map((group,index)=>{const shown=group.modules.filter(name=>!modules.find(m=>m[0]===name)[2]||admin());if(!shown.length)return '';return `<details class="tool-group ${group.tone}" ${index===0||matchMedia('(min-width: 800px)').matches?'open':''}><summary><span class="group-title">${icon(group.icon,27)}${group.name}</span><small>${shown.length} herramientas</small></summary><div class="tool-list">${shown.map(name=>{const mod=modules.find(m=>m[0]===name);return `<button class="tool-card" data-action="nav" data-id="${name}"><span class="tool-icon">${icon(mod[1],25)}</span><span><b>${name==='Equipo y permisos'?'Equipo':name}</b><small>${toolDescriptions[name]}</small></span>${icon('chevron',18)}</button>`}).join('')}</div></details>`}).join('')+`</div><p class="footnote">${count} módulos disponibles para ${roles[state.data.role].toLowerCase()}. ${admin()?'Puedes administrar los accesos desde Equipo.':'Los precios y los permisos los administra el responsable del negocio.'}</p>`;
}
function taskCard(title,description,ico,action,id,tone=''){return `<button class="task-card ${tone}" data-action="${action}" data-id="${id}"><span class="task-icon">${icon(ico,30)}</span><span><b>${title}</b><small>${description}</small></span>${icon('chevron',23)}</button>`}
function overview(){
  const d=state.data,r=state.report,active=d.products.filter(p=>p.active),low=active.filter(p=>num(p.stock)<=num(p.minimum));
  const expiring=active.filter(p=>p.expiry&&p.expiry<=new Date(Date.now()+14*86400000).toISOString().slice(0,10)&&num(p.stock)>0);
  const receivable=admin()?num(r.receivable):d.invoices.reduce((n,i)=>n+num(i.balance),0);
  let dismissed=false;try{dismissed=localStorage.getItem('nexo-guide-dismissed')==='yes'}catch{}
  return `<div class="welcome-heading"><div><span class="eyebrow">${DEMO?'TU ESPACIO PARA PRACTICAR':'TU NEGOCIO, MÁS SIMPLE'}</span><h1>¿Qué necesitas hacer?</h1><p>Elige una tarea. Te acompañamos.</p></div><span class="today-label">${new Date().toLocaleDateString('es',{weekday:'long',day:'numeric',month:'long'})}</span></div>
  <div class="home-layout"><section class="home-tasks" aria-label="Tareas frecuentes">
  ${taskCard('Quiero vender','Registra una venta y crea su factura','buy','nav','Ventas','hero-task')}
  ${!dismissed?`<div class="first-tip">${icon('help',21)}<p><b>¿Es tu primera vez?</b> Toca «Quiero vender». Te guiaremos en cada paso.</p><button class="text-button" data-action="dismiss-guide">Entendido</button></div>`:''}
  <div class="secondary-tasks">${admin()?taskCard('Recibí productos','Registra lo que compraste','box','transaction','purchase','blue-task'):''}
  ${taskCard('Ver mis productos','Mira cuánto te queda','box','nav','Inventario','mint-task')}
  ${taskCard('Revisar cobros','Consulta lo que falta por pagar','invoice','nav','Facturación','peach-task')}</div>
  </section><section class="panel home-chart"><div class="panel-heading"><div><span class="eyebrow">UN VISTAZO A TU NEGOCIO</span><h2>Así van tus ventas</h2><p>${dateLabel(r.start+'T12:00:00')} — ${dateLabel(r.end+'T12:00:00')}</p></div><span class="chart-symbol">${icon('chart',26)}</span></div><div class="home-sales-total">${money(r.sales)}<small>${admin()?'Ventas netas':'Tus ventas'} · sin impuestos</small></div>${chart()}${admin()?`<button class="chart-link text-button" data-action="nav" data-id="Reportes">Ver mis reportes ${icon('chevron',17)}</button>`:''}</section></div>
  <section class="next-section"><div class="section-heading"><div><h2>Un momento para revisar</h2><p>Pequeñas tareas para mantener todo en orden.</p></div></div><div class="attention-grid">
  <article class="attention-card amber-card"><span class="attention-icon">${icon('box',27)}</span><div><h3>${low.length?`${low.length} productos por reponer`:'Tus productos están sobre el mínimo'}</h3><p>${low.length?'Algunos están por terminarse. Revisa cuánto te queda.':'Puedes consultar las cantidades en tu inventario.'}</p><button class="text-button" data-action="replenishment">${low.length?'Ver qué hace falta':'Ver existencias'} ${icon('chevron',16)}</button></div></article>
  <article class="attention-card mint-card"><span class="attention-icon">${icon('wallet',27)}</span><div><h3>${receivable?`${money(receivable)} por cobrar`:'Tus cobros están al día'}</h3><p>${receivable?'Son ventas que todavía no te han pagado por completo.':'Aquí aparecerán las ventas pendientes de pago.'}</p><button class="text-button" data-action="nav" data-id="Facturación">Revisar facturas ${icon('chevron',16)}</button></div></article>
  ${admin()?`<article class="attention-card violet-card"><span class="attention-icon">${icon('clock',27)}</span><div><h3>Cada producto tiene su historia</h3><p>El kardex te dice qué entró, qué salió y cuánto quedó.</p><button class="text-button" data-action="nav" data-id="Kardex">Abrir kardex ${icon('chevron',16)}</button></div></article>`:''}
  </div>${expiring.length?`<div class="helper-note warning spaced">${icon('alert')}<div><b>${expiring.length} productos requieren revisar su fecha.</b><span>Incluye productos vencidos o con vencimiento en los próximos 14 días.</span></div>${button('Revisar fechas','expiry','','secondary')}</div>`:''}</section>`;
}
function productImage(p,large=false){
  if(p.has_photo)return `<img class="product-photo ${large?'large':''}" src="${apiUrl(`/api/b/${state.id}/products/${p.id}/photo/?v=${p.version}`)}" alt="${esc(p.name)}" loading="lazy">`;
  if(DEMO&&p.demo_photo)return `<img class="product-photo catalog-photo ${large?'large':''}" src="${esc(p.demo_photo.src)}" alt="${esc(p.name)}" loading="lazy" decoding="async">`;
  const known=DEMO&&['CAFE-250','ARROZ-1K','ACEITE-500','LECHE-1L','GALLETAS','JABON','AGUA-600','PAPEL'].includes(p.sku);
  if(known)return `<img class="product-photo illustrated ${large?'large':''}" src="/static/core/products/${encodeURIComponent(p.sku.toLowerCase())}.svg" alt="Ilustración de ${esc(p.name)}" loading="lazy">`;
  return `<span class="product-placeholder tone-${p.category.length%4} ${large?'large':''}">${icon('box',large?44:24)}</span>`;
}
function photoCredit(p){
  if(!DEMO||p.has_photo||!p.demo_photo)return '';
  const f=p.demo_photo;
  return `<p class="photo-credit">Fotografía: <a href="${esc(f.source)}" target="_blank" rel="noopener">${esc(f.author)}</a> · <a href="${esc(f.license_url)}" target="_blank" rel="noopener">${esc(f.license)}</a>. Tamaño y compresión adaptados para Nexo. Los precios y las existencias son de ejemplo.</p>`;
}
function inventory(){
  const products=state.data.products;
  const shown=products.filter(p=>(state.filter==='Archivados'?!p.active:p.active)&&(state.category==='Todas'||p.category===state.category)&&(state.filter!=='Por reponer'||num(p.stock)<=num(p.minimum))&&(state.filter!=='Agotados'||num(p.stock)===0)&&[p.name,p.sku,p.location].join(' ').toLowerCase().includes(state.query.toLowerCase()));
  return heading('Mis productos','Mira lo que tienes y cuánto te queda.',admin()?button('Nuevo producto','product','','primary','plus'):'')+
  `<div class="inventory-shortcuts">${admin()?button('Contar productos','count','','secondary','check')+button('Qué hace falta','replenishment','','secondary','alert')+button('Ver kardex','nav','Kardex','secondary','clock')+button('Exportar','export','inventory','secondary','download'):''}</div><section class="panel inventory-panel"><div class="filters"><label class="search">${icon('search')}<input id="search" value="${esc(state.query)}" placeholder="Nombre, código o ubicación…" aria-label="Buscar productos"></label><select id="category-filter" aria-label="Categoría">${['Todas',...new Set(products.map(p=>p.category))].map(c=>`<option ${state.category===c?'selected':''}>${esc(c)}</option>`).join('')}</select><select id="status-filter" aria-label="Estado">${['Todos','Por reponer','Agotados','Archivados'].map(c=>`<option ${state.filter===c?'selected':''}>${c}</option>`).join('')}</select></div><div class="table-caption">${shown.length} productos <span>Toca un nombre para ver sus detalles.</span></div>
  <div class="inventory-cards">${shown.map(p=>`<article class="inventory-product">${productImage(p,true)}<div class="inventory-product-body"><small>${esc(p.category)}</small><button class="product-name" data-action="product-detail" data-id="${p.id}">${esc(p.name)}</button><div class="stock-number"><strong>${fmt(p.stock)}</strong><span>${esc(p.unit)} disponibles</span></div><div class="product-card-bottom">${stockBadge(p)}<b>${money(p.price)}</b></div></div><button class="product-card-open" data-action="product-detail" data-id="${p.id}" aria-label="Ver detalles de ${esc(p.name)}">Ver producto ${icon('chevron',16)}</button></article>`).join('')}</div>${!shown.length?empty('No hay productos en esta selección','Prueba con otro nombre o cambia los filtros.',admin()?button('Agregar producto','product','','primary','plus'):''):''}</section>`;
}
function available(p){return num(p?.stocks.find(s=>String(s.warehouse)===String(state.cartWarehouse||state.data.warehouses.find(w=>w.active)?.id))?.quantity)}
function saleTotals(){
  const taxRate=BigInt(Math.round(num(state.data.business.tax_rate)*100));let subtotal=0n,tax=0n;
  const lines=state.cart.map(l=>{const cents=(BigInt(Math.round(l.quantity*1000))*BigInt(Math.round(l.price*100))+500n)/1000n;const lineTax=(cents*taxRate+5000n)/10000n;subtotal+=cents;tax+=lineTax;return {...l,total:Number(cents+lineTax)/100,subtotal:Number(cents)/100}});
  return {lines,subtotal:Number(subtotal)/100,tax:Number(tax)/100,total:Number(subtotal+tax)/100};
}
function saleSteps(){return `<ol class="sale-steps" aria-label="Pasos de la venta">${['Productos','Revisar','Factura'].map((name,i)=>`<li class="${state.saleStep===i+1?'current':state.saleStep>i+1?'complete':''}" ${state.saleStep===i+1?'aria-current="step"':''}><span>${state.saleStep>i+1?icon('check',18):i+1}</span><b>${name}</b></li>`).join('')}</ol>`}
function cartLines(review=false){const totals=saleTotals();return totals.lines.map(l=>{const p=state.data.products.find(p=>p.id===l.id);return `<div class="guided-cart-line">${review?productImage(p):''}<div class="cart-product-name"><b>${esc(l.name)}</b><small>${money(l.price)} por ${esc(l.unit)}</small></div><div class="quantity-control"><button type="button" data-action="cart-minus" data-id="${l.id}" aria-label="Restar ${esc(l.name)}">−</button><input class="cart-qty" data-id="${l.id}" aria-label="Cantidad de ${esc(l.name)}" type="number" step="0.001" min="0.001" max="${available(p)}" value="${l.quantity}"><button type="button" data-action="cart-plus" data-id="${l.id}" aria-label="Sumar ${esc(l.name)}">+</button></div><strong>${money(l.subtotal)}</strong><button type="button" class="icon-button" data-action="cart-remove" data-id="${l.id}" aria-label="Quitar ${esc(l.name)}">×</button></div>`}).join('')}
function totalsMarkup(t){return `<div class="totals"><div><span>Subtotal</span><b>${money(t.subtotal)}</b></div><div><span>Impuestos (${fmt(state.data.business.tax_rate)}%)</span><b>${money(t.tax)}</b></div><div class="grand-total"><span>Total de la venta</span><strong>${money(t.total)}</strong></div></div>`}
function sales(){
  const d=state.data;state.cartWarehouse ||= d.warehouses.find(w=>w.active)?.id;state.saleStep ||= 1;
  const title=state.saleStep===3?'Tu venta está lista':state.saleStep===2?'Revisa tu venta':'¿Qué vas a vender?';
  const intro=state.saleStep===3?'La factura ya está creada. Puedes registrar el pago recibido.':state.saleStep===2?'Comprueba los productos y las cantidades antes de confirmar.':'Toca un producto para agregarlo. Después podrás revisar todo.';
  const head=heading(title,intro,button('Mis ventas','sales-history','','secondary','clock'))+saleSteps();
  if(state.saleStep===3){const i=d.invoices.find(x=>x.id===state.saleInvoice);return head+`<section class="sale-finished panel"><span class="success-check">${icon('check',42)}</span><h2>Venta guardada</h2><p>Actualizamos las existencias y creamos tu factura.</p>${i?`<div class="finished-invoice"><span>${esc(i.number)}</span><strong>${money(i.total)}</strong>${pill(...statuses[i.status])}</div><div class="stack-buttons">${num(i.balance)>0?button('Ya recibí el pago','payment',i.id,'primary','wallet'):''}${button('Ver mi factura','invoice-detail',i.id,'secondary','invoice')}<a class="button secondary" href="${apiUrl(`/api/b/${state.id}/invoices/${i.id}/pdf/`)}" target="_blank" rel="noopener">${icon('download')} Abrir / imprimir PDF</a></div>`:''}<button class="text-button spaced" data-action="new-sale">Empezar otra venta ${icon('chevron',18)}</button><p class="form-note spaced">Registrar un cobro indica que ya recibiste el dinero.</p></section>`}
  const t=saleTotals();
  if(state.saleStep===2)return head+`<div class="review-layout"><section class="panel review-products"><div class="panel-heading"><h2>Productos en esta venta (${state.cart.length})</h2></div><form id="sale-form" class="review-form">${cartLines(true)}<div class="form-grid spaced">${select('warehouse','De dónde salen los productos',d.warehouses.filter(w=>w.active).map(w=>[w.id,w.name]),state.cartWarehouse)}${select('contact','Cliente (opcional)',[['','Consumidor final'],...d.contacts.filter(c=>c.kind==='customer').map(c=>[c.id,c.name])],state.cartContact||'')}</div><details class="extra-options"><summary>Fecha de pago y nota (opcional)</summary>${input('due_date','Fecha límite de pago',state.cartDue||iso(),'date','required min="'+iso()+'"')}${area('note','Nota para esta venta',state.cartNote||'')}</details></form></section><section class="panel review-confirm"><h2>Antes de guardar</h2>${totalsMarkup(t)}<div class="impact-note"><b>Al confirmar:</b><ul>${state.cart.map(l=>`<li>${icon('box',18)}<span>Se descontarán <b>${fmt(l.quantity)} ${esc(l.unit)}</b> de ${esc(l.name)}.</span></li>`).join('')}<li>${icon('invoice',18)}<span>Se creará una factura de <b>${money(t.total)}</b>.</span></li></ul></div><button class="button primary full confirm-sale" data-action="confirm-sale" ${!state.cart.length?'disabled':''}>${icon('check',23)} Confirmar venta · ${money(t.total)}</button>${button('Seguir agregando productos','sale-back','','secondary full','plus')}<p class="form-note">El cobro se registra en el siguiente paso.</p></section></div>`;
  const products=d.products.filter(p=>p.active&&[p.name,p.sku,p.category].join(' ').toLowerCase().includes(state.query.toLowerCase())&&(state.category==='Todas'||state.category===p.category));
  return head+`<div class="pos-layout"><section><label class="search pos-search">${icon('search')}<input id="search" value="${esc(state.query)}" placeholder="Busca un producto o escanea su código…" aria-label="Buscar producto"></label><div class="chips">${['Todas',...new Set(d.products.filter(p=>p.active).map(p=>p.category))].map(c=>`<button class="chip ${state.category===c?'active':''}" data-action="category" data-id="${esc(c)}">${esc(c==='Todas'?'Todos':c)}</button>`).join('')}</div><div class="product-grid">${products.map(p=>{const qty=available(p),expired=p.expiry&&p.expiry<iso();return `<button class="product-tile" data-action="cart-add" data-id="${p.id}" ${qty<=0||expired?'disabled':''}>${productImage(p,true)}<h3>${esc(p.name)}</h3><small>${expired?'Vencido':qty>0?`${fmt(qty)} ${esc(p.unit)} disponibles`:'Sin existencias aquí'}</small><div><strong>${money(p.price)}</strong><span class="add-product">${icon('plus',20)}</span></div></button>`}).join('')}</div>${!products.length?empty('No encontramos ese producto','Prueba con otro nombre o código.'):''}</section><section class="panel sale-cart"><div class="panel-heading"><h2>Tu venta (${state.cart.length})</h2>${state.cart.length?'<button class="text-button danger" data-action="cart-clear">Vaciar</button>':''}</div><form id="sale-form" class="cart-form">${select('warehouse','De dónde salen los productos',d.warehouses.filter(w=>w.active).map(w=>[w.id,w.name]),state.cartWarehouse)}<input type="hidden" name="contact" value="${esc(state.cartContact||'')}"><div class="cart-lines">${state.cart.length?cartLines():`<div class="cart-empty">${icon('buy',35)}<p>Toca un producto para empezar.</p></div>`}</div>${totalsMarkup(t)}<button class="button primary full" type="submit" ${!state.cart.length?'disabled':''}>Revisar mi venta ${icon('chevron',19)}</button><p class="form-note">Podrás revisar todo antes de guardar.</p></form></section></div>${state.cart.length?`<div class="mobile-cart-bar"><span>${state.cart.length} productos <b>${money(t.total)}</b></span><button class="button primary" data-action="review-sale">Revisar ${icon('chevron',18)}</button></div>`:''}`;
}
function validateSale(){
  const f=$('#sale-form');if(f&&!f.reportValidity())return false;
  if(!state.cart.length){toast('Agrega al menos un producto.');return false;}
  for(const l of state.cart){const p=state.data.products.find(p=>p.id===l.id);if(!p||!Number.isFinite(l.quantity)||l.quantity<=0||Math.abs(l.quantity*1000-Math.round(l.quantity*1000))>1e-6)throw Error('Revisa las cantidades. Puedes usar hasta tres decimales.');if(l.quantity>available(p))throw Error(`Te quedan ${fmt(available(p))} ${p.unit} de ${p.name} en este almacén.`);if(p.expiry&&p.expiry<iso())throw Error(`${p.name} está vencido.`)}
  return true;
}
function reviewSale(){if(!validateSale())return;preserveCart();state.saleStep=2;render();window.scrollTo({top:0,behavior:'instant'});$('#page').focus({preventScroll:true})}
function enhanceTables(){document.querySelectorAll('#page table,#modal table').forEach(table=>{const labels=[...table.querySelectorAll('thead th')].map(th=>th.textContent.trim());if(!labels.length)return;table.classList.add('responsive-table');table.querySelectorAll('tbody tr').forEach(tr=>[...tr.children].forEach((td,i)=>td.dataset.label=labels[i]||'Acciones'))})}
function replenishment(){
  const list=state.data.products.filter(p=>p.active&&num(p.stock)<=num(p.minimum));
  openModal('¿Qué hace falta?',`<div class="helper-note"><div><b>Prepara tu próxima compra.</b><span>Estas cantidades sirven para alcanzar el mínimo que configuraste. Revisa lo que necesitas antes de comprar.</span></div></div>${list.length?list.map(p=>{const needed=Math.max(0,num(p.minimum)-num(p.stock));return `<div class="replenish-row">${productImage(p)}<div><b>${esc(p.name)}</b><small>Te quedan ${fmt(p.stock)} ${esc(p.unit)} · mínimo ${fmt(p.minimum)}</small><span class="need-amount">${needed?`Faltan ${fmt(needed)} ${esc(p.unit)} para el mínimo`:'Está justo en el mínimo'}</span></div>${button('Ver producto','product-detail',p.id,'secondary')}</div>`}).join(''):empty('Todo está sobre el mínimo','Puedes ajustar el mínimo de cada producto desde su ficha.')}${admin()?`<p class="form-note spaced">Cuando los productos lleguen, usa «Recibí productos» para registrar las cantidades reales.</p>${button('Ya recibí productos','transaction','purchase','primary full spaced','box')}`:''}`,'Una ayuda para evitar que tus productos se terminen.',true);
}
function accountModal(){openModal('Mi cuenta',`<div class="account-info"><span class="avatar">${esc(state.user.name.slice(0,2))}</span><div><h3>${esc(state.user.name)}</h3><p>${roles[state.data.role]} · ${esc(state.data.business.name)}</p></div></div><div class="stack-buttons">${button(DEMO?'Acerca de mi prueba':'Cambiar contraseña','password','','secondary','shield')}${DEMO?`<a class="button secondary" href="${DEMO_BASE==='/demo'?'/demo/ferreteria/':'/demo/'}">${DEMO_BASE==='/demo'?'Probar una ferretería':'Probar una tienda'}</a>`:''}${admin()&&!DEMO?button('Crear otro negocio','business','','secondary','plus'):''}<button class="button secondary danger" data-action="logout">Cerrar sesión</button></div>`)}
function helpModal(){
  const topic=toolDescriptions[state.view]||'Tus herramientas, organizadas por tareas';
  openModal('Te acompañamos',`<p class="help-context">Estás en <b>${state.view==='Más'?'Todas tus herramientas':esc(state.view)}</b>: ${topic.toLowerCase()}.</p><div class="help-steps"><div><span>1</span><div><b>Para vender</b><p>Elige productos, revisa las cantidades y confirma. Después registra el pago que recibiste.</p></div></div><div><span>2</span><div><b>Para recibir productos</b><p>En Compras, agrega solo lo que llegó a tu negocio. El sistema sumará esas cantidades.</p></div></div><div><span>3</span><div><b>Para entender las existencias</b><p>«Disponible» es lo que tienes. «Por reponer» avisa que un producto llegó al mínimo. El kardex muestra cómo cambió la cantidad.</p></div></div></div><details class="extra-options"><summary>Palabras que verás en Nexo</summary><p><b>Inventario:</b> los productos que tienes.</p><p><b>Almacén:</b> el lugar donde los guardas.</p><p><b>Kardex:</b> el historial de entradas, salidas y saldo de un producto.</p><p><b>Saldo por cobrar:</b> el dinero que aún falta recibir.</p><p><b>Costo promedio:</b> lo que te ha costado cada unidad, considerando las compras.</p></details>${button('Volver a lo que estaba haciendo','close-modal','','primary full spaced')}`,'Puedes consultar esta ayuda cuando lo necesites.');
}

// Read-only kardex: filters are separate from general report dates and stock writes.
function kardexView(){
  const f=state.ledgerFilters;const products=state.data.products,warehouses=state.data.warehouses;
  f.product ||= products[0]?.id||'';f.warehouse ||= warehouses[0]?.id||'';f.start ||= iso().slice(0,7)+'-01';f.end ||= iso();
  const k=state.kardex;
  return heading('Kardex','La historia de un producto: qué entró, qué salió y cuánto quedó.',k?button('Exportar kardex','kardex-export','','secondary','download'):'')+
  `<div class="helper-note"><span class="tool-icon">${icon('clock',25)}</span><div><b>Elige un producto y el lugar donde lo guardas.</b><span>El saldo inicial es lo que tenías al comenzar. Cada entrada suma; cada salida resta.</span></div></div><section class="panel ledger-filters"><form id="kardex-form"><div class="form-grid">${select('product','Producto',products.map(p=>[p.id,p.name+(p.active?'':' · archivado')]),f.product)}${select('warehouse','Almacén',warehouses.map(w=>[w.id,w.name]),f.warehouse)}${input('start','Desde',f.start,'date','required')}${input('end','Hasta',f.end,'date','required')}</div><button type="submit" class="button primary" ${!products.length||state.ledgerLoading?'disabled':''}>${icon('search',19)} Ver historial</button></form></section>
  ${state.ledgerError?`<div class="error-banner" role="alert">${esc(state.ledgerError)}</div>`:''}
  ${state.ledgerLoading?'<div class="loading-surface compact"><span class="loader"></span><p>Buscando su historia…</p></div>':k?`<div class="ledger-caption"><h2>${esc(k.product.name)}</h2><p>${esc(k.warehouse.name)} · ${dateLabel(k.start+'T12:00:00')} — ${dateLabel(k.end+'T12:00:00')}</p></div><div class="stats ledger-stats">${stat('Al comenzar',fmt(k.opening),k.product.unit,'box')}${stat('Entraron',fmt(k.incoming),k.product.unit,'plus')}${stat('Salieron',fmt(k.outgoing),k.product.unit,'move')}${stat('Al terminar',fmt(k.closing),k.product.unit,'check')}</div><section class="panel"><div class="panel-heading"><h2>Entradas y salidas</h2><span class="muted">${k.total_rows} movimientos</span></div>${k.rows.length?`<div class="table-scroll"><table class="ledger-table"><thead><tr><th>Fecha / documento</th><th>Qué ocurrió</th><th>Entradas</th><th>Salidas</th><th>Quedaron</th><th>Costo promedio</th></tr></thead><tbody>${k.rows.map(row=>`<tr><td><b>${dateLabel(row.date)}</b><small>${esc(row.document)}</small></td><td><b>${kinds[row.kind]}</b><small>${esc(row.note||row.reference||'Sin nota')} · ${esc(row.actor)}</small></td><td class="numeric incoming">${num(row.incoming)?'+'+fmt(row.incoming):'—'}</td><td class="numeric outgoing">${num(row.outgoing)?'−'+fmt(row.outgoing):'—'}</td><td class="numeric ledger-balance">${fmt(row.balance)}<small>${esc(k.product.unit)}</small></td><td class="numeric">${row.average_cost===null?'Sin registro':new Intl.NumberFormat('es-US',{style:'currency',currency:state.data.business.currency,minimumFractionDigits:4,maximumFractionDigits:4}).format(num(row.average_cost))}</td></tr>`).join('')}</tbody></table></div>`:empty('No hubo movimientos en estas fechas','El saldo se conserva. Prueba otro período para ver movimientos anteriores.')}<div class="ledger-pagination"><button class="button secondary" data-action="kardex-page" data-id="${k.page-1}" ${k.page===1?'disabled':''}>Anterior</button><span>Página ${k.page} de ${k.pages}</span><button class="button secondary" data-action="kardex-page" data-id="${k.page+1}" ${k.page===k.pages?'disabled':''}>Siguiente</button></div></section><p class="footnote">Cantidades en ${esc(k.product.unit)}. El costo es el promedio registrado al realizar cada movimiento; no es el precio de venta. La exportación incluye todo el período seleccionado.</p>`:!products.length?empty('Primero agrega un producto','Su historia comenzará con la primera entrada.'):''}`;
}
async function loadKardex(page=1){
  if(!admin()||!state.data.products.length)return;
  const id=state.id,request=(state.ledgerRequest||0)+1;state.ledgerRequest=request;state.ledgerLoading=true;state.ledgerError='';state.kardex=null;render();
  try{const result=await api(`/api/b/${id}/kardex/?${new URLSearchParams({...state.ledgerFilters,page})}`);if(request!==state.ledgerRequest||id!==state.id)return;state.kardex=result;}
  catch(err){if(request===state.ledgerRequest)state.ledgerError=err.message}
  finally{if(request===state.ledgerRequest){state.ledgerLoading=false;if(state.view==='Kardex')render()}}
}

// Physical count: inspect a server snapshot, then confirm a difference against that exact snapshot.
async function countModal(productId){
  if(!admin())return;
  const products=state.data.products.filter(p=>p.active);if(!products.length){toast('Agrega un producto antes de contar.');return;}
  state.count={product:num(productId)||products[0].id,warehouse:state.data.warehouses.find(w=>w.active)?.id,counted:'',step:1,key:crypto.randomUUID()};
  renderCount();await fetchCount();
}
async function fetchCount(){
  const count=state.count;if(!count)return;count.snapshot=null;count.step=1;count.counted='';renderCount();
  try{const snapshot=await api(`/api/b/${state.id}/stock-snapshot/?${new URLSearchParams({product:count.product,warehouse:count.warehouse})}`);if(state.count!==count)return;count.snapshot=snapshot;count.counted=String(snapshot.quantity);count.key=crypto.randomUUID();renderCount();}
  catch(err){if(state.count===count){count.error=err.message;renderCount()}}
}
function renderCount(){
  state.modalType='count';
  const c=state.count,p=state.data.products.find(p=>p.id===c.product);const diff=c.snapshot?Math.round((num(c.counted)-num(c.snapshot.quantity))*1000)/1000:0;
  openModal(c.step===2?'Revisa tu conteo':'¿Cuántos tienes?',`<form id="count-form" class="form-stack">${c.step===1?`<div class="form-grid">${select('product','Producto',state.data.products.filter(p=>p.active).map(p=>[p.id,p.name]),c.product)}${select('warehouse','Dónde estás contando',state.data.warehouses.filter(w=>w.active).map(w=>[w.id,w.name]),c.warehouse)}</div>`:''}<div class="count-product">${productImage(p)}<div><h3>${esc(p.name)}</h3><p>${esc(state.data.warehouses.find(w=>w.id===c.warehouse)?.name)}</p></div></div>${c.snapshot?`<div class="count-values"><div><span>Cantidad registrada</span><strong>${fmt(c.snapshot.quantity)}</strong><small>${esc(p.unit)}</small></div><label class="field">Cantidad que contaste<input name="counted" type="number" min="0" step="0.001" max="999999999" value="${esc(c.counted)}" required ${c.step===2?'readonly':''}><small>${esc(p.unit)}</small></label></div>${c.step===2?`<div class="impact-note"><b>${diff>0?'Se sumarán':diff<0?'Se descontarán':'La cantidad coincide'} ${diff?fmt(Math.abs(diff))+' '+esc(p.unit):''}.</b><p>${diff?'Guardaremos un ajuste y aparecerá en el kardex.':'No hace falta registrar un ajuste.'}</p></div>`:`<p class="helper-note compact">Cuenta las unidades que tienes físicamente. Podrás revisar la diferencia antes de guardar.</p>`}${c.step===1?area('note','Motivo del conteo',c.note||'Conteo físico de productos',true):`<p class="form-note">Motivo: ${esc(c.note)}</p>`}<div class="stack-buttons"><button type="submit" class="button primary">${c.step===1?'Revisar cambio':diff?'Guardar conteo':'Terminar sin cambios'}</button>${c.step===2?button('Corregir cantidad','count-back','','secondary'):button('Dejar para después','close-modal','','secondary')}</div>${button('Actualizar cantidad registrada','count-refresh','','text-button')}`:c.error?`<div class="form-error" role="alert">${esc(c.error)}</div>${button('Volver a intentar','count-refresh','','secondary')}`:'<div class="loading-surface compact"><span class="loader"></span><p>Consultando las existencias…</p></div>'}</form>`,'Revisa las cantidades del producto y del almacén seleccionados.');
}
async function experienceAction(action,id,btn){
  if(action==='help'){helpModal();return true;}
  if(action==='account'){accountModal();return true;}
  if(action==='logout'){$('#logout-form').submit();return true;}
  if(action==='dismiss-guide'){try{localStorage.setItem('nexo-guide-dismissed','yes')}catch{}btn.closest('.first-tip').remove();return true;}
  if(action==='replenishment'){replenishment();return true;}
  if(action==='expiry'){const list=state.data.products.filter(p=>p.active&&p.expiry&&p.expiry<=new Date(Date.now()+14*86400000).toISOString().slice(0,10)&&num(p.stock)>0);openModal('Fechas por revisar',list.map(p=>`<div class="replenish-row">${productImage(p)}<div><b>${esc(p.name)}</b><small>Vence: ${dateLabel(p.expiry+'T12:00:00')}</small>${pill(p.expiry<iso()?'Vencido':'Próximo a vencer',p.expiry<iso()?'red':'amber')}</div>${button('Ver','product-detail',p.id,'secondary')}</div>`).join(''),'Revisa el estado del producto antes de venderlo.');return true;}
  if(action==='review-sale'){reviewSale();return true;}
  if(action==='sale-back'){preserveCart();state.saleStep=1;render();return true;}
  if(action==='new-sale'){state.saleStep=1;state.saleInvoice=null;state.cartContact='';state.cartDue=iso();navigate('Ventas');return true;}
  if(action==='confirm-sale'){
    if(!validateSale())return true;preserveCart();
    await save('document',{warehouse:state.cartWarehouse,contact:state.cartContact||'',due_date:state.cartDue||iso(),note:state.cartNote||'',request_key:state.cartKey||=crypto.randomUUID(),kind:'sale',lines:state.cart.map(l=>({product:l.id,quantity:String(l.quantity),price:String(l.price)}))});return true;
  }
  if(action==='open-kardex'){state.ledgerFilters.product=id;state.kardex=null;navigate('Kardex');return true;}
  if(action==='kardex-page'){await loadKardex(num(id));return true;}
  if(action==='kardex-export'){if(state.kardex)location.assign(apiUrl(`/api/b/${state.id}/kardex/?${new URLSearchParams({product:state.kardex.product.id,warehouse:state.kardex.warehouse.id,start:state.kardex.start,end:state.kardex.end,format:'csv'})}`));return true;}
  if(action==='count'){await countModal(id);return true;}
  if(action==='count-refresh'){state.count.error='';await fetchCount();return true;}
  if(action==='count-back'){state.count.step=1;renderCount();return true;}
  return false;
}
async function experienceSubmit(form,fd){
  if(form.id==='kardex-form'){state.ledgerFilters={...fd};await loadKardex();return true;}
  if(form.id==='count-form'){
    const c=state.count;if(!c?.snapshot)return true;
    if(c.step===1){c.counted=fd.counted;c.note=fd.note;c.step=2;renderCount();return true;}
    const delta=Math.round((num(c.counted)-num(c.snapshot.quantity))*1000)/1000;
    if(!delta){closeModal();toast('La cantidad coincide. No se necesitó un ajuste.');return true;}
    await save('document',{kind:'adjustment',warehouse:c.warehouse,request_key:c.key,note:c.note,lines:[{product:c.product,quantity:String(delta),counted:String(c.counted),expected:String(c.snapshot.quantity),last_movement:c.snapshot.last_movement}]});return true;
  }
  return false;
}
document.addEventListener('change',async event=>{
  const el=event.target;
  if(el.closest('#count-form')&&['product','warehouse'].includes(el.name)){state.count={...state.count,[el.name]:num(el.value),error:''};await fetchCount()}
  if(el.closest('#sale-form')&&el.name==='warehouse'){preserveCart();render()}
});
new MutationObserver(()=>enhanceTables()).observe($('#modal-body'),{childList:true});
