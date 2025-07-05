frappe.ui.form.on('Student', {
    refresh: function(frm) {
        if (!frm.is_new() && frm.doc.custom_hall_ticket_number) {
            frm.add_custom_button(__('Sync Exam Results'), function() {
                frappe.call({
                    method: 'srkr_frappe_app_api.api.sync_student_results',
                    args: {
                        student_id: frm.doc.name
                    },
                    callback: function(r) {
                        if (r.message && r.message.status === 'success') {
                            frm.reload_doc();
                        }
                    },
                    freeze: true,
                    freeze_message: __("Syncing results from API...")
                });
            }).addClass('btn-primary');
        }
    }
});
