// Copyright (c) 2024, SRKR and contributors
// For license information, please see license.txt

frappe.ui.form.on('Manual Attendance Sync', {
    refresh: function (frm) {
        frm.disable_save();
    },

    run_sync_now: function (frm) {
        if (!frm.doc.sync_date) {
            frappe.msgprint(__("Please select a date first."));
            return;
        }

        frappe.confirm(
            `Are you sure you want to run the External Attendance Sync for <b>${frm.doc.sync_date}</b>? <br>This handles the diff and merge automatically.`,
            function () {
                // Action
                frappe.call({
                    method: "srkr_frappe_app_api.instructor.api.sync_external_attendance",
                    args: {
                        sync_date: frm.doc.sync_date
                    },
                    freeze: true,
                    freeze_message: __("Syncing Attendance... Please wait."),
                    callback: function (r) {
                        if (r.message) {
                            // r.message is the Log Name
                            const log_name = r.message;
                            frappe.show_alert({ message: __("Sync Completed"), indicator: 'green' });

                            // Update Interface
                            frm.set_value('latest_log_link', log_name);
                            frm.set_df_property('status_html', 'options',
                                `<div class="alert alert-success">
									<b>Success!</b> Sync Job Completed.<br>
									<a href="/app/external-attendance-sync-log/${log_name}">Click here to view the detailed log: ${log_name}</a>
								</div>`
                            );
                            frm.refresh_field('status_html');
                        } else {
                            frappe.msgprint(__("Sync finished but no log ID was returned. Check Error Logs."));
                        }
                    },
                    error: function (r) {
                        frappe.msgprint(__("An internal error occurred."));
                    }
                });
            }
        );
    }
});
