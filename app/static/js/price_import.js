document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.price-target-select').forEach(select => {
        const fields = select.closest('td').querySelector('.price-new-fields');
        if (!fields) return;
        const update = () => { fields.hidden = fields.disabled = select.value !== 'new'; };
        select.addEventListener('change', update);
        update();
    });
});
