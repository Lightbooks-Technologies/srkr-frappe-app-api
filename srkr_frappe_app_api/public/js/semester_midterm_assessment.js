frappe.ui.form.on('Semester Midterm Assessment', {
    refresh: function(frm) {
        // Clear existing custom buttons to avoid duplicates on every refresh
        frm.clear_custom_buttons();

        // --- BUTTON LOGIC ---

        // Button to load the default structure, shown only for new documents.
        if (frm.is_new()) {
            frm.add_custom_button(__('Load Default Structure'), function() {
                frappe.confirm('This will clear and load the default R23 assessment structure. Continue?', () => {
                    frappe.call({
                        method: 'srkr_frappe_app_api.internal_assessments.doctype.semester_midterm_assessment.semester_midterm_assessment.get_default_assessment_structure',
                        callback: function(r) {
                            if (r.message) {
                                frm.clear_table('assessment_structure');
                                r.message.forEach(item => {
                                    frm.add_child('assessment_structure', item);
                                });
                                frm.refresh_field('assessment_structure');
                                frappe.show_alert({message: 'Default structure loaded.', indicator: 'green'});
                            }
                        }
                    });
                });
            });
        }

        // Buttons for saved documents that are still in Draft status.
        if (!frm.is_new() && frm.doc.docstatus === 0) {
            
            frm.add_custom_button(__('Generate Marksheet Template'), function() {
                if (!frm.doc.assessment_structure || frm.doc.assessment_structure.length === 0) {
                    frappe.msgprint(__('Please define and save the Assessment Structure first.'));
                    return;
                }
                const url = frappe.urllib.get_full_url("/api/method/srkr_frappe_app_api.internal_assessments.doctype.semester_midterm_assessment.semester_midterm_assessment.generate_marksheet_template?docname=" + encodeURIComponent(frm.doc.name));
                window.open(url);
            }).addClass('btn-primary');

            frm.add_custom_button(__('Upload Marksheet'), function() {
                new frappe.ui.FileUploader({
                    doctype: frm.doctype,
                    docname: frm.doc.name,
                    on_success: function(file) {
                        frappe.show_alert({message: __('Processing Marksheet...'), indicator: 'blue'}, 7);
                        frappe.call({
                            method: 'srkr_frappe_app_api.internal_assessments.doctype.semester_midterm_assessment.semester_midterm_assessment.upload_marksheet',
                            args: { file_url: file.file_url, docname: frm.doc.name },
                            callback: function(r) {
                                if (r.message) {
                                    frappe.show_alert({message: __('Marksheet uploaded successfully.'), indicator: 'green'}, 5);
                                    frm.reload_doc();
                                }
                            },
                            error: function() {
                                frappe.show_alert({message: __('Error processing marksheet.'), indicator: 'red'}, 7);
                            }
                        });
                    }
                });
            });

            // Button to view the detailed report
            frm.add_custom_button(__('View Detailed Marksheet'), function() {
                frappe.set_route('query-report', 'Semester Midterm Assessment Report', {
                    assessment: frm.doc.name
                });
            });
        }

        // --- UI Polish ---
        // Always hide the grid's own add/delete buttons for the summary table.
        frm.fields_dict['final_scores_summary'].grid.grid_buttons.hide();
    },
    
    student_group: function(frm) {
        // Auto-population logic
        if (!frm.doc.student_group) {
            frm.clear_table('final_scores_summary');
            frm.refresh_field('final_scores_summary');
            return;
        }
        
        // Ask for confirmation only if the table is not empty
        if (frm.doc.final_scores_summary && frm.doc.final_scores_summary.length > 0) {
             frappe.confirm(
                __('Changing the Student Group will clear the current student list. Continue?'),
                () => { fetch_and_populate_students(frm); }
            );
        } else {
             fetch_and_populate_students(frm);
        }
    }
});

function fetch_and_populate_students(frm) {
    // Non-blocking indicator logic
    frappe.show_alert({ message: __('Fetching Students...'), indicator: 'blue' }, 5);
    frappe.call({
        method: 'srkr_frappe_app_api.internal_assessments.doctype.semester_midterm_assessment.semester_midterm_assessment.get_students_for_group',
        args: { student_group: frm.doc.student_group },
        callback: function(response) {
            if (response.message) {
                frm.clear_table('final_scores_summary');
                response.message.forEach(student => {
                    frm.add_child('final_scores_summary', {
                        'student': student.student,
                        'student_name': student.student_name,
                        'customer_student_id': student.register_number
                    });
                });
                frm.refresh_field('final_scores_summary');
                frappe.show_alert({ message: __('{0} students populated.', [response.message.length]), indicator: 'green' }, 3);
            }
        },
        error: function() {
            frappe.show_alert({ message: __('Failed to fetch students. Please try again.'), indicator: 'red' }, 5);
        }
    });
}