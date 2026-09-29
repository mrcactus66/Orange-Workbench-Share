(function () {
  var themeIcons = {
    sun: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.5"></circle><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.65 17.65l1.42 1.42M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.65 6.35l1.42-1.42"></path></svg>',
    moon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.2 15.1A8.5 8.5 0 0 1 8.9 3.8 8.5 8.5 0 1 0 20.2 15.1Z"></path></svg>'
  };
  function applyThemeLabel() {
    var button = document.getElementById('theme-toggle');
    if (!button) return;
    var dark = document.body.classList.contains('theme-dark');
    button.setAttribute('aria-label', dark ? '切换到浅色主题' : '切换到深色主题');
    button.setAttribute('aria-pressed', dark ? 'true' : 'false');
    button.title = dark ? '切换到浅色主题' : '切换到深色主题';
    button.innerHTML = dark ? themeIcons.moon : themeIcons.sun;
  }
  window.toggleTheme = function () {
    var dark = document.body.classList.toggle('theme-dark');
    localStorage.setItem('theme', dark ? 'dark' : 'light');
    applyThemeLabel();
    window.dispatchEvent(new Event('themechange'));
  };
  if (localStorage.getItem('theme') === 'dark') document.body.classList.add('theme-dark');
  applyThemeLabel();
  window.addEventListener('themechange', applyThemeLabel);
})();

