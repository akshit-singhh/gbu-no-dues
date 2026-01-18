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
│  │  │  ├─ captcha.py
│  │  │  ├─ students.py
│  │  │  ├─ users.py
│  │  │  ├─ utils.py
│  │  │  ├─ verification.py
│  │  │  └─ __init__.py
│  │  └─ __init__.py
│  ├─ core
│  │  ├─ config.py
│  │  ├─ database.py
│  │  ├─ department_roles.py
│  │  ├─ rate_limiter.py
│  │  ├─ rbac.py
│  │  ├─ security.py
│  │  ├─ storage.py
│  │  └─ __init__.py
│  ├─ main.py
│  ├─ models
│  │  ├─ application.py
│  │  ├─ application_history.py
│  │  ├─ application_stage.py
│  │  ├─ audit.py
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
│  │  ├─ audit.py
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
│  │  ├─ pdf_service.py
│  │  ├─ student_service.py
│  │  ├─ user_service.py
│  │  ├─ workflow_service.py
│  │  └─ __init__.py
│  ├─ static
│  │  ├─ certificates
│  │  │  ├─ certificate_13022946-d2a0-4117-b179-1731c0d1c124.pdf
│  │  │  ├─ certificate_2b5333a0-363f-4fcf-9086-8b0f73126532.pdf
│  │  │  ├─ certificate_98f004d1-d5ec-4772-9947-c5bc042458b6.pdf
│  │  │  ├─ certificate_a292b005-32a3-422f-9795-11ac8ca98d17.pdf
│  │  │  └─ certificate_c4e50742-cf33-42fc-a1ff-fcd949b205c4.pdf
│  │  ├─ favicon.ico
│  │  ├─ fonts
│  │  │  ├─ ARIAL.TTF
│  │  │  └─ DejaVuSans-Bold.ttf
│  │  ├─ images
│  │  │  └─ gbu_logo.png
│  │  └─ status.html
│  ├─ templates
│  │  ├─ email
│  │  │  ├─ application_approved.html
│  │  │  ├─ application_completed.html
│  │  │  ├─ application_created.html
│  │  │  ├─ application_rejected.html
│  │  │  ├─ password_reset.html
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
   ├─ test_students.py
   ├─ test_student_registration.py
   ├─ test_users.py
   ├─ test_utils.py
   ├─ test_verification.py
   └─ __init__.py

```
```
