frappe.ui.form.on('Student', {
    refresh: function(frm) {
        // Only show buttons and data for saved documents
        if (frm.is_new()) {
            return;
        }

        // Add "Sync Exam Results" button only if the student has a custom ID
        if (frm.doc.custom_student_id) {
            frm.add_custom_button(__('Sync Exam Results'), function() {
                frappe.confirm(
                    __('This will sync all official examination data from the SRKR API, overwriting existing records for this student. This includes:<br><br>' +
                       '<ul>' +
                       '<li>Regular semester results</li>' +
                       '<li>Backlog information</li>' +
                       '<li>Honors & Minors results</li>' +
                       '</ul><br>' +
                       'Do you want to continue?'),
                    () => { // Use arrow function for clarity
                        frappe.call({
                            // CORRECTED PATH to our new api.py file
                            method: 'srkr_frappe_app_api.examination.api.sync_student_exam_results',
                            args: {
                                student_id: frm.doc.name
                            },
                            callback: function(r) {
                                // The main message is now shown from the server-side,
                                // but we can still reload the form to update dashboard items.
                                if (r.message && r.message.status === 'success') {
                                    frm.reload_doc();
                                }
                            },
                            freeze: true,
                            freeze_message: __("Syncing examination results...")
                        });
                    }
                );
            }, __('Actions')).addClass('btn-primary');
        }
        
        // Add "View Results" button for any saved student
        frm.add_custom_button(__('View Results'), function() {
            let d = new frappe.ui.Dialog({
                title: __('View Examination Results'),
                fields: [
                    {
                        label: __('Select Result Type'),
                        fieldname: 'result_type',
                        fieldtype: 'Select',
                        options: [
                            'Regular Semester Results',
                            'Backlog Information',
                            'Honors & Minors Results'
                        ],
                        default: 'Regular Semester Results',
                        reqd: 1
                    }
                ],
                primary_action_label: __('View'),
                primary_action(values) {
                    let doctype_map = {
                        'Regular Semester Results': 'Exam Semester Result',
                        'Backlog Information': 'Exam Semester Backlog',
                        'Honors & Minors Results': 'Exam HM Semester Result'
                    };
                    
                    frappe.set_route('List', doctype_map[values.result_type], {
                        'student': frm.doc.name
                    });
                    d.hide();
                }
            });
            d.show();
        }, __('Actions'));
        
        // Show exam summary dashboard indicators
        if (frm.doc.custom_student_id) {
            frappe.call({
                // CORRECTED PATH to our new api.py file
                method: 'srkr_frappe_app_api.examination.api.get_student_exam_summary',
                args: {
                    student_id: frm.doc.name
                },
                callback: function(r) {
                    if (r.message && Object.keys(r.message).length > 0) {
                        frm.dashboard.clear_indicators(); // Clear old indicators before adding new ones
                        let summary = r.message;
                        if (summary.latest_cgpa != null) {
                            frm.dashboard.add_indicator(
                                __('Latest CGPA: {0} (Sem {1})', [
                                    summary.latest_cgpa.toFixed(2),
                                    summary.latest_semester
                                ]), 
                                'blue'
                            );
                        }
                        if (summary.total_backlogs > 0) {
                            frm.dashboard.add_indicator(
                                __('Active Backlogs: {0}', [summary.total_backlogs]), 
                                'orange'
                            );
                        } else {
                             frm.dashboard.add_indicator(
                                __('No Active Backlogs'), 
                                'green'
                            );
                        }
                    }
                }
            });
        }
    },
    
    // Refresh the buttons and dashboard when the student ID is added or changed
    custom_student_id: function(frm) {
        frm.refresh();
    }
});