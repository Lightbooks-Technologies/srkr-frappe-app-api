# Mentorship Module Setup Script for SRKR Frappe App API

import frappe

# ==============================================================================
# All helper functions must be defined before the main orchestrator function.
# ==============================================================================

# --- Phase 1: Create all necessary DocTypes ---
def create_mentorship_doctypes():
    print("--- Phase 1: Creating DocTypes ---")
    if frappe.db.exists('DocType', 'Mentor Assignment History'):
        frappe.delete_doc('DocType', 'Mentor Assignment History', force=True, ignore_permissions=True)
        print("    ✅ Cleaned up obsolete DocType: Mentor Assignment History")

    doctypes_to_create = [
        {'doctype': 'DocType','name': 'Mentorship Goals','module': 'Education','custom': 1,'istable': 1,'fields': [{'label': 'Academic Term','fieldname': 'academic_term','fieldtype': 'Link','options': 'Academic Term','reqd': 1,'in_list_view': 1},{'label': 'Goal Category','fieldname': 'goal_category','fieldtype': 'Select','options': 'Academic\nCareer\nSkill Development\nPersonal','reqd': 1,'in_list_view': 1},{'label': 'Specific Goal','fieldname': 'specific_goal','fieldtype': 'Data','reqd': 1,'in_list_view': 1},{'label': 'Status','fieldname': 'status','fieldtype': 'Select','options': 'To Do\nIn Progress\nAchieved\nOn Hold','default': 'To Do','in_list_view': 1}],'permissions': [{'role': 'System Manager','read': 1,'write': 1,'create': 1,'delete': 1},{'role': 'Instructor','read': 1,'write': 1,'create': 1}]},
        {'doctype': 'DocType','name': 'Mentorship Activities','module': 'Education','custom': 1,'istable': 1,'fields': [{'label': 'Date','fieldname': 'date','fieldtype': 'Date','reqd': 1,'in_list_view': 1},{'label': 'Activity Category','fieldname': 'activity_category','fieldtype': 'Select','options': 'Technical\nCultural\nSports\nSocial Service\nCertification\nPublication','in_list_view': 1},{'label': 'Activity Name','fieldname': 'activity_name','fieldtype': 'Data','reqd': 1,'in_list_view': 1},{'label': 'Description','fieldname': 'description','fieldtype': 'Small Text'}],'permissions': [{'role': 'System Manager','read': 1,'write': 1,'create': 1,'delete': 1},{'role': 'Instructor','read': 1,'write': 1,'create': 1}]},
        {'doctype': 'DocType','name': 'Student Mentorship Profile','module': 'Education','custom': 1,'autoname': 'field:student','title_field': 'student_name','track_changes': 1,'is_submittable': 1,'fields': [{'label': 'Student','fieldname': 'student','fieldtype': 'Link','options': 'Student','reqd': 1,'unique': 1},{'label': 'Student Name','fieldname': 'student_name','fieldtype': 'Data','read_only': 1,'fetch_from': 'student.student_name'},{'label': 'Current Mentor','fieldname': 'current_mentor','fieldtype': 'Link','options': 'Instructor'},{'label': 'Program','fieldname': 'program','fieldtype': 'Link','options': 'Program'},{'label': 'Goal Plan','fieldname': 'goals_tab','fieldtype': 'Tab Break','description': 'The strategic plan for the term. Set once and update status.'},{'label': 'Term Goals','fieldname': 'goals','fieldtype': 'Table','options': 'Mentorship Goals'},{'label': 'Achievements Log','fieldname': 'activities_tab','fieldtype': 'Tab Break','description': 'A log of verified student achievements.'},{'label': 'Co-Curriculars','fieldname': 'activities','fieldtype': 'Table','options': 'Mentorship Activities'},{'label': 'Live Dashboard','fieldname': 'dashboard_tab','fieldtype': 'Tab Break','description': 'Real-time academic data for the student.'},{'label': 'Academic Performance','fieldname': 'academic_performance_html','fieldtype': 'HTML','read_only': 1}],'permissions': [{'role': 'System Manager','read': 1,'write': 1,'create': 1,'delete': 1,'submit': 1,'cancel': 1},{'role': 'Instructor','read': 1,'write': 1,'create': 1},{'role': 'Student','read': 1}]},
        {'doctype': 'DocType','name': 'Mentorship Log Entry','module': 'Education','custom': 1,'autoname': 'format:LOG-{student}-{#####}','title_field': 'student','track_changes': 1,'fields': [{'label': 'Student','fieldname': 'student','fieldtype': 'Link','options': 'Student','reqd': 1,'in_list_view': 1},{'label': 'Student Name','fieldname': 'student_name','fieldtype': 'Data','fetch_from': 'student.student_name','read_only': 1},{'label': 'Mentor','fieldname': 'mentor','fieldtype': 'Link','options': 'Instructor','reqd': 1,'in_list_view': 1},{'label': 'Column Break','fieldname': 'col_break_1','fieldtype': 'Column Break'},{'label': 'Date','fieldname': 'date','fieldtype': 'Date','reqd': 1,'default': 'Today','in_list_view': 1},{'label': 'Academic Term','fieldname': 'academic_term','fieldtype': 'Link','options': 'Academic Term'},{'label': 'General Discussion','fieldname': 'discussion_tab','fieldtype': 'Tab Break'},{'label': 'Discussion Notes','fieldname': 'notes','fieldtype': 'Text Editor'},{'label': 'Academic Feedback','fieldname': 'academic_feedback_tab','fieldtype': 'Tab Break'},{'label': 'Academic Progress','fieldname': 'academic_feedback_sb','fieldtype': 'Section Break'},{'label': 'Overall Teaching Quality','fieldname': 'teaching_quality_rating','fieldtype': 'Rating','options': '5'},{'label': 'Lab & Library Facilities','fieldname': 'facilities_rating','fieldtype': 'Rating','options': '5'},{'label': 'Are there any specific subjects the student is struggling with?','fieldname': 'subject_struggles','fieldtype': 'Check'},{'label': 'If yes, list subjects and notes','fieldname': 'subject_struggles_notes','fieldtype': 'Small Text','depends_on': 'eval:doc.subject_struggles==1'},{'label': 'Column Break','fieldname': 'col_break_acad','fieldtype': 'Column Break'},{'label': 'Course Content Relevancy','fieldname': 'content_relevancy_rating','fieldtype': 'Rating','options': '5'},{'label': 'Assessment & Exam Experience','fieldname': 'assessment_rating','fieldtype': 'Rating','options': '5'},{'label': 'Academic Concerns Summary','fieldname': 'academic_concerns_summary','fieldtype': 'Small Text','description': 'Mentor: Summarize any academic issues raised.'},{'label': 'Campus Life Feedback','fieldname': 'campus_life_tab','fieldtype': 'Tab Break'},{'label': 'Hostel & Food','fieldname': 'hostel_food_sb','fieldtype': 'Section Break'},{'label': 'Hostel Experience','fieldname': 'hostel_rating','fieldtype': 'Rating','options': '5'},{'label': 'Mess/Canteen Food Quality','fieldname': 'food_rating','fieldtype': 'Rating','options': '5'},{'label': 'Issues to Report (Check all that apply)','fieldname': 'campus_issues_html','fieldtype': 'HTML','options': '<b>Issues to Report (Check all that apply)</b>'},{'label': 'Hostel Cleanliness','fieldname': 'issue_hostel_cleanliness','fieldtype': 'Check'},{'label': 'Hostel Wi-Fi/Network','fieldname': 'issue_hostel_wifi','fieldtype': 'Check'},{'label': 'Food Variety/Hygiene','fieldname': 'issue_food_quality','fieldtype': 'Check'},{'label': 'Column Break','fieldname': 'col_break_campus','fieldtype': 'Column Break'},{'label': 'Transport Facilities','fieldname': 'transport_rating','fieldtype': 'Rating','options': '5'},{'label': 'Sports & Recreation','fieldname': 'sports_rating','fieldtype': 'Rating','options': '5'},{'label': 'Other Campus Life Notes','fieldname': 'campus_life_notes','fieldtype': 'Small Text'},{'label': 'Action Plan','fieldname': 'action_plan_tab','fieldtype': 'Tab Break'},{'label': 'Next Steps','fieldname': 'action_plan_sb','fieldtype': 'Section Break'},{'label': 'Follow-up Required?','fieldname': 'follow_up_required','fieldtype': 'Check'},{'label': 'Action Items for Student','fieldname': 'action_items_student','fieldtype': 'Text'},{'label': 'Action Items for Mentor','fieldname': 'action_items_mentor','fieldtype': 'Text'},{'label': 'Notify Parent','fieldname': 'notify_parent','fieldtype': 'Check','description': 'If checked, an email can be triggered to the parent/guardian.'}],'permissions': [{'role': 'System Manager','read': 1,'write': 1,'create': 1,'delete': 1},{'role': 'Instructor','read': 1,'write': 1,'create': 1}]}
    ]
    for p in doctypes_to_create:
        if not frappe.db.exists('DocType',p['name']):
            frappe.get_doc(p).insert(ignore_permissions=True); print(f"    ✅ Created DocType: {p['name']}")
        else:
            print(f"    ⚪️ DocType '{p['name']}' already exists. Skipping.")
    print("--- Phase 1 Complete ---")

