(() => {
 const board = document.getElementById('kanban'); if (!board) return;
 let busy = false;
 const scrollKey = `pcc-board-scroll:${board.dataset.projectId}`;
 async function move(id, data, control) {
  if (busy) return;
  if (data.status === 'blocked' && board.querySelector(`[data-status-select][data-task-id-select="${CSS.escape(id)}"]`)?.dataset.current !== 'blocked') {
   // Existing status validation remains the source of truth; collect the reason in the task drawer.
   const link = document.createElement('a'); link.href = `/tasks/${id}/edit/?mode=update&board_status=blocked&clear_column=${data.clear_column || 'false'}`; link.dataset.projectAction = '';
   document.body.append(link); link.click(); link.remove();
   if (control) control.value = control.dataset.current;
   return;
  }
  busy = true; if (control) control.disabled = true;
  const url = id.startsWith('feedback:') ? `/projects/${board.dataset.projectId}/board/feedback/${id.slice(9)}/` : data.column ? `/projects/${board.dataset.projectId}/board/tasks/${id}/` : `/tasks/${id}/status/`;
  try {await PCC.update(url, data); sessionStorage.setItem(scrollKey, board.scrollLeft); location.reload();}
  catch (error) {PCC.notify(error.message, true); if (control) {control.value = control.dataset.current; control.disabled = false;} busy = false;}
 }
 board.scrollLeft = Number(sessionStorage.getItem(scrollKey) || 0);
 board.querySelectorAll('[data-status-select]').forEach(select => select.addEventListener('change', () => move(select.dataset.taskIdSelect, {status: select.value}, select)));
 board.querySelectorAll('[data-column-select]').forEach(select => select.addEventListener('change', () => {
  const status = board.querySelector(`[data-task-id-select="${select.dataset.taskIdSelect}"][data-status-select]`).dataset.current;
  move(select.dataset.taskIdSelect, select.value ? {column: select.value} : {status, clear_column: 'true'}, select);
 }));
 board.querySelectorAll('[data-feedback-column-select]').forEach(select => select.addEventListener('change', () => move(`feedback:${select.dataset.feedbackIdSelect}`, {column: select.value}, select)));
 board.querySelectorAll('[data-task-id], [data-feedback-id]').forEach(card => {
  if (card.dataset.draggable !== 'true') return;
  card.draggable = true;
  card.addEventListener('dragstart', event => {event.dataTransfer.setData('text/plain', card.dataset.feedbackId ? `feedback:${card.dataset.feedbackId}` : card.dataset.taskId); event.dataTransfer.effectAllowed = 'move'; card.classList.add('opacity-40');});
  card.addEventListener('dragend', () => card.classList.remove('opacity-40'));
 });
 board.querySelectorAll('[data-status], [data-custom-column]').forEach(column => {
  column.addEventListener('dragover', event => event.preventDefault());
  column.addEventListener('drop', event => {
   event.preventDefault(); const id = event.dataTransfer.getData('text/plain');
   if (id.startsWith('feedback:')) {
    const feedback = board.querySelector(`[data-feedback-id="${CSS.escape(id.slice(9))}"]`);
    if (feedback?.dataset.draggable !== 'true') return;
    if (!column.dataset.customColumn) {PCC.notify('Pindahkan feedback ke kolom tambahan. Status pekerjaan diatur pada task terkait.', true); return;}
    move(id, {column: column.dataset.customColumn}); return;
   }
   const card = board.querySelector(`[data-task-id="${CSS.escape(id)}"]`);
   if (card?.dataset.draggable === 'true') move(id, column.dataset.customColumn ? {column: column.dataset.customColumn} : {status: column.dataset.status, clear_column: 'true'});
  });
 });
})();
