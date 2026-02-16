// Mobile nav toggle
document.addEventListener('DOMContentLoaded', function() {
    const toggle = document.querySelector('.nav-toggle');
    const nav = document.querySelector('.navbar-nav');
    if (toggle && nav) {
        toggle.addEventListener('click', function() {
            nav.classList.toggle('open');
        });
    }
});

// Copy invite link to clipboard
function copyInvite(text) {
    navigator.clipboard.writeText(text).then(function() {
        const btn = document.querySelector('.copy-btn');
        if (btn) {
            const orig = btn.textContent;
            btn.textContent = 'Copiado!';
            setTimeout(function() { btn.textContent = orig; }, 2000);
        }
    });
}

// Confirm before destructive actions
function confirmAction(msg) {
    return confirm(msg || 'Tem certeza?');
}
