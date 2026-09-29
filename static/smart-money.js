(function () {
  var wallets = Array.isArray(window.SMART_MONEY_DATA) ? window.SMART_MONEY_DATA : [];
  var modal = document.getElementById('sm-modal');
  var backdrop = document.getElementById('sm-backdrop');
  var form = document.getElementById('sm-form');
  var deleteButton = document.getElementById('sm-delete');
  var deleteArmed = false;
  var deleteTimer = null;

  function openModal(wallet) {
    form.reset();
    deleteArmed = false;
    deleteButton.classList.remove('confirming');
    document.getElementById('sm-modal-title').textContent = wallet ? '编辑聪明钱地址' : '登记聪明钱地址';
    document.getElementById('sm-wallet-id').value = wallet ? wallet.id : '';
    document.getElementById('sm-name').value = wallet ? wallet.name || '' : '';
    document.getElementById('sm-address').value = wallet ? wallet.address || '' : '';
    document.getElementById('sm-assets').value = wallet && Number(wallet.estimated_assets) ? wallet.estimated_assets : '';
    document.getElementById('sm-capital').value = wallet ? wallet.capital_tier || 'unknown' : 'unknown';
    document.getElementById('sm-priority').value = wallet ? wallet.priority || 'watch' : 'watch';
    document.getElementById('sm-activity').value = wallet ? wallet.activity || 'unknown' : 'unknown';
    document.getElementById('sm-source-url').value = wallet ? wallet.source_url || '' : '';
    document.getElementById('sm-tags').value = wallet ? (wallet.tags || []).join(', ') : '';
    document.getElementById('sm-note').value = wallet ? wallet.note || '' : '';
    form.querySelectorAll('input[type="checkbox"]').forEach(function (input) {
      var selected = input.name === 'strategies' ? (wallet && wallet.strategies || []) : (wallet && wallet.chains || []);
      input.checked = selected.indexOf(input.value) !== -1;
    });
    deleteButton.hidden = !wallet;
    document.getElementById('sm-delete-id').value = wallet ? wallet.id : '';
    modal.classList.add('visible');
    backdrop.classList.add('visible');
    document.body.style.overflow = 'hidden';
    setTimeout(function () { document.getElementById(wallet ? 'sm-name' : 'sm-address').focus(); }, 30);
  }

  function closeModal() {
    modal.classList.remove('visible');
    backdrop.classList.remove('visible');
    document.body.style.overflow = '';
    deleteArmed = false;
    deleteButton.classList.remove('confirming');
    if (deleteTimer) clearTimeout(deleteTimer);
  }

  function applyFilters() {
    var query = document.getElementById('sm-search').value.trim().toLowerCase();
    var strategy = document.getElementById('sm-strategy-filter').value;
    var chain = document.getElementById('sm-chain-filter').value;
    var priority = document.getElementById('sm-priority-filter').value;
    var cards = Array.from(document.querySelectorAll('.sm-card'));
    var visible = 0;
    cards.forEach(function (card) {
      var show = (!query || card.dataset.search.indexOf(query) !== -1) &&
        (!strategy || card.dataset.strategies.split('|').indexOf(strategy) !== -1) &&
        (!chain || card.dataset.chains.split('|').indexOf(chain) !== -1) &&
        (!priority || card.dataset.priority === priority);
      card.hidden = !show;
      if (show) visible += 1;
    });
    document.getElementById('sm-result-count').textContent = visible + ' / ' + cards.length + ' 个地址';
  }

  document.getElementById('sm-open-add').addEventListener('click', function () { openModal(null); });
  document.querySelectorAll('.sm-empty-add').forEach(function (button) { button.addEventListener('click', function () { openModal(null); }); });
  document.querySelectorAll('.sm-edit').forEach(function (button) {
    button.addEventListener('click', function () {
      openModal(wallets.find(function (item) { return item.id === button.dataset.id; }) || null);
    });
  });
  document.querySelectorAll('[data-copy]').forEach(function (button) {
    button.addEventListener('click', function () {
      var address = button.dataset.copy;
      var original = button.querySelector('span').textContent;
      navigator.clipboard.writeText(address).then(function () {
        button.querySelector('span').textContent = '已复制';
        setTimeout(function () { button.querySelector('span').textContent = original; }, 1200);
      }).catch(function () {
        var input = document.createElement('textarea');
        input.value = address; input.style.position = 'fixed'; input.style.left = '-9999px';
        document.body.appendChild(input); input.select(); document.execCommand('copy'); input.remove();
        button.querySelector('span').textContent = '已复制';
        setTimeout(function () { button.querySelector('span').textContent = original; }, 1200);
      });
    });
  });

  ['sm-search', 'sm-strategy-filter', 'sm-chain-filter', 'sm-priority-filter'].forEach(function (id) {
    document.getElementById(id).addEventListener(id === 'sm-search' ? 'input' : 'change', applyFilters);
  });
  document.getElementById('sm-close-modal').addEventListener('click', closeModal);
  document.getElementById('sm-cancel').addEventListener('click', closeModal);
  backdrop.addEventListener('click', closeModal);
  document.addEventListener('keydown', function (event) { if (event.key === 'Escape') closeModal(); });
  deleteButton.addEventListener('click', function () {
    if (!deleteArmed) {
      deleteArmed = true; deleteButton.classList.add('confirming');
      deleteTimer = setTimeout(function () { deleteArmed = false; deleteButton.classList.remove('confirming'); }, 3500);
      return;
    }
    document.getElementById('sm-delete-form').submit();
  });
  document.getElementById('sm-assets').addEventListener('input', function (event) {
    var value = Number(event.target.value || 0), tier = 'unknown';
    if (value >= 1000000) tier = 'over_1m'; else if (value >= 100000) tier = '100k_1m'; else if (value >= 10000) tier = '10k_100k'; else if (value > 0) tier = 'under_10k';
    document.getElementById('sm-capital').value = tier;
  });
  applyFilters();
})();
