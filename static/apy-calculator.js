/* LP scenario calculator. All values stay in the browser. */
(function () {
  'use strict';
  const modal = document.getElementById('lp-apy-modal');
  if (!modal) return;
  const byId = id => document.getElementById(id);
  const principalInput = byId('apy-principal'), rateInput = byId('apy-apr');
  const state = {frequency:365, days:365, mode:'compound'};
  let chart;
  const money = n => Number.isFinite(n) ? new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(n) : '—';
  const percent = n => Number.isFinite(n) ? (n*100).toFixed(2)+'%' : '—';
  // Reinvest only at completed periods; accrue the remaining days as simple interest.
  function values(principal, rate, days, frequency) {
    const periods=days*frequency/365, whole=Math.floor(periods+1e-10), rest=Math.max(0,periods-whole);
    const simple=principal*(1+rate*days/365);
    const compound=principal*Math.pow(1+rate/frequency,whole)*(1+rate/frequency*rest);
    return {simple,compound};
  }
  function read() {
    const principal=principalInput.valueAsNumber, rate=rateInput.valueAsNumber/100;
    const valid=Number.isFinite(principal)&&principal>=0&&Number.isFinite(rate)&&rate>=0;
    return {principal,rate,valid:valid&&Number.isFinite(values(principal,rate,365,state.frequency).compound)};
  }
  function renderChart(principal,rate,valid) {
    if (!window.Chart || !modal.classList.contains('visible')) return;
    const styles=getComputedStyle(document.body), color=name=>styles.getPropertyValue(name).trim();
    const days=Array.from({length:Math.min(state.days,120)+1},(_,i)=>state.days*i/Math.min(state.days,120));
    const datasets=['simple','compound'].map((mode,i)=>({
      label:i?'复投':'不复投',
      data:days.map(day=>({x:day,y:valid?values(principal,rate,day,state.frequency)[mode]:null})),
      borderColor:color(i?'--green':'--blue'),backgroundColor:'transparent',
      borderWidth:state.mode===mode?3:1.7,borderDash:i?[]:[5,4],pointRadius:0,pointHoverRadius:4,tension:0,fill:false
    }));
    if (!chart) chart=new Chart(byId('apy-growth-chart'),{type:'line',data:{datasets},options:{
      responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:'index',intersect:false},
      plugins:{legend:{display:false},tooltip:{callbacks:{
        title:items=>'第 '+Number(items[0].parsed.x.toFixed(1))+' 天',
        label:item=>item.dataset.label+' · '+money(item.parsed.y)
      }}},
      scales:{x:{type:'linear',min:0,max:state.days,ticks:{maxTicksLimit:6,callback:n=>Number(n.toFixed(1))+' 天'},grid:{display:false}},
      y:{ticks:{maxTicksLimit:5,callback:n=>'$'+new Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:1}).format(n)},border:{display:false}}}
    }});
    chart.data.datasets=datasets;chart.options.scales.x.max=state.days;
    ['x','y'].forEach(axis=>{chart.options.scales[axis].ticks.color=color('--text3');chart.options.scales[axis].grid.color=color('--border');});
    chart.update('none');
  }
  function update() {
    const {principal,rate,valid}=read();
    const current=valid?values(principal,rate,state.days,state.frequency):{simple:NaN,compound:NaN};
    const total=current[state.mode], profit=total-principal;
    const annual=valid?Math.pow(1+rate/state.frequency,state.frequency)-1:NaN;
    byId('apy-input-status').textContent=valid?'':'请输入有效的非负金额和年化收益率。';
    byId('apy-effective').textContent=percent(annual);
    byId('apy-result-label').textContent=(state.days===365?'1 年':state.days+' 天')+' · '+(state.mode==='compound'?'复投':'不复投')+'后总额';
    byId('apy-year-total').textContent=money(total);
    byId('apy-year-profit').textContent=money(profit);
    byId('apy-roi').textContent=percent(valid?(principal===0?0:profit/principal):NaN);
    byId('apy-extra').textContent=money(current.compound-current.simple);
    byId('apy-total-heading').textContent=state.mode==='compound'?'复投后总额':'不复投后总额';
    modal.querySelectorAll('#apy-results tr').forEach(row=>{
      const days=Number(row.dataset.days), v=valid?values(principal,rate,days,state.frequency):{simple:NaN,compound:NaN};
      row.querySelector('.simple-profit').textContent=money(v.simple-principal);
      row.querySelector('.compound-profit').textContent=money(v.compound-principal);
      row.querySelector('.compound-total').textContent=money(v[state.mode]);
      row.classList.toggle('is-selected',days===state.days);
      row.querySelector('.simple-profit').classList.toggle('is-emphasized',state.mode==='simple');
      row.querySelector('.compound-profit').classList.toggle('is-emphasized',state.mode==='compound');
    });
    renderChart(principal,rate,valid);
  }
  [principalInput,rateInput].forEach(input=>{input.addEventListener('input',update);input.addEventListener('change',update);});
  [['mode','mode'],['frequency','frequency'],['period','days']].forEach(([attr,key])=>{
    modal.querySelectorAll('[data-'+attr+']').forEach(button=>button.addEventListener('click',()=>{
      state[key]=key==='mode'?button.dataset[attr]:Number(button.dataset[attr]);
      modal.querySelectorAll('[data-'+attr+']').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
      update();
    }));
  });
  modal.addEventListener('keydown',event=>{
    if(event.key!=='Tab')return;
    const elements=Array.from(modal.querySelectorAll('button,input')).filter(el=>!el.disabled);
    const first=elements[0],last=elements[elements.length-1];
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
  });
  window.addEventListener('themechange',update);
  window.lpApy={open(){update();principalInput.focus();principalInput.select();}};
  update();
})();
