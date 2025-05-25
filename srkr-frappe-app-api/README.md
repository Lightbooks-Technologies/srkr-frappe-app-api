### srkr-frappe-app-api/srkr-frappe-app-api/README.md

# Srkr Frappe App API

This project is a custom Frappe application designed to provide an API for managing student-related data and functionalities.

## Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/Lightbooks-Technologies/srkr-frappe-app-api --branch main
bench install-app srkr_frappe_app_api
```

## Usage

This app provides several API endpoints for interacting with student data. You can access the following endpoints:

- `GET /api/method/srkr_frappe_app_api.api.hello_world`: Returns a simple greeting message.
- `GET /api/method/srkr_frappe_app_api.api.get_student_attendance?student_id=<student_id>`: Retrieves attendance records for a specific student.
- `GET /api/method/srkr_frappe_app_api.api.get_student_details?student_id=<student_id>`: Retrieves details for a specific student based on their ID.
- `GET /api/method/srkr_frappe_app_api.api.get_user_details?email_id=<email_id>`: Retrieves details for a specific Frappe user based on their email ID.

## Contributing

Contributions are welcome! Please follow the standard practices for contributing to open-source projects. Ensure that you have installed `pre-commit` for code formatting and linting:

```bash
cd srkr_frappe_app_api
pre-commit install
```

## License

This project is licensed under the MIT License. See the [LICENSE](license.txt) file for more details.