def create_mentorship_client_script():
    print("\n--- Phase 2: Creating Client Script ---")
    script_name, doctype_name = "Student Mentorship Profile - Custom Buttons and Dashboard", "Student Mentorship Profile"
    api_path = "srkr_frappe_app_api.api.get_student_academic_summary"
    client_script_code = f"""
frappe.ui.form.on('Student Mentorship Profile', {{
    refresh: function(frm) {{
        // Add custom button to create a new mentorship log
        if (!frm.is_new() && frm.doc.docstatus === 1) {{
            frm.add_custom_button(__('Add Mentorship Log'), function() {{
                frappe.new_doc('Mentorship Log Entry', {{
                    'student': frm.doc.student,
                    'mentor': frm.doc.current_mentor
                }});
            }}, __('Create'));
        }}
        
        // Load and display academic data
        if (frm.doc.student) {{
            let dashboardArea = frm.get_field("academic_performance_html").$wrapper;
            dashboardArea.html('<div class="p-3"><p class="text-muted text-center"><i class="fa fa-spinner fa-spin fa-2x"></i><br><em>Loading academic data...</em></p></div>');
            
            frappe.call({{
                method: "{api_path}",
                args: {{
                    student: frm.doc.student
                }},
                callback: function(r) {{
                    if (r.message) {{
                        let data = r.message;
                        let output = '';
                        
                        // Current Term Attendance
                        output += '<div class="card mb-4"><div class="card-header bg-light"><h5 class="mb-0">Current Term Attendance</h5></div><div class="card-body">';
                        
                        if (data.courses && data.courses.length > 0) {{
                            output += '<table class="table table-bordered table-sm"><thead class="thead-light"><tr><th>Course Code</th><th>Course Name</th><th style="text-align:right;">Attendance %</th></tr></thead><tbody>';
                            
                            data.courses.forEach(course => {{
                                let attendanceClass = '';
                                if (course.attendance !== 'N/A') {{
                                    attendanceClass = parseFloat(course.attendance) < 75 ? 'text-danger font-weight-bold' : 'text-success';
                                }}
                                
                                output += `<tr>
                                    <td>${{course.course_code}}</td>
                                    <td>${{course.course_name}}</td>
                                    <td class="${{attendanceClass}}" style="text-align:right;">${{course.attendance}}%</td>
                                </tr>`;
                            }});
                            
                            output += '</tbody></table>';
                        }} else {{
                            output += '<p class="text-muted">No course enrollments found for the current term.</p>';
                        }}
                        
                        output += '</div></div>';
                        
                        // Exam Results Section
                        output += '<div class="card"><div class="card-header bg-light"><h5 class="mb-0">Exam Results</h5></div><div class="card-body">';
                        
                        if (data.results && data.results.length > 0) {{
                            // Semester Summary
                            output += '<div class="table-responsive mb-4"><table class="table table-bordered table-sm"><thead class="thead-light"><tr><th>Semester</th><th style="text-align:right;">SGPA</th><th style="text-align:right;">CGPA</th><th style="text-align:right;">Credits Secured</th><th style="text-align:right;">Total Credits</th></tr></thead><tbody>';
                            
                            data.results.forEach(result => {{
                                output += `<tr>
                                    <td>${{result.semester}}</td>
                                    <td style="text-align:right;">${{result.sgpa}}</td>
                                    <td style="text-align:right;">${{result.cgpa}}</td>
                                    <td style="text-align:right;">${{result.credits_secured}}</td>
                                    <td style="text-align:right;">${{result.total_credits}}</td>
                                </tr>`;
                            }});
                            
                            output += '</tbody></table></div>';
                            
                            // Latest Semester Subjects
                            if (data.results[0] && data.results[0].subjects && data.results[0].subjects.length > 0) {{
                                output += `<h6 class="text-muted">Latest Results (${data.results[0].semester})</h6>`;
                                output += '<div class="table-responsive"><table class="table table-bordered table-sm"><thead class="thead-light"><tr><th>Subject Code</th><th>Subject Name</th><th>Credits</th><th>Grade</th><th>Result</th></tr></thead><tbody>';
                                
                                data.results[0].subjects.forEach(subject => {{
                                    let resultClass = subject.result === 'PASS' ? 'text-success' : 'text-danger font-weight-bold';
                                    
                                    output += `<tr>
                                        <td>${{subject.subject_code}}</td>
                                        <td>${{subject.subject_name}}</td>
                                        <td>${{subject.credits}}</td>
                                        <td>${{subject.grade}}</td>
                                        <td class="${{resultClass}}">${{subject.result}}</td>
                                    </tr>`;
                                }});
                                
                                output += '</tbody></table></div>';
                            }}
                        }} else {{
                            output += '<p class="text-muted">No exam results found for this student.</p>';
                        }}
                        
                        output += '</div></div>';
                        
                        dashboardArea.html(output);
                    }} else {{
                        dashboardArea.html('<div class="alert alert-warning">Unable to load academic data. Please try again later.</div>');
                    }}
                }},
                error: function() {{
                    dashboardArea.html('<div class="alert alert-danger"><i class="fa fa-exclamation-triangle"></i> Error loading academic data. Please check network connection and try again.</div>');
                }}
            }});
        }}
    }}
}});"""

    if not frappe.db.exists("Client Script", {"name": script_name}):
        frappe.get_doc({
            "doctype": "Client Script",
            "name": script_name,
            "dt": doctype_name,
            "script": client_script_code
        }).insert(ignore_permissions=True)
        print(f"    ✅ Created Client Script: '{script_name}'")
    else:
        doc = frappe.get_doc("Client Script", script_name)
        doc.script = client_script_code
        doc.save(ignore_permissions=True)
        print(f"    ✅ Updated Client Script: '{script_name}'")
    print("--- Phase 2 Complete ---")

