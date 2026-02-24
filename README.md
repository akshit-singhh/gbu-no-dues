
```
gbu-no-dues-management-backend
├─ .dockerignore
├─ app
│  ├─ api
│  │  ├─ deps.py
│  │  ├─ endpoints
│  │  │  ├─ academic.py
│  │  │  ├─ account.py
│  │  │  ├─ applications.py
│  │  │  ├─ approvals.py
│  │  │  ├─ auth.py
│  │  │  ├─ auth_student.py
│  │  │  ├─ common.py
│  │  │  ├─ jobs.py
│  │  │  ├─ logs.py
│  │  │  ├─ students.py
│  │  │  ├─ users.py
│  │  │  ├─ utils.py
│  │  │  ├─ verification.py
│  │  │  └─ __init__.py
│  │  └─ __init__.py
│  ├─ core
│  │  ├─ config.py
│  │  ├─ constants.py
│  │  ├─ database.py
│  │  ├─ department_roles.py
│  │  ├─ rate_limiter.py
│  │  ├─ rbac.py
│  │  ├─ security.py
│  │  ├─ seeding_logic.py
│  │  ├─ storage.py
│  │  └─ __init__.py
│  ├─ main.py
│  ├─ models
│  │  ├─ academic.py
│  │  ├─ application.py
│  │  ├─ application_stage.py
│  │  ├─ audit.py
│  │  ├─ certificate.py
│  │  ├─ department.py
│  │  ├─ enums.py
│  │  ├─ school.py
│  │  ├─ student.py
│  │  ├─ system_audit.py
│  │  ├─ user.py
│  │  └─ __init__.py
│  ├─ schemas
│  │  ├─ academic.py
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
│  │  ├─ turnstile.py
│  │  └─ __init__.py
│  ├─ static
│  │  ├─ certificates
│  │  │  ├─ certificate_06fb5dfb-ac70-447d-99aa-2034c2940320.pdf
│  │  │  ├─ certificate_13022946-d2a0-4117-b179-1731c0d1c124.pdf
│  │  │  ├─ certificate_25d87624-6480-4f5a-9f61-60c05c80299d.pdf
│  │  │  ├─ certificate_28515b0a-65b3-4040-8305-33a64de39d0f.pdf
│  │  │  ├─ certificate_2b5333a0-363f-4fcf-9086-8b0f73126532.pdf
│  │  │  ├─ certificate_34304394-48da-4bbb-8788-e38c5026d969.pdf
│  │  │  ├─ certificate_52b13478-2797-421b-b1d3-4f57b5ede50d.pdf
│  │  │  ├─ certificate_8c22f168-c5c3-41cc-a16c-83dda38ffb89.pdf
│  │  │  ├─ certificate_98f004d1-d5ec-4772-9947-c5bc042458b6.pdf
│  │  │  ├─ certificate_9e31453f-f942-4e8f-ab98-d676bc2a426d.pdf
│  │  │  ├─ certificate_a292b005-32a3-422f-9795-11ac8ca98d17.pdf
│  │  │  ├─ certificate_a3433008-75f3-4d90-b771-5b585f71f8bc.pdf
│  │  │  ├─ certificate_ad5709c9-04a8-47ba-95d6-65017ee888f6.pdf
│  │  │  ├─ certificate_c4e50742-cf33-42fc-a1ff-fcd949b205c4.pdf
│  │  │  ├─ certificate_cfd506bf-c0ca-4c71-9146-28301acf932b.pdf
│  │  │  ├─ certificate_e7340931-095b-4975-9dbc-d8feb057a78d.pdf
│  │  │  └─ certificate_eb543e70-accc-4290-bd28-3be426c30115.pdf
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
│  │  │  ├─ application_created.html
│  │  │  ├─ application_rejected.html
│  │  │  ├─ password_reset.html
│  │  │  ├─ pending_reminder.html
│  │  │  └─ student_welcome.html
│  │  ├─ pdf
│  │  │  └─ certificate_template.html
│  │  └─ verification.html
│  └─ __init__.py
├─ docker-compose.yml
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