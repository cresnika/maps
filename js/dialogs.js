const toast = document.createElement('div');
toast.className = 'toast';
document.body.appendChild(toast);

let toastTimeout;

function showToast(message, duration = 2500) {
    toast.textContent = message;
    toast.classList.add('show');

    clearTimeout(toastTimeout);

    toastTimeout = setTimeout(() => {
            toast.classList.remove('show');
        }, duration);
}

function ConfirmOrderDialog(wp, maxIndex) {
    return new Promise(resolve => {
        const backdrop = document.getElementById('confirm-order-backdrop');
        const textElem = document.getElementById('confirm-order-text');
        const userInput = document.getElementById('waypoint-position');
        const btnYes = document.getElementById('confirm-order-yes');
        const btnNo = document.getElementById('confirm-order-no');

        textElem.innerHTML = `An welche Position soll #${wp.routeIndex} (${wp.label}) verschoben werden?<br><br>0 = Start und ${maxIndex} = Ziel`;
        userInput.value = '';
        backdrop.classList.add('active');
        userInput.focus();
        userInput.addEventListener('keydown', (e) => { 
        if (e.key === 'Enter') {
            btnYes.click();
        }
        if (e.key === 'Escape') {
            btnNo.click();
        }
        });
        function close(result) {
            backdrop.classList.remove('active');
            btnYes.onclick = null;
            btnNo.onclick = null;
            resolve(result);
        }
        
        btnNo.onclick = () => close(-1);
        btnYes.onclick = () => {
            const newIndex = Number(userInput.value.trim());
            if (!Number.isFinite(newIndex) || newIndex > maxIndex) {
                showToast('Bitte eine gültige Position eingeben', 1000);
                return;
            }
            else {
            close(newIndex);
            }
        };
    });
}

function confirmDialog(text) {
    return new Promise(resolve => {
        const backdrop = document.getElementById('confirm-backdrop');
        const textElem = document.getElementById('confirm-text');
        const btnYes = document.getElementById('confirm-yes');
        const btnNo = document.getElementById('confirm-no');

        textElem.textContent = text;
        backdrop.classList.add('active');

        const cleanup = result => {
        backdrop.classList.remove('active');
        btnYes.onclick = null;
        btnNo.onclick = null;
        resolve(result);
        };

        btnYes.onclick = () => cleanup(true);
        btnNo.onclick = () => cleanup(false);
    });
}

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme',theme);
    localStorage.setItem('theme', theme);
}

document.documentElement.setAttribute(
    'data-theme',
    localStorage.getItem('theme') || 'light'
);
