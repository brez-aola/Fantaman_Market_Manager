// Consolidated JS extracted from templates
document.addEventListener('click', function(e){
  // header sort link delegation (index page)
  var a = e.target.closest && e.target.closest('a.header-link');
  if(a){
    e.preventDefault();
    var url = a.getAttribute('href');
    fetch(url).then(r=>r.text()).then(html=>{
      var m = html.match(/<div id="players-table">([\s\S]*?)<\/div>/i);
      if(m){
        var container = document.getElementById('players-table');
        if(container) container.innerHTML = m[1];
      } else {
        document.body.innerHTML = html;
      }
    }).catch(function(err){ console.error('Failed to load sorted table', err); window.location = url; });
    return;
  }

  // assign button delegation
  var btn = e.target.closest && e.target.closest('.assign-btn');
  if(btn){
    e.preventDefault();
    var id = btn.getAttribute('data-id');
    var nome = btn.getAttribute('data-name');
    openAssignPopup(id, nome);
    return;
  }

  // edit button in rose page
  var edit = e.target.closest && e.target.closest('.edit-btn');
  if(edit){
    e.preventDefault();
    var id = edit.getAttribute('data-id');
    if(typeof openEdit === 'function'){
      openEdit(id, edit);
    } else {
      alert('Edit player: ' + id);
    }
    return;
  }
});

// Assign popup helper functions
function openAssignPopup(id, nome) {
    var elId = document.getElementById('assign_id');
    var elNome = document.getElementById('assign_nome');
    var popup = document.getElementById('assignPopup');
    var anni = document.getElementById('anni_contratto');
    elId && (elId.value = id);
    elNome && (elNome.innerText = nome);
    if(popup) popup.style.display = 'block';
    if(anni) { anni.value = '1'; updateOpzione(); }
}
function closeAssignPopup() { var popup = document.getElementById('assignPopup'); if(popup) popup.style.display = 'none'; }
function updateOpzione() {
  var anniEl = document.getElementById('anni_contratto');
  var opzione = document.getElementById('opzione');
  if(!anniEl || !opzione) return;
  var anni = anniEl.value;
  if (anni == '3') { opzione.checked = false; opzione.disabled = true; }
  else { opzione.checked = true; opzione.disabled = false; }
}

async function submitAssignForm(){
    var form = document.getElementById('assignForm');
    if(!form) return false;
    var formData = new FormData(form);
    var params = new URLSearchParams();
    for (const pair of formData.entries()) params.append(pair[0], pair[1]);
    try{
        var res = await fetch(form.action, {method:'POST', body: params});
        if(!res.ok){
            var text = await res.text();
            var errBox = document.getElementById('assignError');
            if(errBox){ errBox.style.display='block'; errBox.innerText = text || res.statusText; }
            else alert('Errore: ' + (text || res.statusText));
            return false;
        }
        closeAssignPopup();
        try{
            var rhtml = await fetch('/');
            var text = await rhtml.text();
            var m1 = text.match(/<div class="team-cash-container">([\s\S]*?)<\/div>/i);
            if(m1){
                var container = document.querySelector('.team-cash-container');
                if(container) container.outerHTML = '<div class="team-cash-container">' + m1[1] + '</div>';
            }
            var m2 = text.match(/<div id="players-table">([\s\S]*?)<\/div>/i);
            if(m2){ var pt = document.getElementById('players-table'); if(pt) pt.innerHTML = m2[1]; }
        }catch(e){ window.location.reload(); }
        return false;
    }catch(e){ var errBox = document.getElementById('assignError'); if(errBox){ errBox.style.display='block'; errBox.innerText = 'Errore invio: ' + e.message; } else alert('Errore invio: ' + e.message); return false; }
}

// Expose submitAssignForm on window for the form onsubmit to call
window.submitAssignForm = submitAssignForm;
window.openAssignPopup = openAssignPopup;
window.closeAssignPopup = closeAssignPopup;
window.updateOpzione = updateOpzione;