// LP-only progressive presentation; accounting and chart series remain route-owned.
(function () {
  if (!document.body.classList.contains('section-lp')) return;
  if (window.Chart) {
    var daily = Chart.getChart('lp-daily-chart');
    // The legacy route gives both charts the same options object. Isolate it
    // before changing bar-only geometry, preserving callback functions.
    function cloneChartOptions(value) {
      if (Array.isArray(value)) return value.map(cloneChartOptions);
      if (value && Object.getPrototypeOf(value) === Object.prototype) {
        var copy = {};
        Object.keys(value).forEach(function (key) { copy[key] = cloneChartOptions(value[key]); });
        return copy;
      }
      return value;
    }
    if (daily) {
      var dailyOptions = cloneChartOptions(daily.config.options);
      var dailyData = daily.data;
      var dailyViewport = daily.canvas.parentElement;
      var dailyCanvas = daily.canvas;
      daily.destroy();
      var dailySurface = document.createElement('div');
      dailySurface.style.cssText = 'position:relative;min-height:100%;width:100%;';
      // Override legacy route/shared chart-body overflow for this scroll owner only.
      dailyViewport.style.setProperty('overflow', 'hidden auto', 'important');
      dailyViewport.style.scrollbarGutter = 'stable';
      dailyViewport.setAttribute('tabindex', '0');
      dailyViewport.setAttribute('role', 'region');
      dailyViewport.setAttribute('aria-label', '每日盈亏图，上下滚动查看日期，盈利向右、亏损向左，单位美元');
      dailyViewport.appendChild(dailySurface);
      dailySurface.appendChild(dailyCanvas);
      dailySurface.style.height = (dailyData.labels.length * 30 + 42) + 'px';
      dailyOptions.indexAxis = 'y';
      dailyOptions.animation = false;
      dailyOptions.scales = {
        x: {type:'linear',position:'bottom',bounds:'data',ticks:{maxTicksLimit:5}},
        y: {type:'category',offset:true,ticks:{autoSkip:false}}
      };
    }
    var cumulative = Chart.getChart('lp-cumulative-chart');
    if (cumulative) {
      cumulative.config.options = cloneChartOptions(cumulative.config.options);
      cumulative.config.options.plugins.tooltip.callbacks.label = function (context) {
        var value = Number(context.raw || 0), cny = value * 6.66;
        return ['当月累计盈亏 ' + (value >= 0 ? '+' : '-') + '$' + Math.abs(value).toFixed(2),
          '人民币 ' + (cny >= 0 ? '+' : '-') + '¥' + Math.abs(cny).toLocaleString('zh-CN', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' CNY'];
      };
      cumulative.update('none');
    }
    function amountLabel(value) {
      return (value >= 0 ? '+' : '-') + '$' + Math.abs(value).toFixed(1);
    }
    window.lpDrawDailyLabels = function (chart) {
      if (chart.canvas.id !== 'lp-daily-chart') return;
      var ctx = chart.ctx, meta = chart.getDatasetMeta(0), values = chart.data.datasets[0].data;
      var styles = getComputedStyle(document.body), size = 11, height = 14;
      ctx.save();
      ctx.font = '600 ' + size + 'px system-ui, sans-serif';
      ctx.textBaseline = 'middle';
      chart.$dailyLabelBoxes = [];
      meta.data.forEach(function (bar, index) {
        var value = Number(values[index] || 0);
        if (!value) return;
        var label = amountLabel(value), width = ctx.measureText(label).width;
        var x = bar.x + (value < 0 ? -8 : 8), y = bar.y;
        ctx.save();
        ctx.translate(x, y);
        ctx.textAlign = value < 0 ? 'right' : 'left';
        ctx.fillStyle = styles.getPropertyValue(value < 0 ? '--red' : '--green').trim();
        ctx.fillText(label, 0, 0);
        ctx.restore();
        chart.$dailyLabelBoxes.push({index:index,x:value<0?x-width:x,y:y-height/2,width:width,height:height,angle:0});
      });
      ctx.restore();
    };
    // Run for every month/theme/resize update: route code replaces layout.padding.
    Chart.register({
      id: 'lpDailyHorizontal',
      beforeUpdate: function (chart) {
        if (chart.canvas.id !== 'lp-daily-chart') return;
        dailySurface.style.height = (chart.data.labels.length * 30 + 42) + 'px';
        chart.options.indexAxis = 'y';
        chart.options.animation = false;
        var styles = getComputedStyle(document.body);
        var text = styles.getPropertyValue('--text2').trim();
        var grid = styles.getPropertyValue('--border').trim();
        var x = chart.options.scales.x, y = chart.options.scales.y;
        x.type = 'linear'; x.offset = false; x.bounds = 'data';
        x.ticks.callback = function(value) { return '$' + Number(value).toLocaleString('en-US'); };
        x.ticks.color = text; x.ticks.maxTicksLimit = 5;
        x.ticks.includeBounds = false; x.ticks.precision = 0;
        x.afterBuildTicks = function(scale) {
          var rawStep = (scale.max - scale.min) / 4;
          var power = Math.pow(10, Math.floor(Math.log10(rawStep || 1)));
          var step = [1,2,5,10].map(function(n) { return n * power; }).find(function(n) { return n >= rawStep; }) || power * 10;
          var ticks = [];
          for (var value = Math.ceil(scale.min / step) * step; value <= scale.max; value += step) ticks.push({value:+value.toPrecision(12)});
          scale.ticks = ticks;
        };
        x.grid.color = function(context) { return context.tick.value === 0 ? text : grid; };
        x.grid.lineWidth = function(context) { return context.tick.value === 0 ? 1.5 : 1; };
        y.type = 'category'; y.offset = true;
        y.ticks.autoSkip = false; y.ticks.color = text;
        y.ticks.font = {size:11};
        y.ticks.callback = function(value) { return this.getLabelForValue(value) + ' 日'; };
        y.grid.display = false;
        chart.data.datasets.forEach(function (dataset) {
          dataset.barThickness = 14;
          dataset.maxBarThickness = 14;
          dataset.categoryPercentage = 0.8;
          dataset.barPercentage = 0.9;
        });
        var ctx = chart.ctx, positive = 0, negative = 0;
        var low = 0, high = 0;
        ctx.save();
        ctx.font = '600 11px system-ui, sans-serif';
        chart.data.datasets[0].data.forEach(function (value) {
          var width = value ? ctx.measureText(amountLabel(Number(value))).width + 18 : 0;
          if (value < 0) negative = Math.max(negative, width);
          else positive = Math.max(positive, width);
          low = Math.min(low, Number(value || 0));
          high = Math.max(high, Number(value || 0));
        });
        ctx.restore();
        // Reserve numeric-axis range for labels, keeping them clear of date ticks.
        var range = high - low || 1;
        var available = Math.max(60, chart.width - 65 - positive - negative);
        x.min = low - range * negative / available;
        x.max = high + range * positive / available || 1;
        chart.options.layout.padding = {top:6,bottom:6,left:4,right:8};
      },
      afterDataLimits: function(chart, args) {
        if (chart.canvas.id !== 'lp-daily-chart' || args.scale.id !== 'x') return;
        args.scale.min = chart.options.scales.x.min;
        args.scale.max = chart.options.scales.x.max;
      },
      afterUpdate: function(chart) {
        if (chart.canvas.id !== 'lp-daily-chart') return;
        var month = document.querySelector('.month-filter button.active');
        var key = (month ? month.dataset.month : '') + ':' + chart.data.labels.join(',');
        if (chart.$dailyMonthKey === key) return;
        chart.$dailyMonthKey = key;
        cancelAnimationFrame(chart.$dailyScrollFrame);
        chart.$dailyScrollFrame = requestAnimationFrame(function() {
          chart.resize();
          chart.$dailyScrollFrame = requestAnimationFrame(function() {
            dailyViewport.scrollTop = chart.$dailyExpanded ? 0 : dailyViewport.scrollHeight;
          });
        });
      }
    });
    if (dailyCanvas) daily = new Chart(dailyCanvas, {type:'bar',data:dailyData,options:dailyOptions});
    if (daily) {
      var dailyCard = dailyViewport.closest('.chart-panel');
      var expandButton = document.createElement('button');
      expandButton.type = 'button';
      expandButton.className = 'lp-chart-expand';
      expandButton.textContent = '⤢';
      expandButton.title = '展开整月';
      expandButton.setAttribute('aria-label', '展开每日盈亏整月视图');
      expandButton.setAttribute('aria-expanded', 'false');
      dailyCard.querySelector('.chart-head').appendChild(expandButton);
      var chartDialog = document.createElement('dialog');
      chartDialog.className = 'charts-grid lp-chart-dialog';
      chartDialog.setAttribute('aria-label', '每日盈亏整月视图');
      document.body.appendChild(chartDialog);
      var placeholder, savedDailyData, savedViewportStyle, savedScroll, savedBodyOverflow;
      function positionExpandedChart() {
        if (!chartDialog.open || !placeholder) return;
        var rect = placeholder.getBoundingClientRect();
        var height = Math.min(innerHeight - 24, daily.data.labels.length * 30 + 42 + dailyCard.querySelector('.chart-head').offsetHeight + 26);
        chartDialog.style.width = Math.min(rect.width, innerWidth - 24) + 'px';
        chartDialog.style.left = Math.max(12, Math.min(rect.left, innerWidth - rect.width - 12)) + 'px';
        chartDialog.style.top = Math.max(12, Math.min(rect.top, innerHeight - height - 12)) + 'px';
        dailyViewport.style.setProperty('height', (height - dailyCard.querySelector('.chart-head').offsetHeight - 2) + 'px', 'important');
        daily.resize();
      }
      function closeExpandedChart() {
        if (!placeholder) return;
        daily.$dailyExpanded = false;
        daily.data = savedDailyData;
        cancelAnimationFrame(daily.$dailyScrollFrame);
        placeholder.replaceWith(dailyCard);
        placeholder = null;
        dailyViewport.setAttribute('style', savedViewportStyle);
        document.body.style.overflow = savedBodyOverflow;
        expandButton.textContent = '⤢';
        expandButton.title = '展开整月';
        expandButton.setAttribute('aria-label', '展开每日盈亏整月视图');
        expandButton.setAttribute('aria-expanded', 'false');
        daily.resize(); daily.update('none');
        cancelAnimationFrame(daily.$dailyScrollFrame);
        dailyViewport.scrollTop = savedScroll;
        expandButton.focus({preventScroll:true});
      }
      expandButton.addEventListener('click', function() {
        if (chartDialog.open) { chartDialog.close(); return; }
        savedViewportStyle = dailyViewport.getAttribute('style') || '';
        savedScroll = dailyViewport.scrollTop;
        savedBodyOverflow = document.body.style.overflow;
        savedDailyData = daily.data;
        var month = document.querySelector('.month-filter button.active').dataset.month;
        var monthDays = new Date(Number(month.slice(0,4)), Number(month.slice(5,7)), 0).getDate();
        var amounts = {};
        daily.data.labels.forEach(function(label,index) { amounts[Number(label)] = daily.data.datasets[0].data[index]; });
        daily.data = cloneChartOptions(daily.data);
        daily.data.labels = Array.from({length:monthDays}, function(_,i) { return String(i+1).padStart(2,'0'); });
        daily.data.datasets[0].data = daily.data.labels.map(function(label) { return amounts[Number(label)] || 0; });
        daily.data.datasets[0].backgroundColor = daily.data.datasets[0].data.map(function(value) { return value >= 0 ? 'rgba(23,150,119,.72)' : 'rgba(200,77,96,.72)'; });
        daily.$dailyExpanded = true;
        placeholder = document.createElement('div');
        placeholder.style.height = dailyCard.getBoundingClientRect().height + 'px';
        dailyCard.replaceWith(placeholder);
        chartDialog.appendChild(dailyCard);
        expandButton.textContent = '×';
        expandButton.title = '收起';
        expandButton.setAttribute('aria-label', '收起每日盈亏整月视图');
        expandButton.setAttribute('aria-expanded', 'true');
        chartDialog.showModal();
        document.body.style.overflow = 'hidden';
        positionExpandedChart();
        daily.update('none');
        dailyViewport.scrollTop = 0;
        expandButton.focus({preventScroll:true});
      });
      chartDialog.addEventListener('close', closeExpandedChart);
      chartDialog.addEventListener('click', function(event) { if (event.target === chartDialog) chartDialog.close(); });
      window.addEventListener('resize', positionExpandedChart);
    }
  }
  document.querySelectorAll('.add-panel input:not([type="hidden"]), .add-panel textarea').forEach(function (field) {
    field.setAttribute('aria-label', field.type === 'datetime-local' ? '开仓日期与时间' : field.placeholder);
  });
  var search = document.getElementById('lp-search');
  var rows = document.getElementById('lp-rows');
  if (search && rows) {
    search.parentElement.classList.add('lp-searchbar');
    search.setAttribute('aria-label', '搜索活跃仓位');
    search.placeholder = '搜索代币对或仓位备注…';
    var status = document.createElement('span');
    status.className = 'lp-search-feedback';
    status.setAttribute('aria-live', 'polite');
    search.after(status);
    var empty = document.createElement('tr');
    empty.className = 'lp-empty-row';
    empty.innerHTML = '<td colspan="8">没有匹配的仓位，请尝试其他关键词。</td>';
    empty.hidden = true;
    rows.appendChild(empty);
    function updateSearch() {
      var all = Array.from(rows.querySelectorAll('tr[data-search]'));
      var shown = all.filter(function (row) { return row.style.display !== 'none'; }).length;
      status.textContent = search.value ? '匹配 ' + shown + ' / ' + all.length + ' 个仓位' : '';
      empty.hidden = shown > 0 || all.length === 0;
    }
    search.addEventListener('input', updateSearch);
  }
  document.querySelectorAll('.summary-grid .metric:nth-child(4) b, .lp-layout .lp-table td:nth-child(6)').forEach(function (node) {
    var value = Number(node.textContent.replace(/[^0-9.+-]/g, ''));
    node.classList.add(value < 0 ? 'lp-loss' : 'lp-gain');
  });
  function highlightToday() {
    var now = new Date();
    var date = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
    document.querySelectorAll('.heat-day[title]').forEach(function (day) {
      var today = day.title.slice(0, 10) === date;
      day.classList.toggle('is-today', today);
      if (today) day.setAttribute('aria-current', 'date');
    });
  }
  var calendar = document.getElementById('lp-heatmap');
  if (calendar) new MutationObserver(highlightToday).observe(calendar, {childList:true, subtree:true});
  highlightToday();
})();
