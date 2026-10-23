// Editor kaya ringan: textarea tetap jadi sumber data, contenteditable jadi tampilan.
(() => {
    const TOOLS = [
        { cmd: 'bold', label: 'Tebal', html: '<b>B</b>' },
        { cmd: 'italic', label: 'Miring', html: '<i>I</i>' },
        { cmd: 'insertUnorderedList', label: 'Daftar berbutir', html: '&bull;' },
        { cmd: 'insertOrderedList', label: 'Daftar bernomor', html: '1.' },
        { cmd: 'createLink', label: 'Tautan', html: '&#128279;' },
        { cmd: 'removeFormat', label: 'Hapus format', html: '&#10005;' },
    ];
    const escapeHtml = value => value.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

    function build(textarea) {
        if (textarea.dataset.editorReady) return;
        textarea.dataset.editorReady = 'true';

        const shell = document.createElement('div');
        shell.className = 'wysiwyg';
        const toolbar = document.createElement('div');
        toolbar.className = 'wysiwyg-toolbar';
        toolbar.setAttribute('role', 'toolbar');
        toolbar.setAttribute('aria-label', 'Format teks');
        const editor = document.createElement('div');
        editor.className = 'wysiwyg-editor rich-text';
        editor.contentEditable = 'true';
        editor.setAttribute('role', 'textbox');
        editor.setAttribute('aria-multiline', 'true');
        editor.setAttribute('aria-label', textarea.getAttribute('aria-label') || textarea.name);
        editor.dataset.placeholder = textarea.getAttribute('placeholder') || 'Tulis di sini…';
        if (textarea.getAttribute('aria-invalid')) editor.setAttribute('aria-invalid', textarea.getAttribute('aria-invalid'));
        if (textarea.getAttribute('aria-describedby')) editor.setAttribute('aria-describedby', textarea.getAttribute('aria-describedby'));

        const initial = textarea.value || '';
        editor.innerHTML = initial.includes('<') ? initial : escapeHtml(initial).replace(/\n/g, '<br>');

        const sync = () => {
            const html = editor.innerHTML;
            textarea.value = html === '<br>' || html === '<div><br></div>' ? '' : html;
        };

        if (textarea.id) {
            const label = document.querySelector(`label[for="${CSS.escape(textarea.id)}"]`);
            editor.id = `${textarea.id}-editor`;
            if (label) label.setAttribute('for', editor.id);
        }

        TOOLS.forEach(tool => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'wysiwyg-btn';
            button.innerHTML = tool.html;
            button.title = tool.label;
            button.setAttribute('aria-label', tool.label);
            button.addEventListener('mousedown', event => event.preventDefault());
            button.addEventListener('click', () => {
                if (tool.cmd === 'createLink') {
                    const url = window.prompt('Alamat tautan (https://…)');
                    if (url) document.execCommand('createLink', false, url);
                } else {
                    document.execCommand(tool.cmd, false, null);
                }
                editor.focus();
                sync();
            });
            toolbar.append(button);
        });

        editor.addEventListener('input', sync);
        editor.addEventListener('blur', sync);
        editor.addEventListener('paste', event => {
            event.preventDefault();
            const text = (event.clipboardData || window.clipboardData).getData('text/plain');
            document.execCommand('insertText', false, text);
        });

        const parent = textarea.parentNode;
        parent.insertBefore(shell, textarea);
        shell.append(toolbar, editor, textarea);
        textarea.classList.add('wysiwyg-source');
        if (textarea.form) textarea.form.addEventListener('submit', sync);
        sync();
        if (window.PCC?.initMentions) PCC.initMentions(textarea.form);
    }

    function init(root = document) {
        root.querySelectorAll('textarea[data-wysiwyg]').forEach(build);
    }
    document.addEventListener('DOMContentLoaded', () => init());
    document.addEventListener('pcc:panel-loaded', event => init(event.target));
})();