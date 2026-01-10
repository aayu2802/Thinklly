"""Debug script to check database content"""
from db_single import get_session
from models import Student, Class
from teacher_models import Subject
from examination_models import ExaminationSubject

session = get_session()

print("=" * 60)
print("DATABASE DEBUG CHECK")
print("=" * 60)

# Check Students
print("\n1. STUDENTS:")
students = session.query(Student).limit(10).all()
print(f"   Total students found: {len(students)}")
for s in students:
    print(f"   - ID: {s.id}, Tenant: {s.tenant_id}, Class: {s.class_id}, Roll: {s.roll_number}, Name: {s.full_name}")

# Check Classes
print("\n2. CLASSES:")
classes = session.query(Class).limit(10).all()
print(f"   Total classes found: {len(classes)}")
for c in classes:
    print(f"   - ID: {c.id}, Tenant: {c.tenant_id}, Name: {c.class_name}")

# Check Subjects
print("\n3. SUBJECTS:")
subjects = session.query(Subject).limit(10).all()
print(f"   Total subjects found: {len(subjects)}")
for subj in subjects:
    print(f"   - ID: {subj.id}, Tenant: {subj.tenant_id}, Name: {subj.name}, Code: {subj.code}")

# Check ExaminationSubjects
print("\n4. EXAMINATION SUBJECTS:")
exam_subjects = session.query(ExaminationSubject).limit(10).all()
print(f"   Total exam subjects found: {len(exam_subjects)}")
for es in exam_subjects:
    print(f"   - ID: {es.id}, Exam: {es.examination_id}, Subject: {es.subject_id}, Class: {es.class_id}, Status: {es.mark_entry_status}")

print("\n" + "=" * 60)
print("END DEBUG")
print("=" * 60)

session.close()
