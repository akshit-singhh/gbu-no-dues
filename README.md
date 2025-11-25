# gbu-no-dues-management-backend

```
gbu-no-dues-management-backend
├─ app
│  ├─ api
│  │  ├─ deps.py
│  │  ├─ endpoints
│  │  │  ├─ account.py
│  │  │  ├─ applications.py
│  │  │  ├─ approvals.py
│  │  │  ├─ auth.py
│  │  │  ├─ auth_student.py
│  │  │  ├─ dashboard.py
│  │  │  ├─ department.py
│  │  │  ├─ students.py
│  │  │  ├─ users.py
│  │  │  └─ __init__.py
│  │  └─ __init__.py
│  ├─ core
│  │  ├─ config.py
│  │  ├─ database.py
│  │  ├─ rbac.py
│  │  ├─ security.py
│  │  └─ __init__.py
│  ├─ main.py
│  ├─ models
│  │  ├─ application.py
│  │  ├─ application_history.py
│  │  ├─ application_stage.py
│  │  ├─ department.py
│  │  ├─ school.py
│  │  ├─ student.py
│  │  ├─ user.py
│  │  └─ __init__.py
│  ├─ schemas
│  │  ├─ application.py
│  │  ├─ approval.py
│  │  ├─ auth.py
│  │  ├─ auth_student.py
│  │  ├─ student.py
│  │  ├─ user.py
│  │  └─ __init__.py
│  ├─ services
│  │  ├─ application_service.py
│  │  ├─ approval_service.py
│  │  ├─ audit_service.py
│  │  ├─ auth_service.py
│  │  ├─ department_service.py
│  │  ├─ notification_service.py
│  │  ├─ pdf_service.py
│  │  ├─ sheets_service.py
│  │  ├─ student_service.py
│  │  ├─ user_service.py
│  │  ├─ workflow_service.py
│  │  └─ __init__.py
│  ├─ static
│  │  └─ favicon.ico
│  ├─ templates
│  │  ├─ email
│  │  │  ├─ application_approved.html
│  │  │  ├─ application_completed.html
│  │  │  ├─ application_created.html
│  │  │  └─ application_rejected.html
│  │  └─ pdf
│  │     └─ certificate_template.html
│  └─ __init__.py
├─ Dockerfile
├─ LICENSE
├─ pytest.ini
├─ README.md
├─ requirements.txt
└─ tests
   ├─ conftest.py
   ├─ test_applications.py
   ├─ test_approvals.py
   ├─ test_auth.py
   ├─ test_auth_student.py
   ├─ test_departments.py
   ├─ test_students.py
   ├─ test_student_registration.py
   ├─ test_users.py
   └─ __init__.py

```