def configure_mentorship_links():
    print("\n--- Phase 3: Configuring Links Dashboard ---")
    try:
        doc = frappe.get_doc("DocType", "Student Mentorship Profile")
        if not any(d.link_doctype == "Mentorship Log Entry" for d in doc.get("links", [])):
            doc.append("links", {"link_doctype": "Mentorship Log Entry"})
            doc.save(ignore_permissions=True)
            print("    ✅ Added 'Mentorship Log Entry' to Profile's Connections.")
        else:
            print("    ⚪️ Link already configured. Skipping.")
    except Exception as e:
        print(f"    ❌ FAILED to configure links. Error: {e}")
    print("--- Phase 3 Complete ---")

def create_all_student_mentorship_profiles():
    print("\n--- Phase 4: Creating Profiles for All Students ---")
    enabled_students = frappe.get_all("Student", filters={"enabled": 1}, fields=["name"])
    if not enabled_students:
        print("    No enabled students found. Skipping.")
        return
        
    existing_profiles = frappe.get_all("Student Mentorship Profile", pluck="name")
    created, skipped, failed = 0, 0, 0
    
    for student in enabled_students:
        if student.name in existing_profiles:
            skipped += 1
            continue
            
        try:
            frappe.get_doc({
                "doctype": "Student Mentorship Profile",
                "student": student.name
            }).insert(ignore_permissions=True)
            created += 1
        except Exception as e:
            failed += 1
            print(f"    ❌ FAILED to create profile for {student.name}. Error: {e}")
            
    if created > 0:
        frappe.db.commit()
        
    print(f"    ✅ Successfully Created: {created} new profiles.")
    print(f"    ⚪️ Skipped: {skipped} profiles.")
    if failed > 0:
        print(f"    ❌ Failed: {failed} profiles.")
    print("--- Phase 4 Complete ---")

def run_complete_mentorship_setup():
    """
    Executes the complete setup process for the Mentorship module.
    This is the main function to call from the Frappe console.
    """
    print("\n===== SRKR MENTORSHIP MODULE SETUP =====\n")
    create_mentorship_doctypes()
    create_mentorship_client_script()
    configure_mentorship_links()
    create_all_student_mentorship_profiles()
    frappe.db.commit()
    print("\n\n✅✅✅ MENTORSHIP MODULE SETUP COMPLETE! ✅✅✅")
    print("\nIMPORTANT: Please exit the console and run 'bench migrate' to complete the setup.")

# Call this function from the console to run the setup
# run_complete_mentorship_setup()
