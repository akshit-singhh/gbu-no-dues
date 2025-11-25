from app.models.user import UserRole

# Map each role to allowed department IDs
DEPARTMENT_ROLE_MAP = {
    UserRole.Admin: "ALL",          # Admin can manage all departments
    UserRole.HOD: [1],              # Department (HOD)
    UserRole.Office: [2],           # Library
    UserRole.CellMember: [6],       # Exam Cell
    UserRole.Student: [],           # Students do not approve anything
}

# Optional: human friendly names (UI can use this)
DEPARTMENT_LABELS = {
    1: "Department",
    2: "Library",
    3: "Hostel",
    4: "Accounts",
    5: "Sports",
    6: "Exam Cell",
}
