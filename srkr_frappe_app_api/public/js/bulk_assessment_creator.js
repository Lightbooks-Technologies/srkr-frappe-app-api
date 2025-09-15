frappe.ui.form.on('Bulk Assessment Creator', {
    refresh: function(frm) {
        // --- THIS IS THE CORRECTED CODE FOR A SINGLE DOCTYPE ---
        // We access the field directly from the 'frm' object.
        
        // First, get the field controller
        const buttonField = frm.get_field('create_draft_assessments');
        
        // Then, add the click event listener to its input element
        buttonField.$input.on('click', function() {
            if (!frm.doc.academic_term) {
                frappe.msgprint(__('Please select an Academic Term first.'));
                return;
            }

            frappe.confirm(
                __('This will create draft assessment records for all non-lab courses in the selected term. This action cannot be undone. Are you sure you want to continue?'),
                () => {
                    // If user confirms, call the backend function.
                    frappe.call({
                        method: 'srkr_frappe_app_api.internal_assessments.doctype.bulk_assessment_creator.bulk_assessment_creator.create_assessments_for_term',
                        args: {
                            academic_term: frm.doc.academic_term
                        },
                        freeze: true,
                        freeze_message: __('Creating assessments, this may take a moment...')
                    });
                }
            );
        });
    }
});