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
│  │  │  ├─ verification.py
│  │  │  └─ __init__.py
│  │  └─ __init__.py
│  ├─ core
│  │  ├─ config.py
│  │  ├─ database.py
│  │  ├─ department_roles.py
│  │  ├─ rbac.py
│  │  ├─ security.py
│  │  └─ __init__.py
│  ├─ main.py
│  ├─ models
│  │  ├─ application.py
│  │  ├─ application_history.py
│  │  ├─ application_stage.py
│  │  ├─ certificate.py
│  │  ├─ department.py
│  │  ├─ enums.py
│  │  ├─ school.py
│  │  ├─ student.py
│  │  ├─ user.py
│  │  └─ __init__.py
│  ├─ schemas
│  │  ├─ application.py
│  │  ├─ approval.py
│  │  ├─ approval_summary.py
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
│  │  ├─ email_service.py
│  │  ├─ notification_service.py
│  │  ├─ pdf_service.py
│  │  ├─ sheets_service.py
│  │  ├─ student_service.py
│  │  ├─ user_service.py
│  │  ├─ workflow_service.py
│  │  └─ __init__.py
│  ├─ static
│  │  ├─ certificates
│  │  │  └─ certificate_18cb5a20-106c-4823-aea5-599ef8bc4267.pdf
│  │  ├─ favicon.ico
│  │  └─ status.html
│  ├─ templates
│  │  ├─ email
│  │  │  ├─ application_approved.html
│  │  │  ├─ application_completed.html
│  │  │  ├─ application_created.html
│  │  │  ├─ application_rejected.html
│  │  │  └─ student_welcome.html
│  │  ├─ pdf
│  │  │  └─ certificate_template.html
│  │  └─ verification.html
│  └─ __init__.py
├─ Dockerfile
├─ LICENSE
├─ pytest.ini
├─ README.md
├─ requirements.txt
└─ tests
   ├─ conftest.py
   ├─ test_account.py
   ├─ test_applications.py
   ├─ test_approvals.py
   ├─ test_approvals_workflow.py
   ├─ test_auth.py
   ├─ test_auth_student.py
   ├─ test_departments.py
   ├─ test_email_mock.py
   ├─ test_metrics.py
   ├─ test_students.py
   ├─ test_student_registration.py
   ├─ test_users.py
   └─ __init__.py

```